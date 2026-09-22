"""Structured, deterministic portfolio risk and diversification analysis."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional

from app.services.sarvam import summarize_portfolio_risk
from app.services.sector_lookup import fetch_sector

# Broad categories make missing exposure explicit rather than pretending every
# portfolio must own every possible industry.
DEFAULT_SECTORS = ["Financial Services", "Information Technology", "Healthcare", "Consumer Goods", "Industrials", "Energy", "Utilities", "Materials", "Communication Services", "Real Estate"]
SYMBOL_SECTORS = {"INFY": "Information Technology", "TCS": "Information Technology", "WIPRO": "Information Technology", "HCLTECH": "Information Technology", "HDFCBANK": "Financial Services", "ICICIBANK": "Financial Services", "SBIN": "Financial Services", "AXISBANK": "Financial Services", "KOTAKBANK": "Financial Services", "RELIANCE": "Energy", "ONGC": "Energy", "TATAPOWER": "Utilities", "NTPC": "Utilities", "ITC": "Consumer Goods", "HINDUNILVR": "Consumer Goods", "MARUTI": "Industrials", "TATAMOTORS": "Industrials", "SUNPHARMA": "Healthcare", "CIPLA": "Healthcare", "DRREDDY": "Healthcare", "TATASTEEL": "Materials", "HINDALCO": "Materials", "BHARTIARTL": "Communication Services", "DLF": "Real Estate"}


def _number(value: Any) -> Optional[float]:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _annualized_volatility(prices: Iterable[Any]) -> Optional[float]:
    closes = [value for value in (_number(item) for item in prices) if value is not None and value > 0]
    if len(closes) < 2:
        return None
    returns = [closes[index] / closes[index - 1] - 1 for index in range(1, len(closes))]
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    return round(math.sqrt(variance) * math.sqrt(252) * 100, 2)


def _cap_classification(market_cap: Optional[float]) -> Optional[str]:
    if market_cap is None:
        return None
    # INR thresholds: ₹20,000 crore and ₹5,000 crore, respectively.
    if market_cap >= 200_000_000_000:
        return "Large Cap"
    if market_cap >= 50_000_000_000:
        return "Mid Cap"
    return "Small Cap"


def _risk_rating(volatility: Optional[float], cap_class: Optional[str], beta: Optional[float], momentum: Optional[float]) -> str:
    score = 0
    score += 2 if volatility is None else 2 if volatility >= 40 else 1 if volatility >= 25 else 0
    score += {"Small Cap": 2, "Mid Cap": 1}.get(cap_class, 0)
    score += 1 if beta is not None and beta >= 1.3 else 0
    score += 1 if momentum is not None and momentum <= -15 else 0
    return "High" if score >= 4 else "Medium" if score >= 2 else "Low"


def _return_potential(holding: Dict[str, Any]) -> Dict[str, Any]:
    price, target, momentum = _number(holding.get("current_price")), _number(holding.get("analyst_target_price")), _number(holding.get("recent_momentum_pct"))
    upside = round((target - price) / price * 100, 2) if price and target else None
    growth = str(holding.get("growth_outlook") or "Unknown").title()
    score = (1 if upside is not None and upside >= 15 else -1 if upside is not None and upside <= -10 else 0) + (1 if momentum is not None and momentum >= 10 else -1 if momentum is not None and momentum <= -10 else 0) + {"Positive": 1, "Negative": -1}.get(growth, 0)
    outlook = "Positive" if score >= 1 else "Negative" if score <= -1 else "Neutral"
    return {"outlook": outlook, "analyst_upside_pct": upside, "recent_momentum_pct": momentum, "growth_outlook": growth}


def stock_level_risk_profile(holdings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    profiles = []
    for holding in holdings:
        symbol = str(holding.get("ticker") or holding.get("symbol") or "UNKNOWN").upper()
        errors = []
        sector = holding.get("sector")
        if not sector:
            sector = fetch_sector(symbol, holding.get("exchange", "NSE"))
            if sector == "Unknown":
                sector = SYMBOL_SECTORS.get(symbol)
        if not sector:
            errors.append("Missing sector")
        volatility = _number(holding.get("annualized_volatility_pct")) or _annualized_volatility(holding.get("historical_prices") or [])
        if volatility is None:
            errors.append("Missing volatility data")
        market_cap = _number(holding.get("market_cap"))
        cap_class = _cap_classification(market_cap)
        if cap_class is None:
            errors.append("Missing market capitalization")
        beta, momentum = _number(holding.get("beta")), _number(holding.get("recent_momentum_pct"))
        profiles.append({"ticker": symbol, "sector": sector or "Unknown", "volatility": {"annualized_pct": volatility, "beta": beta}, "market_cap": {"value": market_cap, "currency": holding.get("market_cap_currency", "INR"), "classification": cap_class}, "return_potential": _return_potential(holding), "overall_risk_rating": _risk_rating(volatility, cap_class, beta, momentum), "data_quality": {"complete": not errors, "errors": errors}})
    return profiles


def sector_level_risk_profile(stock_profiles: List[Dict[str, Any]], holdings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    values = {str(item.get("ticker") or item.get("symbol") or "UNKNOWN").upper(): (_number(item.get("quantity")) or 0) * (_number(item.get("current_price")) or _number(item.get("buy_price")) or 0) for item in holdings}
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for profile in stock_profiles:
        grouped[profile["sector"]].append(profile)
    output = []
    for sector, stocks in grouped.items():
        weights = [values.get(stock["ticker"], 0) for stock in stocks]
        total_weight = sum(weights)
        vol_pairs = [(stock["volatility"]["annualized_pct"], weights[index]) for index, stock in enumerate(stocks) if stock["volatility"]["annualized_pct"] is not None]
        average_volatility = round(sum(vol * (weight / total_weight if total_weight else 1 / len(vol_pairs)) for vol, weight in vol_pairs), 2) if vol_pairs else None
        caps = {key: sum(1 for stock in stocks if stock["market_cap"]["classification"] == key) for key in ("Large Cap", "Mid Cap", "Small Cap", "Unknown")}
        caps["Unknown"] = sum(1 for stock in stocks if stock["market_cap"]["classification"] is None)
        outlooks = [stock["return_potential"]["outlook"] for stock in stocks]
        outlook = "Positive" if outlooks.count("Positive") > outlooks.count("Negative") else "Negative" if outlooks.count("Negative") > outlooks.count("Positive") else "Neutral"
        risks = [stock["overall_risk_rating"] for stock in stocks]
        rating = "High" if risks.count("High") >= max(1, len(risks) / 2) else "Medium" if "Medium" in risks or "High" in risks else "Low"
        output.append({"sector": sector, "stock_count": len(stocks), "average_volatility_pct": average_volatility, "market_cap_distribution": caps, "return_potential_outlook": outlook, "overall_sector_risk_rating": rating})
    return sorted(output, key=lambda item: item["sector"])


def diversification_analysis(holdings: List[Dict[str, Any]], stock_profiles: List[Dict[str, Any]], sector_profiles: List[Dict[str, Any]], concentration_threshold_pct: float = 35, minimum_allocation_pct: float = 5) -> Dict[str, Any]:
    sector_values: Dict[str, float] = defaultdict(float)
    errors = []
    for holding, profile in zip(holdings, stock_profiles):
        quantity, price = _number(holding.get("quantity")), _number(holding.get("current_price")) or _number(holding.get("buy_price"))
        if quantity is None or price is None:
            errors.append(f"{profile['ticker']}: missing quantity or price; excluded from allocation")
            continue
        sector_values[profile["sector"]] += quantity * price
    total = sum(sector_values.values())
    allocations = [{"sector": sector, "value": round(value, 2), "allocation_pct": round(value / total * 100, 2) if total else 0} for sector, value in sector_values.items()]
    allocations.sort(key=lambda item: item["allocation_pct"], reverse=True)
    concentrated = [item for item in allocations if item["allocation_pct"] >= concentration_threshold_pct]
    known = set(sector_values) - {"Unknown"}
    under_exposed = sorted(sector for sector in DEFAULT_SECTORS if sector not in known or (next((item["allocation_pct"] for item in allocations if item["sector"] == sector), 0) < minimum_allocation_pct))
    ratings = [item["overall_sector_risk_rating"] for item in sector_profiles]
    risk = "High" if concentrated and any(item["overall_sector_risk_rating"] == "High" for item in sector_profiles if item["sector"] in {flag["sector"] for flag in concentrated}) else "Medium" if concentrated or "High" in ratings or "Medium" in ratings else "Low"
    verdict = f"Concentrated in {concentrated[0]['sector']}" if concentrated else "Well diversified" if len(known) >= 5 else "Limited sector diversification"
    return {"sector_allocation": allocations, "concentration_threshold_pct": concentration_threshold_pct, "concentration_flags": [{"sector": item["sector"], "allocation_pct": item["allocation_pct"], "message": f"{item['sector']} exceeds the {concentration_threshold_pct}% concentration threshold."} for item in concentrated], "under_exposed_or_missing_sectors": under_exposed, "overall_portfolio_risk_level": risk, "diversification_score": round(max(0, min(100, 100 - (max((item["allocation_pct"] for item in allocations), default=100) - 20) - len(under_exposed) * 2)), 1), "summary_verdict": verdict, "data_quality": {"complete": not errors and "Unknown" not in sector_values, "errors": errors}}


def analyze_portfolio_risk(holdings: List[Dict[str, Any]], include_llm_insight: bool = True, concentration_threshold_pct: float = 35, minimum_allocation_pct: float = 5) -> Dict[str, Any]:
    """Analyze raw holdings and return the three report-ready JSON modules."""
    stocks = stock_level_risk_profile(holdings)
    sectors = sector_level_risk_profile(stocks, holdings)
    diversification = diversification_analysis(holdings, stocks, sectors, concentration_threshold_pct, minimum_allocation_pct)
    insight = summarize_portfolio_risk(stocks, sectors, diversification) if include_llm_insight else None
    return {"expected_input_schema": {"required": ["ticker (or symbol)", "quantity"], "recommended": ["sector", "current_price (or buy_price)", "annualized_volatility_pct (or historical_prices)", "market_cap", "beta", "analyst_target_price", "recent_momentum_pct", "growth_outlook"]}, "stock_level_risk_profiles": stocks, "sector_level_risk_profiles": sectors, "portfolio_diversification_analysis": diversification, "summary": {"portfolio_risk_level": diversification["overall_portfolio_risk_level"], "diversification_verdict": diversification["summary_verdict"], "sarvam_insight": insight, "disclaimer": "Risk profiles are informational estimates, not investment advice."}}
