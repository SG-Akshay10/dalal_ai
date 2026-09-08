from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from app.services.market_data import market_snapshot
from app.services.portfolio_risk import DEFAULT_SECTORS, SYMBOL_SECTORS
from .schemas import EnrichedHolding, HoldingInput, Technicals


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def calculate_technicals(history: list[dict[str, Any]], indicators: dict[str, Any]) -> Technicals:
    closes = [float(row["close"]) for row in history if _finite(row.get("close"))]
    if len(closes) < 2:
        return Technicals(rsi14=indicators.get("rsi14"), macd_histogram=indicators.get("macd_histogram"), crossover=indicators.get("sma_crossover", "unavailable"))
    returns = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
    volatility = math.sqrt(sum((item - sum(returns) / len(returns)) ** 2 for item in returns) / max(1, len(returns) - 1)) * math.sqrt(252) * 100
    peak = closes[0]
    drawdown = min((price / max(peak := max(peak, price), 0.000001) - 1) * 100 for price in closes)
    recent = closes[-60:] if len(closes) >= 60 else closes
    return Technicals(rsi14=indicators.get("rsi14"), sma50=history[-1].get("sma50"), sma200=history[-1].get("sma200"), macd_histogram=indicators.get("macd_histogram"), crossover=indicators.get("sma_crossover", "unavailable"), annualized_volatility_pct=round(volatility, 2), support=round(min(recent), 2), resistance=round(max(recent), 2), max_drawdown_pct=round(drawdown, 2))


def enrich_holding(holding: HoldingInput) -> EnrichedHolding:
    ticker = (holding.ticker or holding.symbol or "").upper()
    errors: list[str] = []
    price, history, indicators = holding.current_price, [], {}
    try:
        snapshot = market_snapshot(ticker, holding.exchange)
        price = snapshot.get("price") or price
        history, indicators = snapshot.get("history", []), snapshot.get("indicators", {})
    except Exception as exc:
        errors.append(f"Market data unavailable: {exc}")
    if price is None:
        errors.append("Current price unavailable")
    pnl = ((price - holding.buy_price) / holding.buy_price * 100) if price is not None and holding.buy_price else None
    return EnrichedHolding(ticker=ticker, sector=holding.sector or SYMBOL_SECTORS.get(ticker, "Unknown"), quantity=holding.quantity, buy_price=holding.buy_price, current_price=price, market_value=price * holding.quantity if price is not None else None, pnl_pct=round(pnl, 2) if pnl is not None else None, technicals=calculate_technicals(history, indicators), data_errors=errors)


def allocation(holdings: list[EnrichedHolding]) -> tuple[dict[str, float], float]:
    values: dict[str, float] = defaultdict(float)
    for holding in holdings:
        if holding.market_value is not None:
            values[holding.sector] += holding.market_value
    total = sum(values.values())
    return dict(values), total


def diversification_score(values: dict[str, float], total: float) -> float:
    if not total:
        return 0
    hhi = sum((value / total) ** 2 for value in values.values())
    return round(max(0, min(100, (1 - hhi) * 125)), 1)


def missing_sectors(values: dict[str, float], total: float) -> list[str]:
    return [sector for sector in DEFAULT_SECTORS if not total or values.get(sector, 0) / total * 100 < 5]
