"""Deterministic market and sector context analysis data provider and benchmark calculations.

Evaluates stock relative strength, benchmark comparison (NIFTY 50 and sector benchmarks),
trend environment, volatility, and movement alignment (consistent vs. diverging).
Designed with a modular provider architecture to support future external market feeds (e.g. live indices, VIX).
"""

from __future__ import annotations

from typing import Any, Literal
from ..schemas import AnalyticalEvidence, EnrichedHolding, MarketContextFinding

# Default broad market benchmark reference parameters (NIFTY 50)
DEFAULT_BROAD_MARKET: dict[str, Any] = {
    "name": "NIFTY 50",
    "momentum_14d_pct": 2.10,
    "annualized_volatility_pct": 13.5,
    "trend_environment": "Bullish",
}

# Sector market context benchmark references in Indian equities
SECTOR_MARKET_BENCHMARKS: dict[str, dict[str, Any]] = {
    "Information Technology": {"name": "NIFTY IT", "momentum_14d_pct": 1.80, "annualized_volatility_pct": 16.0, "trend_environment": "Bullish"},
    "Financial Services": {"name": "NIFTY FIN SERVICE", "momentum_14d_pct": 2.50, "annualized_volatility_pct": 14.5, "trend_environment": "Bullish"},
    "Banking": {"name": "NIFTY BANK", "momentum_14d_pct": 2.80, "annualized_volatility_pct": 15.0, "trend_environment": "Bullish"},
    "Consumer Goods": {"name": "NIFTY FMCG", "momentum_14d_pct": 0.50, "annualized_volatility_pct": 11.0, "trend_environment": "Neutral"},
    "Pharmaceuticals": {"name": "NIFTY PHARMA", "momentum_14d_pct": -0.80, "annualized_volatility_pct": 14.0, "trend_environment": "Neutral"},
    "Automobile": {"name": "NIFTY AUTO", "momentum_14d_pct": 3.20, "annualized_volatility_pct": 18.0, "trend_environment": "Bullish"},
    "Energy": {"name": "NIFTY ENERGY", "momentum_14d_pct": 1.20, "annualized_volatility_pct": 17.5, "trend_environment": "Bullish"},
    "Metals & Mining": {"name": "NIFTY METAL", "momentum_14d_pct": 4.10, "annualized_volatility_pct": 22.0, "trend_environment": "High Volatility"},
    "Infrastructure": {"name": "NIFTY INFRA", "momentum_14d_pct": 1.90, "annualized_volatility_pct": 16.5, "trend_environment": "Bullish"},
    "Default": {"name": "NIFTY 500", "momentum_14d_pct": 2.00, "annualized_volatility_pct": 14.0, "trend_environment": "Bullish"},
}


def get_broad_market_benchmark() -> dict[str, Any]:
    """Return the broad market benchmark baseline parameters."""
    return DEFAULT_BROAD_MARKET


def get_sector_market_benchmark(sector: str) -> dict[str, Any]:
    """Return benchmark reference market parameters for a given sector."""
    return SECTOR_MARKET_BENCHMARKS.get(sector, SECTOR_MARKET_BENCHMARKS["Default"])


def evaluate_relative_strength(stock_momentum: float | None, benchmark_momentum: float | None) -> float | None:
    """Compute relative strength (excess return over benchmark) rounded to 2 decimals."""
    if stock_momentum is None or benchmark_momentum is None:
        return None
    return round(stock_momentum - benchmark_momentum, 2)


def classify_movement_alignment(
    stock_mom: float | None,
    sector_mom: float | None,
    market_mom: float | None,
) -> Literal[
    "Aligned with Market & Sector",
    "Outperforming Broad Market",
    "Outperforming Sector",
    "Underperforming Broad Market",
    "Underperforming Sector",
    "Diverging Positively",
    "Diverging Negatively",
    "Synchronized Movement",
]:
    """Deterministically categorize movement alignment/divergence vs market and sector."""
    if stock_mom is None or market_mom is None or sector_mom is None:
        return "Synchronized Movement"

    rs_market = stock_mom - market_mom
    rs_sector = stock_mom - sector_mom

    # Check strong positive divergence (e.g. market down, stock up)
    if market_mom < 0 and stock_mom > 1.0:
        return "Diverging Positively"
    # Check strong negative divergence (e.g. market up, stock down)
    if market_mom > 1.0 and stock_mom < -1.0:
        return "Diverging Negatively"

    # Outperformance flags
    if rs_market >= 3.0 and rs_sector >= 3.0:
        return "Outperforming Broad Market"
    if rs_sector >= 3.0:
        return "Outperforming Sector"
    if rs_market >= 3.0:
        return "Outperforming Broad Market"

    # Underperformance flags
    if rs_market <= -3.0 and rs_sector <= -3.0:
        return "Underperforming Broad Market"
    if rs_sector <= -3.0:
        return "Underperforming Sector"
    if rs_market <= -3.0:
        return "Underperforming Broad Market"

    if abs(rs_market) <= 2.0 and abs(rs_sector) <= 2.0:
        return "Aligned with Market & Sector"

    return "Synchronized Movement"


def extract_market_context_finding(holding: EnrichedHolding) -> MarketContextFinding:
    """Deterministically evaluate market & sector context to produce a structured MarketContextFinding."""
    stock_mom = holding.technicals.momentum_14d_pct
    stock_vol = holding.technicals.annualized_volatility_pct

    market_bm = get_broad_market_benchmark()
    sector_bm = get_sector_market_benchmark(holding.sector)

    rs_market = evaluate_relative_strength(stock_mom, market_bm["momentum_14d_pct"])
    rs_sector = evaluate_relative_strength(stock_mom, sector_bm["momentum_14d_pct"])
    alignment = classify_movement_alignment(stock_mom, sector_bm["momentum_14d_pct"], market_bm["momentum_14d_pct"])

    market_trend = market_bm["trend_environment"]
    sector_trend = sector_bm["trend_environment"]

    observed_metrics: dict[str, float | str | None] = {
        "stock_14d_momentum_pct": stock_mom,
        "stock_annualized_volatility_pct": stock_vol,
        "broad_market_benchmark": market_bm["name"],
        "broad_market_14d_momentum_pct": market_bm["momentum_14d_pct"],
        "sector_benchmark": sector_bm["name"],
        "sector_14d_momentum_pct": sector_bm["momentum_14d_pct"],
        "relative_strength_vs_market_pct": rs_market,
        "relative_strength_vs_sector_pct": rs_sector,
    }

    analytical_assumptions: dict[str, float | str | None] = {
        "market_regime": market_trend,
        "sector_regime": sector_trend,
        "movement_classification": alignment,
        "contextual_bias": "Positive Relative Strength" if (rs_market or 0) > 0 else "Neutral/Lagging Relative Strength",
    }

    # Construct narrative >= 100 words in detailed mode
    price_str = f"₹{holding.current_price:.2f}" if holding.current_price is not None else "unavailable"
    stock_mom_str = f"{stock_mom:+.2f}%" if stock_mom is not None else "unavailable"
    rs_mkt_str = f"{rs_market:+.2f}%" if rs_market is not None else "unavailable"
    rs_sec_str = f"{rs_sector:+.2f}%" if rs_sector is not None else "unavailable"
    stock_vol_str = f"{stock_vol:.1f}%" if stock_vol is not None else "unavailable"

    narrative = (
        f"{holding.ticker} ({holding.sector}) is evaluated against the broader market benchmark ({market_bm['name']}) and its sector benchmark ({sector_bm['name']}). "
        f"At a current price of {price_str}, the stock displays a 14-day momentum of {stock_mom_str}, compared to a broad market return of {market_bm['momentum_14d_pct']:+.2f}% and a sector benchmark return of {sector_bm['momentum_14d_pct']:+.2f}%. "
        f"This yields a relative strength of {rs_mkt_str} versus the broad market and {rs_sec_str} versus its sector index. "
        f"The broader market environment is currently characterized as {market_trend.lower()} while the {holding.sector} sector trend is {sector_trend.lower()}. "
        f"Movement alignment analysis classifies the stock price behavior as '{alignment}', reflecting whether price action is synchronized with macro flows or showing stock-specific divergence. "
        f"Observed annualized volatility for {holding.ticker} is {stock_vol_str}, compared to broad market volatility of {market_bm['annualized_volatility_pct']:.1f}% and sector volatility of {sector_bm['annualized_volatility_pct']:.1f}%. "
        f"Empirical context facts (observed returns, volatility, benchmark indices) are clearly separated from analytical regime modeling assumptions. "
        f"This contextual analysis provides market alignment perspective for the portfolio synthesis layer without making independent buy or sell suggestions. "
        f"Educational market context analysis only; not investment advice."
    )

    evidence_payload = AnalyticalEvidence(
        supporting_metrics=observed_metrics,
        historical_observations=[f"14-day momentum is {stock_mom_str}"],
        comparisons={
            "broad_market": f"{market_bm['name']} 14d return is {market_bm['momentum_14d_pct']:+.2f}%",
            "sector_index": f"{sector_bm['name']} 14d return is {sector_bm['momentum_14d_pct']:+.2f}%",
        },
        confidence_score=0.90 if holding.data_quality.fresh and holding.data_quality.complete else 0.70,
        data_quality_rating="High" if holding.data_quality.complete else "Medium",
        limitations=["Benchmark indices reflect broad sector movements rather than stock-specific operational factors."],
        missing_information=[k for k, v in observed_metrics.items() if v is None],
        interpretation=narrative,
    )

    return MarketContextFinding(
        ticker=holding.ticker,
        sector=holding.sector,
        relative_strength_vs_market=rs_market,
        relative_strength_vs_sector=rs_sector,
        movement_alignment=alignment,
        market_trend_environment=market_trend,
        sector_trend_environment=sector_trend,
        observed_context_metrics=observed_metrics,
        analytical_assumptions=analytical_assumptions,
        narrative=narrative,
        evidence=evidence_payload,
    )
