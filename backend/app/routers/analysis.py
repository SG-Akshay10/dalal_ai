from io import BytesIO
import logging
import csv
import io
from zipfile import ZipFile
import xml.etree.ElementTree as ET
from typing import Any, Dict, List
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.database import DatabaseManager
from app.services.market_data import market_quote, market_snapshot
from app.portfolio_agents.graph import PortfolioAnalysisUnavailable, run_portfolio_pipeline

router = APIRouter(prefix="/api", tags=["analysis"])
logger = logging.getLogger(__name__)
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def user_id(user: dict) -> str:
    value = user.get("sub") or user.get("id")
    if not value:
        raise HTTPException(status_code=401, detail="User ID not found in token")
    return value


class ManualHolding(BaseModel):
    symbol: str
    company_name: str | None = None
    quantity: float
    buy_price: float
    exchange: str = "NSE"


class PortfolioRiskRequest(BaseModel):
    """Raw holding data. `ticker`/`symbol` and `quantity` are required per item."""
    holdings: List[Dict[str, Any]] = Field(default_factory=list)
    include_llm_insight: bool = True
    concentration_threshold_pct: float = Field(default=35, gt=0, le=100)
    minimum_allocation_pct: float = Field(default=5, ge=0, le=100)


@router.post("/analysis/risk-profile")
def risk_profile(payload: PortfolioRiskRequest, user: dict = Depends(get_current_user)):
    """Produce stock, sector, and portfolio diversification JSON from raw holdings.

    Each holding should provide ticker (or symbol), quantity, sector and current_price;
    optional historical/fundamental fields improve the risk profile.
    """
    holdings = payload.holdings or DatabaseManager.get_holdings(user_id(user))
    if not holdings:
        raise HTTPException(status_code=400, detail="At least one holding is required.")
    invalid = [index for index, holding in enumerate(holdings) if not (holding.get("ticker") or holding.get("symbol")) or holding.get("quantity") is None]
    if invalid:
        raise HTTPException(status_code=422, detail=f"Holdings at indexes {invalid} require ticker (or symbol) and quantity.")
    try:
        state = run_portfolio_pipeline(holdings)
        report = state.report
        sector = state.sector_analysis
        risk = state.risk_analysis
        return {
            **state.model_dump(mode="json"),
            # Compatibility fields let the existing dashboard progressively
            # render the richer graph output without losing its summary view.
            "summary": {"portfolio_risk_level": risk.portfolio_risk_level if risk else "Medium", "diversification_verdict": report.headline if report else "Portfolio analysis", "sarvam_insight": report.executive_summary if report else None},
            "portfolio_diversification_analysis": {"sector_allocation": [{"sector": item.sector, "allocation_pct": item.allocation_pct} for item in (sector.findings if sector else [])], "concentration_flags": [{"sector": flag, "allocation_pct": 0} for flag in (sector.concentration_flags if sector else [])], "under_exposed_or_missing_sectors": sector.missing_sectors if sector else []},
            "stock_level_risk_profiles": [{"ticker": item.ticker, "sector": next((holding.sector for holding in state.enriched_holdings if holding.ticker == item.ticker), "Unknown"), "overall_risk_rating": item.severity} for item in (risk.findings if risk else [])],
            "executive_report": report.model_dump(mode="json") if report else None,
        }
    except PortfolioAnalysisUnavailable as exc:
        logger.warning("Portfolio AI analysis unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="AI analysis is temporarily unavailable. Please retry.") from exc


def parse_xlsx(raw: bytes) -> List[Dict[str, Any]]:
    with ZipFile(BytesIO(raw)) as book:
        strings_root = ET.fromstring(book.read("xl/sharedStrings.xml"))
        strings = ["".join(t.text or "" for t in si.findall(".//m:t", NS)) for si in strings_root.findall("m:si", NS)]
        sheet = ET.fromstring(book.read("xl/worksheets/sheet3.xml"))
        rows = []
        for row in sheet.findall(".//m:row", NS):
            values = {}
            for cell in row.findall("m:c", NS):
                value = cell.find("m:v", NS)
                if value is None:
                    continue
                text = value.text or ""
                if cell.attrib.get("t") == "s":
                    text = strings[int(text)]
                values[cell.attrib["r"][0]] = text
            if values:
                rows.append(values)
        header = next((row for row in rows if row.get("B") == "Symbol"), None)
        if not header:
            raise ValueError("Could not find the Combined holdings table")
        return [{"symbol": row.get("B", "").strip(), "quantity": float(row.get("F", 0) or 0), "buy_price": float(row.get("K", 0) or 0)} for row in rows[rows.index(header) + 1:] if row.get("B", "").strip() and row.get("F") and row.get("K")]


def parse_csv(raw: bytes) -> List[Dict[str, Any]]:
    text = raw.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows or not rows[0]:
        raise ValueError("CSV must include a header row")
    headers = {key.strip().lower(): key for key in rows[0] if key}
    symbol_key = next((headers[key] for key in ("symbol", "ticker", "stock") if key in headers), None)
    quantity_key = next((headers[key] for key in ("quantity", "qty", "shares") if key in headers), None)
    price_key = next((headers[key] for key in ("buy_price", "average price", "avg price", "average_price", "cost") if key in headers), None)
    if not symbol_key or not quantity_key or not price_key:
        raise ValueError("CSV must include Symbol, Quantity, and Buy Price columns")
    result = []
    for row in rows:
        symbol = (row.get(symbol_key) or "").strip()
        if symbol:
            result.append({"symbol": symbol, "quantity": float(row[quantity_key]), "buy_price": float(row[price_key])})
    return result


@router.post("/holdings/manual")
def add_manual(payload: ManualHolding, user: dict = Depends(get_current_user)):
    data = payload.model_dump()
    data["symbol"] = data["symbol"].strip().upper()
    data["company_name"] = data["company_name"] or f"{data['symbol']} Ltd"
    return DatabaseManager.add_holding(user_id(user), data)


@router.post("/holdings/import")
async def import_holdings(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".csv")):
        raise HTTPException(status_code=400, detail="Upload a .csv or .xlsx holdings file.")
    try:
        raw = await file.read()
        rows = parse_csv(raw) if file.filename.lower().endswith(".csv") else parse_xlsx(raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read spreadsheet: {exc}")
    imported = [DatabaseManager.add_holding(user_id(user), {**row, "company_name": f"{row['symbol']} Holdings", "exchange": "NSE"}) for row in rows]
    return {"count": len(imported), "holdings": imported}


@router.get("/analysis/portfolio")
def analyze_portfolio(user: dict = Depends(get_current_user)):
    holdings = DatabaseManager.get_holdings(user_id(user))
    def build_position(holding: Dict[str, Any]) -> Dict[str, Any]:
        quantity = float(holding.get("quantity") or 0)
        buy_price = float(holding.get("buy_price") or 0)
        invested = quantity * buy_price
        position = {"holding": holding, "invested_amount": invested, "current_amount": None, "quote": None, "error": None}
        try:
            quote = market_quote(holding["symbol"], holding.get("exchange", "NSE"))
            position["quote"] = {key: quote.get(key) for key in ("price", "previous_close", "day_change_pct", "source", "as_of", "currency")}
            if quote.get("price") is not None:
                position["current_amount"] = quantity * float(quote["price"])
        except Exception as exc:
            position["error"] = str(exc)
        return position
    # Quote requests are I/O bound; fetch positions concurrently so latency is
    # determined by the slowest holding rather than every holding combined.
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(holdings)))) as executor:
        positions = list(executor.map(build_position, holdings))
    total_invested = sum(position["invested_amount"] for position in positions)
    total_current = sum(position["current_amount"] or 0 for position in positions)
    return {"positions": positions, "total_invested": total_invested, "total_current": total_current,
            "price_coverage": sum(1 for item in positions if item["current_amount"] is not None)}


@router.get("/analysis/history/{symbol}")
def stock_history(symbol: str, exchange: str = "NSE", user: dict = Depends(get_current_user)):
    """Return the chart-ready, two-year daily price series for one holding."""
    try:
        snapshot = market_snapshot(symbol, exchange)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not load price history: {exc}")

    return {
        "symbol": snapshot["symbol"],
        "exchange": snapshot["exchange"],
        "history": snapshot["history"],
        "indicators": snapshot["indicators"],
        "source": snapshot["source"],
        "as_of": snapshot["as_of"],
    }
