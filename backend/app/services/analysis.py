"""Market data and portfolio insight helpers."""

from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx

from app.database import DatabaseManager


def fetch_live_price(symbol: str, exchange: str = "NSE") -> Dict[str, Any]:
    """Fetch a delayed quote from Yahoo Finance's free public quote endpoint."""
    suffix = ".NS" if exchange.upper() == "NSE" else ".BO"
    ticker = f"{symbol.upper()}{suffix}"
    try:
        response = httpx.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/" + ticker,
            params={"range": "1d", "interval": "1m"},
            headers={"User-Agent": "dalal.ai/1.0"},
            timeout=10.0,
        )
        response.raise_for_status()
        result = response.json()["chart"]["result"][0]
        meta = result["meta"]
        price = meta.get("regularMarketPrice") or meta.get("previousClose")
        previous = meta.get("previousClose") or meta.get("chartPreviousClose")
        change = ((price - previous) / previous * 100) if price and previous else None
        return {
            "price": price,
            "previous_close": previous,
            "day_change_pct": change,
            "currency": meta.get("currency", "INR"),
            "as_of": datetime.now(timezone.utc).isoformat(),
            "source": "Yahoo Finance (delayed)",
        }
    except Exception as exc:
        return {"price": None, "error": f"Live price unavailable: {exc}"}


def build_analysis(holding: Dict[str, Any], news: List[Dict[str, Any]]) -> Dict[str, Any]:
    avg = holding.get("buy_price")
    quantity = holding.get("quantity")
    quote = fetch_live_price(holding["symbol"], holding.get("exchange", "NSE"))
    price = quote.get("price")
    return_pct = ((price - avg) / avg * 100) if price is not None and avg else None
    sentiment_counts = {key: sum(1 for item in news if item.get("sentiment") == key) for key in ("positive", "negative", "neutral", "unclear")}

    pros: List[str] = []
    cons: List[str] = []
    if return_pct is not None:
        (pros if return_pct >= 0 else cons).append(f"Position is {abs(return_pct):.2f}% {('above' if return_pct >= 0 else 'below')} your average price.")
    if sentiment_counts["positive"] > sentiment_counts["negative"]:
        pros.append(f"Recent coverage leans positive ({sentiment_counts['positive']} positive vs {sentiment_counts['negative']} negative items).")
    elif sentiment_counts["negative"] > sentiment_counts["positive"]:
        cons.append(f"Recent coverage leans negative ({sentiment_counts['negative']} negative vs {sentiment_counts['positive']} positive items).")
    if not news:
        cons.append("There is not enough recent classified news to form a sentiment view.")
    if not pros:
        pros.append("No clear positive signal was identified in the available data.")
    if not cons:
        cons.append("No clear negative signal was identified in the available data.")

    return {
        "holding": holding,
        "quote": quote,
        "performance": {"return_pct": return_pct, "cost_basis": (avg * quantity if avg and quantity else None), "market_value": (price * quantity if price and quantity else None)},
        "sentiment": {"counts": sentiment_counts, "overall": "positive" if sentiment_counts["positive"] > sentiment_counts["negative"] else "negative" if sentiment_counts["negative"] > sentiment_counts["positive"] else "mixed", "news_count": len(news)},
        "pros": pros,
        "cons": cons,
        "news": news[:8],
        "disclaimer": "Insights combine your holding data, a delayed market quote, and recent news sentiment. They are not a recommendation to buy or sell.",
    }
