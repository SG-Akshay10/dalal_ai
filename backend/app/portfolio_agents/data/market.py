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
    historical_count = len(history)
    if len(closes) < 2:
        return Technicals(
            rsi14=_finite(indicators.get("rsi14")),
            macd_histogram=_finite(indicators.get("macd_histogram")),
            crossover=indicators.get("sma_crossover", "unavailable"),
            historical_bars_count=historical_count,
        )

    last_row = history[-1] if history else {}
    returns = [closes[index] / closes[index - 1] - 1 for index in range(1, len(closes))]
    mean = sum(returns) / len(returns)
    volatility = math.sqrt(sum((item - mean) ** 2 for item in returns) / max(1, len(returns) - 1)) * math.sqrt(252) * 100
    peak = closes[0]
    drawdown = min((price / max(peak := max(peak, price), 0.000001) - 1) * 100 for price in closes)
    recent = closes[-60:] if len(closes) >= 60 else closes

    mom14 = round((closes[-1] - closes[-14]) / closes[-14] * 100, 2) if len(closes) >= 14 and closes[-14] > 0 else None
    bw_pct = _finite(last_row.get("bollinger_bandwidth_pct"))
    squeeze = bool(bw_pct is not None and bw_pct < 5.0)

    latest_vol = _finite(last_row.get("volume"))
    avg_vol_20d = _finite(last_row.get("avg_volume_20d"))
    vol_ratio = round(latest_vol / avg_vol_20d, 2) if latest_vol is not None and avg_vol_20d and avg_vol_20d > 0 else None
    vol_surge = bool(vol_ratio is not None and vol_ratio >= 1.5)

    sma20_val = _finite(last_row.get("sma20")) or _finite(indicators.get("sma20"))
    sma50_val = _finite(last_row.get("sma50")) or _finite(indicators.get("sma50"))
    sma200_val = _finite(last_row.get("sma200")) or _finite(indicators.get("sma200"))
    ema12_val = _finite(last_row.get("ema12")) or _finite(indicators.get("ema12"))
    ema26_val = _finite(last_row.get("ema26")) or _finite(indicators.get("ema26"))
    rsi14_val = _finite(last_row.get("rsi14")) if last_row.get("rsi14") is not None else _finite(indicators.get("rsi14"))
    macd_val = _finite(last_row.get("macd")) if last_row.get("macd") is not None else _finite(indicators.get("macd"))
    signal_val = _finite(last_row.get("macd_signal")) if last_row.get("macd_signal") is not None else _finite(indicators.get("macd_signal"))
    hist_val = _finite(last_row.get("macd_histogram")) if last_row.get("macd_histogram") is not None else _finite(indicators.get("macd_histogram"))

    return Technicals(
        rsi14=rsi14_val,
        sma20=sma20_val,
        sma50=sma50_val,
        sma200=sma200_val,
        ema12=ema12_val,
        ema26=ema26_val,
        macd_line=macd_val,
        macd_signal=signal_val,
        macd_histogram=hist_val,
        crossover=indicators.get("sma_crossover", "unavailable"),
        bollinger_upper=_finite(last_row.get("bollinger_upper")),
        bollinger_lower=_finite(last_row.get("bollinger_lower")),
        bollinger_bandwidth_pct=bw_pct,
        bollinger_squeeze=squeeze,
        annualized_volatility_pct=round(volatility, 2),
        momentum_14d_pct=mom14,
        avg_volume_20d=avg_vol_20d,
        latest_volume=latest_vol,
        volume_ratio=vol_ratio,
        volume_surge=vol_surge,
        support=round(min(recent), 2),
        resistance=round(max(recent), 2),
        max_drawdown_pct=round(drawdown, 2),
        historical_bars_count=historical_count,
    )


from .cache import global_data_cache


def enrich_holding(holding: HoldingInput) -> EnrichedHolding:
    cache_key = global_data_cache.make_key(
        "enrich_holding",
        holding.ticker or holding.symbol,
        holding.quantity,
        holding.buy_price,
        holding.current_price,
        holding.market_data_as_of,
        len(holding.historical_prices),
    )
    cached = global_data_cache.get(cache_key)
    if cached is not None:
        return cached

    ticker, errors = (holding.ticker or holding.symbol or "").upper(), []
    price, history, indicators, source, as_of = holding.current_price, list(holding.historical_prices), {}, "client-supplied", holding.market_data_as_of
    pe_ratio, forward_pe, pb_ratio, ev_ebitda, peg_ratio, price_to_sales, de_ratio, high_52w, low_52w, eg_pct = None, None, None, None, None, None, None, None, None, None
    if history and market_data_is_fresh(as_of):
        latest = history[-1]
        indicators = {"rsi14": latest.get("rsi14"), "macd_histogram": latest.get("macd_histogram"), "sma_crossover": "bullish" if latest.get("sma50") is not None and latest.get("sma200") is not None and float(latest["sma50"]) > float(latest["sma200"]) else "bearish" if latest.get("sma50") is not None and latest.get("sma200") is not None and float(latest["sma50"]) < float(latest["sma200"]) else "neutral"}
    else:
        source = "Yahoo Finance (delayed)"
        try:
            snapshot = market_snapshot(ticker, holding.exchange, include_fundamentals=True)
            price, history, indicators, as_of = snapshot.get("price") or price, snapshot.get("history", []), snapshot.get("indicators", {}), snapshot.get("as_of")
            pe_ratio, de_ratio = _finite(snapshot.get("pe_ratio")), _finite(snapshot.get("de_ratio"))
            forward_pe = _finite(snapshot.get("forward_pe"))
            pb_ratio = _finite(snapshot.get("pb_ratio"))
            ev_ebitda = _finite(snapshot.get("ev_ebitda"))
            peg_ratio = _finite(snapshot.get("peg_ratio"))
            price_to_sales = _finite(snapshot.get("price_to_sales"))
            high_52w = _finite(snapshot.get("fifty_two_week_high"))
            low_52w = _finite(snapshot.get("fifty_two_week_low"))
            eg_pct = _finite(snapshot.get("earnings_growth_pct"))
        except Exception as exc:
            errors.append(f"Market data unavailable: {exc}")
    missing = (["current_price"] if price is None else []) + (["historical_prices"] if len(history) < 2 else [])
    if price is None: errors.append("Current price unavailable")
    pnl = ((price - holding.buy_price) / holding.buy_price * 100) if price is not None and holding.buy_price else None
    sector = resolve_sector(ticker, holding.sector, holding.exchange)
    bm = get_sector_benchmark(sector)
    fundamentals = FundamentalMetrics(
        pe_ratio=pe_ratio,
        forward_pe=forward_pe,
        pb_ratio=pb_ratio,
        ev_ebitda=ev_ebitda,
        peg_ratio=peg_ratio,
        price_to_sales=price_to_sales,
        fifty_two_week_high=high_52w,
        fifty_two_week_low=low_52w,
        earnings_growth_pct=eg_pct,
        de_ratio=de_ratio,
        benchmark_pe=bm.get("pe_ratio"),
        benchmark_roe_pct=bm.get("roe_pct"),
    )
    result = EnrichedHolding(
        ticker=ticker, sector=sector, quantity=holding.quantity, buy_price=holding.buy_price,
        current_price=price, market_value=price * holding.quantity if price is not None else None,
        pnl_pct=round(pnl, 2) if pnl is not None else None, technicals=calculate_technicals(history, indicators),
        fundamentals=fundamentals, data_errors=errors,
        data_quality=holding_quality(source=source, as_of=as_of, errors=errors, missing_fields=missing)
    )
    global_data_cache.set(cache_key, result)
    return result
