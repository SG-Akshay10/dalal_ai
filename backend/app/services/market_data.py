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
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional

import httpx

try:  # Optional accelerator. The REST path remains fully functional.
    import yfinance as yf
except ImportError:  # pragma: no cover - depends on deployment environment
    yf = None


YAHOO_HEADERS = {"User-Agent": "dalal.ai/1.0"}
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-IN,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}
_cache: dict[str, tuple[float, Any]] = {}
_cache_lock = threading.Lock()
_cache_key_locks: dict[str, threading.Lock] = {}
_yahoo_request_lock = threading.Lock()
_yahoo_next_request_at = 0.0

# Yahoo's public endpoints are best-effort and will throttle bursts from one
# deployment IP.  Keep requests deliberately modest; callers are already
# backed by the short-lived cache below.
YAHOO_MIN_REQUEST_INTERVAL_SECONDS = 0.35
YAHOO_MAX_RETRIES = 2

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
        key_lock = _cache_key_locks.setdefault(key, threading.Lock())

    # Coalesce simultaneous cache misses (for example, duplicate holdings in
    # a portfolio) into one Yahoo request.
    with key_lock:
        now = time.monotonic()
        with _cache_lock:
            item = _cache.get(key)
            if item and item[0] > now:
                return item[1]
        value = loader()
        with _cache_lock:
            _cache[key] = (time.monotonic() + ttl, value)
        return value


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    """Honor Yahoo's retry hint when supplied, with a bounded fallback."""
    try:
        retry_after = float(response.headers.get("Retry-After", ""))
        if retry_after >= 0:
            return min(retry_after, 10.0)
    except (TypeError, ValueError):
        pass
    return min(0.75 * (2 ** attempt), 5.0)


def _get(path: str, params: dict[str, Any], timeout: float = 8.0) -> dict[str, Any]:
    global _yahoo_next_request_at
    url = "https://query1.finance.yahoo.com" + path
    for attempt in range(YAHOO_MAX_RETRIES + 1):
        # Serialize outbound calls briefly. This avoids turning the portfolio
        # endpoint's worker pool into a burst against Yahoo's public API.
        with _yahoo_request_lock:
            wait = _yahoo_next_request_at - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            _yahoo_next_request_at = time.monotonic() + YAHOO_MIN_REQUEST_INTERVAL_SECONDS
            response = httpx.get(url, params=params, headers=YAHOO_HEADERS, timeout=timeout)
        if response.status_code != 429 or attempt == YAHOO_MAX_RETRIES:
            response.raise_for_status()
            return response.json()
        time.sleep(_retry_delay(response, attempt))
    raise RuntimeError("Yahoo request retry loop exited unexpectedly")  # pragma: no cover


def _nse_eod_rows(symbol: str, days: int) -> list[dict[str, Any]]:
    """Fetch daily NSE OHLCV rows from its security-wise EOD archive.

    NSE serves this browser-facing archive in one-year windows. Priming the
    session obtains the cookies expected by the archive endpoint; no Yahoo
    chart data is used here.
    """
    end = date.today()
    start = end - timedelta(days=days)
    chunks: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=364), end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    records: list[dict[str, Any]] = []
    with httpx.Client(headers=NSE_HEADERS, timeout=12.0, follow_redirects=True) as client:
        client.get("https://www.nseindia.com/").raise_for_status()
        for chunk_start, chunk_end in chunks:
            response = client.get(
                "https://www.nseindia.com/api/historical/securityArchives",
                params={"from": chunk_start.strftime("%d-%m-%Y"), "to": chunk_end.strftime("%d-%m-%Y"),
                        "symbol": symbol, "dataType": "priceVolumeDeliverable", "series": "EQ"},
            )
            response.raise_for_status()
            records.extend(response.json().get("data") or [])

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        try:
            day = datetime.strptime(str(record.get("CH_TIMESTAMP", "")), "%d-%b-%Y").date().isoformat()
        except ValueError:
            continue
        if day in seen:
            continue
        close = _finite(record.get("CH_CLOSING_PRICE"))
        if close is None:
            continue
        seen.add(day)
        open_price = _finite(record.get("CH_OPENING_PRICE")) or close
        high = _finite(record.get("CH_TRADE_HIGH_PRICE")) or max(open_price, close)
        low = _finite(record.get("CH_TRADE_LOW_PRICE")) or min(open_price, close)
        rows.append({"time": day, "open": open_price, "high": max(high, open_price, close),
                     "low": min(low, open_price, close), "close": close,
                     "volume": _finite(record.get("CH_TOT_TRADED_QTY")) or 0})
    rows.sort(key=lambda row: row["time"])
    if not rows:
        raise ValueError(f"NSE returned no EOD history for {symbol}")
    return rows


def _nse_eod_history(symbol: str, days: int) -> list[dict[str, Any]]:
    return _cached(f"nse-eod:{symbol}:{days}", 6 * 60 * 60, lambda: _nse_eod_rows(symbol, days))


def _yahoo_daily_closes(yahoo_symbol: str) -> list[float]:
    """Fallback only when NSE's public EOD archive is temporarily unavailable."""
    result = _get(f"/v8/finance/chart/{yahoo_symbol}", {"range": "1y", "interval": "1d"}, 8)
    chart = (result.get("chart") or {}).get("result") or []
    if not chart:
        raise ValueError("Yahoo returned no fallback indicator history")
    quote = (chart[0].get("indicators") or {}).get("quote", [{}])[0]
    return [value for close in (quote.get("close") or []) if (value := _finite(close)) is not None]


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


def _ema(values: list[float], period: int) -> list[Optional[float]]:
    """EMA seeded with the first full-period SMA, matching common charting tools."""
    output: list[Optional[float]] = [None] * len(values)
    if len(values) < period:
        return output
    ema = sum(values[:period]) / period
    output[period - 1] = ema
    multiplier = 2 / (period + 1)
    for index in range(period, len(values)):
        ema = (values[index] - ema) * multiplier + ema
        output[index] = ema
    return output


def _rsi(values: list[float], period: int = 14) -> list[Optional[float]]:
    """Wilder's RSI; the first reading follows one complete period of changes."""
    output: list[Optional[float]] = [None] * len(values)
    if len(values) <= period:
        return output
    gains = [max(values[index] - values[index - 1], 0) for index in range(1, len(values))]
    losses = [max(values[index - 1] - values[index], 0) for index in range(1, len(values))]
    average_gain, average_loss = sum(gains[:period]) / period, sum(losses[:period]) / period

    def value() -> float:
        if average_loss == 0:
            return 100.0 if average_gain else 50.0
        return 100 - (100 / (1 + average_gain / average_loss))

    output[period] = value()
    for index in range(period + 1, len(values)):
        average_gain = ((average_gain * (period - 1)) + gains[index - 1]) / period
        average_loss = ((average_loss * (period - 1)) + losses[index - 1]) / period
        output[index] = value()
    return output


def _macd(values: list[float], fast: int = 12, slow: int = 26, signal_period: int = 9) -> tuple[list[Optional[float]], list[Optional[float]], list[Optional[float]]]:
    fast_ema, slow_ema = _ema(values, fast), _ema(values, slow)
    macd = [fast_ema[index] - slow_ema[index] if fast_ema[index] is not None and slow_ema[index] is not None else None for index in range(len(values))]
    present = [value for value in macd if value is not None]
    signal_values = _ema(present, signal_period)
    signal: list[Optional[float]] = [None] * len(values)
    first_macd = next((index for index, value in enumerate(macd) if value is not None), len(values))
    for index, value in enumerate(signal_values):
        if value is not None and first_macd + index < len(signal):
            signal[first_macd + index] = value
    histogram = [macd[index] - signal[index] if macd[index] is not None and signal[index] is not None else None for index in range(len(values))]
    return macd, signal, histogram


def _latest(values: list[Optional[float]]) -> Optional[float]:
    return next((value for value in reversed(values) if value is not None), None)


def market_snapshot(symbol: str, exchange: str = "NSE", *, include_fundamentals: bool = False) -> dict[str, Any]:
    """Return two years of daily chart data and, when requested, fundamentals."""
    normalized_symbol = _normalize_symbol(symbol)
    yahoo_symbol = f"{normalized_symbol}.{ 'NS' if exchange.upper() == 'NSE' else 'BO' }"

    def load():
        if exchange.upper() != "NSE":
            raise ValueError("NSE EOD history is available only for NSE holdings")
        rows = _nse_eod_history(normalized_symbol, 730)
        closes = [row["close"] for row in rows]
        volumes = [row["volume"] for row in rows]
        sma20 = _sma(closes, 20)
        sma50, sma200 = _sma(closes, 50), _sma(closes, 200)
        ema12, ema26 = _ema(closes, 12), _ema(closes, 26)
        rsi = _rsi(closes)
        macd, macd_signal, macd_histogram = _macd(closes)
        for index, row in enumerate(rows):
            row["sma20"] = sma20[index]
            row["sma50"], row["sma200"] = sma50[index], sma200[index]
            row["ema12"], row["ema26"] = ema12[index], ema26[index]
            row["rsi14"] = rsi[index]
            row["macd"] = macd[index]
            row["macd_signal"] = macd_signal[index]
            row["macd_histogram"] = macd_histogram[index]
            window = closes[max(0, index - 19): index + 1]
            if len(window) == 20:
                mean = sum(window) / 20
                deviation = math.sqrt(sum((value - mean) ** 2 for value in window) / 20)
                upper, lower = mean + 2 * deviation, mean - 2 * deviation
                row["bollinger_upper"], row["bollinger_lower"] = upper, lower
                row["bollinger_bandwidth_pct"] = ((upper - lower) / mean * 100) if mean else None
            else:
                row["bollinger_upper"] = row["bollinger_lower"] = row["bollinger_bandwidth_pct"] = None
            vol_window = volumes[max(0, index - 19): index + 1]
            row["avg_volume_20d"] = sum(vol_window) / len(vol_window) if vol_window else row["volume"]
        price = rows[-1]["close"] if rows else None
        previous = rows[-2]["close"] if len(rows) > 1 else None
        latest_sma50, latest_sma200 = _latest(sma50), _latest(sma200)
        crossover = "neutral" if latest_sma50 is None or latest_sma200 is None else "bullish" if latest_sma50 > latest_sma200 else "bearish" if latest_sma50 < latest_sma200 else "neutral"
        return {"symbol": normalized_symbol, "exchange": exchange.upper(), "name": normalized_symbol,
                "price": price, "previous_close": previous,
                "day_change_pct": ((price - previous) / previous * 100) if price is not None and previous else None,
                "volume": rows[-1]["volume"] if rows else None, "currency": meta.get("currency", "INR"),
                "history": rows,
                "indicators": {"sma20": _latest(sma20), "sma50": latest_sma50, "sma200": latest_sma200,
                               "ema12": _latest(ema12), "ema26": _latest(ema26),
                               "rsi14": _latest(rsi), "macd": _latest(macd), "macd_signal": _latest(macd_signal),
                               "macd_histogram": _latest(macd_histogram), "sma_crossover": crossover},
                "source": "NSE India EOD", "as_of": datetime.now(timezone.utc).isoformat()}

    snapshot = _cached(f"snapshot:{normalized_symbol}:NSE", 6 * 60 * 60, load)
    # History views do not use valuation data. Avoid quoteSummary there: Yahoo
    # frequently rejects that endpoint without browser session cookies and the
    # extra request unnecessarily consumes the public API rate budget.
    if not include_fundamentals:
        return snapshot

    # quoteSummary provides valuation and balance sheet parameters; absence should not fail snapshot.
    try:
        summary = _get(f"/v10/finance/quoteSummary/{yahoo_symbol}", {"modules": "summaryDetail,defaultKeyStatistics,financialData"})
        modules = ((summary.get("quoteSummary") or {}).get("result") or [{}])[0]
        detail = modules.get("summaryDetail", {})
        stats = modules.get("defaultKeyStatistics", {})
        financial = modules.get("financialData", {})
        
        def _raw_val(val: Any) -> float | None:
            if isinstance(val, dict):
                return _finite(val.get("raw"))
            return _finite(val)

        snapshot = dict(snapshot)
        snapshot["pe_ratio"] = _raw_val(detail.get("trailingPE") or stats.get("trailingPE"))
        snapshot["forward_pe"] = _raw_val(detail.get("forwardPE") or stats.get("forwardPE"))
        snapshot["pb_ratio"] = _raw_val(detail.get("priceToBook") or stats.get("priceToBook"))
        snapshot["ev_ebitda"] = _raw_val(detail.get("enterpriseToEbitda") or stats.get("enterpriseToEbitda"))
        snapshot["peg_ratio"] = _raw_val(stats.get("pegRatio") or detail.get("pegRatio"))
        snapshot["price_to_sales"] = _raw_val(detail.get("priceToSalesTrailing12Months"))
        snapshot["de_ratio"] = _raw_val(stats.get("debtToEquity"))
        snapshot["fifty_two_week_high"] = _raw_val(detail.get("fiftyTwoWeekHigh"))
        snapshot["fifty_two_week_low"] = _raw_val(detail.get("fiftyTwoWeekLow"))
        
        eg = _raw_val(financial.get("earningsGrowth") or stats.get("earningsQuarterlyGrowth"))
        snapshot["earnings_growth_pct"] = eg * 100.0 if eg is not None and abs(eg) <= 10.0 else eg
    except Exception:
        snapshot = dict(snapshot)
        for field in ("pe_ratio", "forward_pe", "pb_ratio", "ev_ebitda", "peg_ratio", "price_to_sales", "de_ratio", "fifty_two_week_high", "fifty_two_week_low", "earnings_growth_pct"):
            snapshot.setdefault(field, None)
    return snapshot


def market_quote(symbol: str, exchange: str = "NSE") -> dict[str, Any]:
    """Return Yahoo's current quote plus NSE EOD-derived indicators."""
    normalized_symbol = _normalize_symbol(symbol)
    normalized_exchange = exchange.upper()
    yahoo_symbol = f"{normalized_symbol}.{ 'NS' if normalized_exchange == 'NSE' else 'BO' }"

    def load():
        result = _get(f"/v8/finance/chart/{yahoo_symbol}", {"range": "5d", "interval": "1d"}, 6)
        chart = (result.get("chart") or {}).get("result") or []
        if not chart:
            raise ValueError("Yahoo returned no quote data")
        item = chart[0]
        meta = item.get("meta", {})
        yahoo_closes = [value for close in ((item.get("indicators") or {}).get("quote", [{}])[0].get("close") or []) if (value := _finite(close)) is not None]
        price = _finite(meta.get("regularMarketPrice")) or _latest(yahoo_closes)
        previous = _finite(meta.get("previousClose")) or _finite(meta.get("chartPreviousClose"))
        indicator_source = "NSE India EOD"
        try:
            rows = _nse_eod_history(normalized_symbol, 365) if normalized_exchange == "NSE" else []
            closes = [row["close"] for row in rows]
        except Exception:
            # NSE's public archive occasionally responds with a bot-protection
            # page. Preserve the indicators with a rate-limited Yahoo fallback.
            closes = _cached(f"yahoo-indicators:{yahoo_symbol}", 6 * 60 * 60,
                             lambda: _yahoo_daily_closes(yahoo_symbol))
            indicator_source = "Yahoo Finance fallback"
        sma50, sma200 = _sma(closes, 50), _sma(closes, 200)
        macd, macd_signal, macd_histogram = _macd(closes)
        latest_sma50, latest_sma200 = _latest(sma50), _latest(sma200)
        crossover = "neutral" if latest_sma50 is None or latest_sma200 is None else "bullish" if latest_sma50 > latest_sma200 else "bearish" if latest_sma50 < latest_sma200 else "neutral"
        indicators = {"rsi14": _latest(_rsi(closes)), "sma50": latest_sma50,
                      "sma200": latest_sma200, "macd": _latest(macd),
                      "macd_signal": _latest(macd_signal), "macd_histogram": _latest(macd_histogram),
                      "sma_crossover": crossover, "source": indicator_source}
        return {"symbol": normalized_symbol, "exchange": normalized_exchange, "price": price,
                "previous_close": previous,
                "day_change_pct": ((price - previous) / previous * 100) if price is not None and previous else None,
                "currency": meta.get("currency", "INR"), "source": "Yahoo Finance (delayed)",
                "indicators": indicators,
                "as_of": datetime.now(timezone.utc).isoformat()}

    return _cached(f"quote:{yahoo_symbol}", 60, load)
