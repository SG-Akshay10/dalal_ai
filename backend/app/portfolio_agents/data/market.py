"""Raw-market-data normalization and programmatic technical calculations."""

from __future__ import annotations

import math
from typing import Any

from app.services.market_data import market_snapshot
from app.services.portfolio_risk import SYMBOL_SECTORS
from app.services.sector_lookup import fetch_sector
from ..schemas import EnrichedHolding, FundamentalMetrics, HoldingInput, Technicals
from .fundamental import get_sector_benchmark
from .quality import holding_quality, market_data_is_fresh


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def resolve_sector(ticker: str, provided_sector: str | None, exchange: str = "NSE") -> str:
    if provided_sector:
        return provided_sector
    sector = fetch_sector(ticker, exchange)
    return sector if sector and sector != "Unknown" else SYMBOL_SECTORS.get(ticker, "Unknown")


def calculate_technicals(history: list[dict[str, Any]], indicators: dict[str, Any]) -> Technicals:
    closes = [float(row["close"]) for row in history if _finite(row.get("close"))]
    if len(closes) < 2:
        return Technicals(rsi14=indicators.get("rsi14"), macd_histogram=indicators.get("macd_histogram"), crossover=indicators.get("sma_crossover", "unavailable"))
    returns = [closes[index] / closes[index - 1] - 1 for index in range(1, len(closes))]
    mean = sum(returns) / len(returns)
    volatility = math.sqrt(sum((item - mean) ** 2 for item in returns) / max(1, len(returns) - 1)) * math.sqrt(252) * 100
    peak = closes[0]
    drawdown = min((price / max(peak := max(peak, price), 0.000001) - 1) * 100 for price in closes)
    recent = closes[-60:] if len(closes) >= 60 else closes
    return Technicals(rsi14=indicators.get("rsi14"), sma50=history[-1].get("sma50"), sma200=history[-1].get("sma200"), macd_histogram=indicators.get("macd_histogram"), crossover=indicators.get("sma_crossover", "unavailable"), annualized_volatility_pct=round(volatility, 2), support=round(min(recent), 2), resistance=round(max(recent), 2), max_drawdown_pct=round(drawdown, 2))


def enrich_holding(holding: HoldingInput) -> EnrichedHolding:
    ticker, errors = (holding.ticker or holding.symbol or "").upper(), []
    price, history, indicators, source, as_of = holding.current_price, list(holding.historical_prices), {}, "client-supplied", holding.market_data_as_of
    pe_ratio, de_ratio = None, None
    if history and market_data_is_fresh(as_of):
        latest = history[-1]
        indicators = {"rsi14": latest.get("rsi14"), "macd_histogram": latest.get("macd_histogram"), "sma_crossover": "bullish" if latest.get("sma50") is not None and latest.get("sma200") is not None and float(latest["sma50"]) > float(latest["sma200"]) else "bearish" if latest.get("sma50") is not None and latest.get("sma200") is not None and float(latest["sma50"]) < float(latest["sma200"]) else "neutral"}
    else:
        source = "Yahoo Finance (delayed)"
        try:
            snapshot = market_snapshot(ticker, holding.exchange)
            price, history, indicators, as_of = snapshot.get("price") or price, snapshot.get("history", []), snapshot.get("indicators", {}), snapshot.get("as_of")
            pe_ratio, de_ratio = _finite(snapshot.get("pe_ratio")), _finite(snapshot.get("de_ratio"))
        except Exception as exc:
            errors.append(f"Market data unavailable: {exc}")
    missing = (["current_price"] if price is None else []) + (["historical_prices"] if len(history) < 2 else [])
    if price is None: errors.append("Current price unavailable")
    pnl = ((price - holding.buy_price) / holding.buy_price * 100) if price is not None and holding.buy_price else None
    sector = resolve_sector(ticker, holding.sector, holding.exchange)
    bm = get_sector_benchmark(sector)
    fundamentals = FundamentalMetrics(
        pe_ratio=pe_ratio,
        de_ratio=de_ratio,
        benchmark_pe=bm.get("pe_ratio"),
        benchmark_roe_pct=bm.get("roe_pct"),
    )
    return EnrichedHolding(
        ticker=ticker, sector=sector, quantity=holding.quantity, buy_price=holding.buy_price,
        current_price=price, market_value=price * holding.quantity if price is not None else None,
        pnl_pct=round(pnl, 2) if pnl is not None else None, technicals=calculate_technicals(history, indicators),
        fundamentals=fundamentals, data_errors=errors,
        data_quality=holding_quality(source=source, as_of=as_of, errors=errors, missing_fields=missing)
    )
