"""Yahoo Finance backed NSE symbol resolution, quotes, and chart series.

The service deliberately keeps the browser independent of Yahoo's response
shape.  Yahoo is a delayed, best-effort source; callers should surface the
``source`` and ``as_of`` fields to users.
"""

from __future__ import annotations

import math
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

import httpx

try:  # Optional accelerator. The REST path remains fully functional.
    import yfinance as yf
except ImportError:  # pragma: no cover - depends on deployment environment
    yf = None


YAHOO_HEADERS = {"User-Agent": "dalal.ai/1.0"}
_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = threading.Lock()

# This is intentionally a small, high-confidence seed. Yahoo search fills in
# the long tail of NSE listings and lets aliases stay maintainable as names
# change. Keys are normalized (letters and digits only).
ALIASES = {
    "sbi": "SBIN", "state bank of india": "SBIN", "l t": "LT", "l and t": "LT",
    "hdfc bank": "HDFCBANK", "hdfcbank": "HDFCBANK", "tata motors": "TMPV",
    "tata motors passenger vehicles": "TMPV", "tata motors commercial vehicles": "TMCV",
    "zomato": "ETERNAL", "eternal": "ETERNAL", "reliance": "RELIANCE",
    "infosys": "INFY", "tcs": "TCS", "tata consultancy services": "TCS",
    "icici bank": "ICICIBANK", "kotak bank": "KOTAKBANK", "axis bank": "AXISBANK",
    "bharti airtel": "BHARTIARTL", "airtel": "BHARTIARTL", "itc": "ITC",
    "adani enterprises": "ADANIENT", "adani ports": "ADANIPORTS", "maruti": "MARUTI",
    "mahindra and mahindra": "M&M", "m m": "M&M", "hindustan unilever": "HINDUNILVR",
    "tata steel": "TATASTEEL", "tata power": "TATAPOWER", "asian paints": "ASIANPAINT",
    "silverbees e": "SILVERBEES", "silverbees": "SILVERBEES", "goldbees": "GOLDBEES",
}


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _normalize_symbol(symbol: str) -> str:
    """Normalize common Indian broker/export suffixes before Yahoo lookup."""
    clean = symbol.strip().upper().removesuffix(".NS").removesuffix(".BO")
    # NSE exports commonly append -E/-EQ (equity series) to the Yahoo ticker.
    clean = re.sub(r"-(?:E|EQ)$", "", clean)
    return clean


def _cached(key: str, ttl: int, loader):
    now = time.monotonic()
    with _cache_lock:
        item = _cache.get(key)
        if item and item[0] > now:
            return item[1]
    value = loader()
    with _cache_lock:
        _cache[key] = (now + ttl, value)
    return value


def _get(path: str, params: dict[str, Any], timeout: float = 8.0) -> dict[str, Any]:
    response = httpx.get("https://query1.finance.yahoo.com" + path, params=params,
                         headers=YAHOO_HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _quote_is_nse(quote: dict[str, Any]) -> bool:
    return (quote.get("exchange") in {"NSI", "NSE"} or str(quote.get("symbol", "")).endswith(".NS"))


def _direct_probe(symbol: str) -> Optional[dict[str, Any]]:
    symbol = _normalize_symbol(symbol)
    try:
        result = _get(f"/v8/finance/chart/{symbol}.NS", {"range": "5d", "interval": "1d"})
        chart = (result.get("chart") or {}).get("result") or []
        if chart:
            meta = chart[0].get("meta", {})
            return {"symbol": symbol, "name": meta.get("longName") or meta.get("shortName") or symbol,
                    "exchange": "NSE", "yahoo_symbol": f"{symbol}.NS"}
    except Exception:
        return None
    return None


def resolve_ticker(query: str) -> dict[str, Any]:
    """Resolve a company name, alias, partial name, or ticker to NSE."""
    clean = query.strip()
    if not clean:
        raise ValueError("Ticker or company name is required")
    normalized = _key(clean)
    alias = ALIASES.get(normalized)
    if alias:
        probe = _cached(f"probe:{alias}", 3600, lambda: _direct_probe(alias))
        if probe:
            return probe | {"matched_by": "alias"}

    def search():
        data = _get("/v1/finance/search", {"q": clean, "quotesCount": 20, "newsCount": 0})
        quotes = [q for q in data.get("quotes", []) if q.get("quoteType") == "EQUITY" and _quote_is_nse(q)]
        return quotes

    try:
        quotes = _cached(f"search:{normalized}", 3600, search)
        if quotes:
            best = quotes[0]
            return {"symbol": best["symbol"].removesuffix(".NS"),
                    "name": best.get("longname") or best.get("shortname") or best["symbol"],
                    "exchange": "NSE", "yahoo_symbol": best["symbol"], "matched_by": "yahoo_search"}
    except Exception:
        pass

    # Optional SDK fallback for installations that already include yfinance.
    if yf:
        try:
            results = yf.Search(clean).quotes
            for quote in results:
                symbol = quote.get("symbol", "")
                if symbol.endswith(".NS"):
                    return {"symbol": symbol[:-3], "name": quote.get("longname") or clean,
                            "exchange": "NSE", "yahoo_symbol": symbol, "matched_by": "yfinance"}
        except Exception:
            pass

    candidate = re.sub(r"[^A-Za-z0-9&]", "", clean).upper()
    direct = _cached(f"probe:{candidate}", 3600, lambda: _direct_probe(candidate))
    if direct:
        return direct | {"matched_by": "direct_probe"}
    raise ValueError(f"No NSE-listed company matched '{query}'")


def search_tickers(query: str, limit: int = 8) -> list[dict[str, Any]]:
    if not query.strip():
        return []
    try:
        quotes = _cached(f"search:{_key(query)}", 3600,
                         lambda: _get("/v1/finance/search", {"q": query, "quotesCount": 20, "newsCount": 0}).get("quotes", []))
        return [{"symbol": q["symbol"].removesuffix(".NS"), "name": q.get("longname") or q.get("shortname"),
                 "exchange": "NSE"} for q in quotes if q.get("quoteType") == "EQUITY" and _quote_is_nse(q)][:limit]
    except Exception:
        return []


def _finite(value: Any) -> Optional[float]:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _sma(values: list[Optional[float]], window: int) -> list[Optional[float]]:
    output = []
    for index in range(len(values)):
        chunk = [v for v in values[max(0, index - window + 1): index + 1] if v is not None]
        output.append(sum(chunk) / window if len(chunk) == window else None)
    return output


def market_snapshot(symbol: str, exchange: str = "NSE") -> dict[str, Any]:
    """Return quote, fundamentals, and two years of daily chart data."""
    normalized_symbol = _normalize_symbol(symbol)
    yahoo_symbol = f"{normalized_symbol}.{ 'NS' if exchange.upper() == 'NSE' else 'BO' }"

    def load():
        result = _get(f"/v8/finance/chart/{yahoo_symbol}", {"range": "2y", "interval": "1d", "events": "div,splits"}, 12)
        chart = (result.get("chart") or {}).get("result") or []
        if not chart:
            raise ValueError("Yahoo returned no chart data")
        item = chart[0]
        meta = item.get("meta", {})
        timestamps = item.get("timestamp") or []
        quote = (item.get("indicators") or {}).get("quote", [{}])[0]
        rows = []
        for index, stamp in enumerate(timestamps):
            close = _finite((quote.get("close") or [])[index] if index < len(quote.get("close", [])) else None)
            if close is None:
                continue
            # Sparse Yahoo candles occasionally omit an intraday field. Keep
            # the daily series chart-safe rather than failing the whole chart.
            open_price = _finite((quote.get("open") or [])[index] if index < len(quote.get("open", [])) else None) or close
            high = _finite((quote.get("high") or [])[index] if index < len(quote.get("high", [])) else None) or max(open_price, close)
            low = _finite((quote.get("low") or [])[index] if index < len(quote.get("low", [])) else None) or min(open_price, close)
            rows.append({"time": datetime.fromtimestamp(stamp, timezone.utc).date().isoformat(),
                         "open": open_price, "high": max(high, open_price, close),
                         "low": min(low, open_price, close), "close": close,
                         "volume": _finite((quote.get("volume") or [])[index]) or 0})
        closes = [row["close"] for row in rows]
        sma50, sma200 = _sma(closes, 50), _sma(closes, 200)
        for index, row in enumerate(rows):
            row["sma50"], row["sma200"] = sma50[index], sma200[index]
            window = closes[max(0, index - 19): index + 1]
            if len(window) == 20:
                mean = sum(window) / 20
                deviation = math.sqrt(sum((value - mean) ** 2 for value in window) / 20)
                row["bollinger_upper"], row["bollinger_lower"] = mean + 2 * deviation, mean - 2 * deviation
            else:
                row["bollinger_upper"] = row["bollinger_lower"] = None
        price = _finite(meta.get("regularMarketPrice")) or (rows[-1]["close"] if rows else None)
        previous = _finite(meta.get("previousClose")) or _finite(meta.get("chartPreviousClose"))
        return {"symbol": normalized_symbol, "exchange": exchange.upper(), "name": meta.get("longName") or normalized_symbol,
                "price": price, "previous_close": previous,
                "day_change_pct": ((price - previous) / previous * 100) if price is not None and previous else None,
                "volume": rows[-1]["volume"] if rows else None, "currency": meta.get("currency", "INR"),
                "history": rows, "source": "Yahoo Finance (delayed)", "as_of": datetime.now(timezone.utc).isoformat()}

    snapshot = _cached(f"snapshot:{yahoo_symbol}", 60, load)
    # quoteSummary provides PE and D/E; absence should not make the chart fail.
    try:
        summary = _get(f"/v10/finance/quoteSummary/{yahoo_symbol}", {"modules": "summaryDetail,defaultKeyStatistics"})
        modules = ((summary.get("quoteSummary") or {}).get("result") or [{}])[0]
        detail, stats = modules.get("summaryDetail", {}), modules.get("defaultKeyStatistics", {})
        snapshot = dict(snapshot)
        snapshot["pe_ratio"] = (detail.get("trailingPE") or stats.get("trailingPE") or {}).get("raw") if isinstance(detail.get("trailingPE") or stats.get("trailingPE"), dict) else None
        snapshot["de_ratio"] = (stats.get("debtToEquity") or {}).get("raw")
    except Exception:
        snapshot = dict(snapshot)
        snapshot.setdefault("pe_ratio", None)
        snapshot.setdefault("de_ratio", None)
    return snapshot
