"""Deterministic fundamental calculations, benchmark references, and health scoring.

Centralizes fundamental processing for financial health, margins, profitability,
ROE, ROCE/ROA, leverage, cash flow conversion, multi-period trends, and benchmarks.
"""

from __future__ import annotations

from typing import Any
from ..schemas import EnrichedHolding, FinancialPeriod, FundamentalFinding, FundamentalMetrics

# Reference benchmarks for standard sector groupings in Indian markets
SECTOR_BENCHMARKS: dict[str, dict[str, float]] = {
    "Information Technology": {"pe_ratio": 26.0, "roe_pct": 22.0, "roce_pct": 25.0, "de_ratio": 0.1, "net_margin_pct": 16.0},
    "Financial Services": {"pe_ratio": 18.0, "roe_pct": 15.0, "roce_pct": 12.0, "de_ratio": 2.5, "net_margin_pct": 18.0},
    "Banking": {"pe_ratio": 16.0, "roe_pct": 14.0, "roce_pct": 11.0, "de_ratio": 3.0, "net_margin_pct": 16.0},
    "Consumer Goods": {"pe_ratio": 45.0, "roe_pct": 20.0, "roce_pct": 24.0, "de_ratio": 0.2, "net_margin_pct": 12.0},
    "Pharmaceuticals": {"pe_ratio": 30.0, "roe_pct": 15.0, "roce_pct": 16.0, "de_ratio": 0.3, "net_margin_pct": 14.0},
    "Automobile": {"pe_ratio": 24.0, "roe_pct": 16.0, "roce_pct": 18.0, "de_ratio": 0.4, "net_margin_pct": 8.0},
    "Energy": {"pe_ratio": 15.0, "roe_pct": 14.0, "roce_pct": 15.0, "de_ratio": 0.8, "net_margin_pct": 7.0},
    "Metals & Mining": {"pe_ratio": 12.0, "roe_pct": 12.0, "roce_pct": 14.0, "de_ratio": 0.7, "net_margin_pct": 8.0},
    "Infrastructure": {"pe_ratio": 20.0, "roe_pct": 12.0, "roce_pct": 13.0, "de_ratio": 1.2, "net_margin_pct": 6.0},
    "Default": {"pe_ratio": 22.0, "roe_pct": 15.0, "roce_pct": 15.0, "de_ratio": 0.5, "net_margin_pct": 10.0},
}


def get_sector_benchmark(sector: str) -> dict[str, float]:
    """Return benchmark reference ratios for a given sector."""
    return SECTOR_BENCHMARKS.get(sector, SECTOR_BENCHMARKS["Default"])


def calculate_fundamental_health(metrics: FundamentalMetrics) -> float:
    """Compute a deterministic health score from 0 to 100 based on core metrics.

    Weighted breakdown:
    - ROE & ROCE / ROA: up to 25 pts
    - Profit Margins: up to 25 pts
    - Leverage (Debt-to-Equity): up to 25 pts
    - Cash Flow & Growth: up to 25 pts
    """
    score = 50.0  # Base neutral score

    # ROE component (+/- 15 pts)
    if metrics.roe_pct is not None:
        if metrics.roe_pct >= 20.0:
            score += 15.0
        elif metrics.roe_pct >= 12.0:
            score += 8.0
        elif metrics.roe_pct < 5.0:
            score -= 10.0

    # Margins component (+/- 10 pts)
    if metrics.operating_margin_pct is not None or metrics.net_margin_pct is not None:
        margin = metrics.operating_margin_pct if metrics.operating_margin_pct is not None else metrics.net_margin_pct
        if margin and margin >= 15.0:
            score += 10.0
        elif margin and margin >= 8.0:
            score += 5.0
        elif margin and margin < 2.0:
            score -= 10.0

    # Leverage component (+/- 15 pts)
    if metrics.de_ratio is not None:
        if metrics.de_ratio <= 0.3:
            score += 15.0
        elif metrics.de_ratio <= 0.8:
            score += 8.0
        elif metrics.de_ratio > 2.0:
            score -= 15.0
        elif metrics.de_ratio > 1.2:
            score -= 8.0

    # Cash Flow & Growth (+/- 10 pts)
    if metrics.free_cash_flow is not None and metrics.free_cash_flow > 0:
        score += 5.0
    elif metrics.free_cash_flow is not None and metrics.free_cash_flow < 0:
        score -= 5.0

    if metrics.revenue_growth_pct is not None and metrics.revenue_growth_pct > 10.0:
        score += 5.0
    elif metrics.revenue_growth_pct is not None and metrics.revenue_growth_pct < 0:
        score -= 5.0

    return max(0.0, min(100.0, round(score, 1)))


def extract_fundamental_finding(holding: EnrichedHolding) -> FundamentalFinding:
    """Deterministically analyze fundamentals to produce a structured FundamentalFinding."""
    metrics = holding.fundamentals
    benchmark = get_sector_benchmark(holding.sector)

    health_score = calculate_fundamental_health(metrics)
    positives: list[str] = []
    deteriorating: list[str] = []
    weaknesses: list[str] = []
    insufficient: list[str] = []

    # Check key metric availability
    if metrics.roe_pct is None:
        insufficient.append("ROE / ROCE historical return metrics")
    if metrics.free_cash_flow is None and metrics.operating_cash_flow is None:
        insufficient.append("Free & operating cash flow metrics")
    if metrics.de_ratio is None:
        insufficient.append("Debt-to-Equity / leverage indicators")
    if metrics.operating_margin_pct is None and metrics.net_margin_pct is None:
        insufficient.append("Operating / net margin metrics")
    if not metrics.historical_periods:
        insufficient.append("Multi-period financial statement history")

    # Evaluate Positives
    if metrics.roe_pct is not None and metrics.roe_pct >= 15.0:
        positives.append(f"Strong Return on Equity (ROE) of {metrics.roe_pct:.1f}%, exceeding sector benchmark ({benchmark['roe_pct']:.1f}%).")
    if metrics.de_ratio is not None and metrics.de_ratio <= 0.5:
        positives.append(f"Low debt burden with Debt-to-Equity ratio of {metrics.de_ratio:.2f}, indicating conservative capital structure.")
    if metrics.operating_margin_pct is not None and metrics.operating_margin_pct >= 15.0:
        positives.append(f"Robust operating margin of {metrics.operating_margin_pct:.1f}%.")
    if metrics.free_cash_flow is not None and metrics.free_cash_flow > 0:
        positives.append(f"Positive Free Cash Flow generation ({metrics.free_cash_flow:,.2f} INR).")
    if metrics.revenue_growth_pct is not None and metrics.revenue_growth_pct > 8.0:
        positives.append(f"Revenue expanded {metrics.revenue_growth_pct:.1f}% year-over-year.")

    # Evaluate Deteriorating Metrics & Weaknesses
    if metrics.de_ratio is not None and metrics.de_ratio > 1.5:
        weaknesses.append(f"High Debt-to-Equity ratio of {metrics.de_ratio:.2f}, creating financial leverage risk.")
    if metrics.roe_pct is not None and metrics.roe_pct < 8.0:
        weaknesses.append(f"Sub-par Return on Equity (ROE) of {metrics.roe_pct:.1f}%, trailing sector benchmark ({benchmark['roe_pct']:.1f}%).")
    if metrics.net_margin_pct is not None and metrics.net_margin_pct < 5.0:
        weaknesses.append(f"Thin net profit margin of {metrics.net_margin_pct:.1f}%.")
    if metrics.free_cash_flow is not None and metrics.free_cash_flow < 0:
        deteriorating.append("Negative Free Cash Flow indicates cash burn or heavy ongoing capital investment.")
    if metrics.revenue_growth_pct is not None and metrics.revenue_growth_pct < 0:
        deteriorating.append(f"Revenue contracted by {abs(metrics.revenue_growth_pct):.1f}% over the recent period.")
    if metrics.earnings_growth_pct is not None and metrics.earnings_growth_pct < 0:
        deteriorating.append(f"Earnings contracted by {abs(metrics.earnings_growth_pct):.1f}% year-over-year.")

    # Historical trend analysis across multi-period data
    trend_lines: list[str] = []
    if metrics.historical_periods and len(metrics.historical_periods) >= 2:
        earliest = metrics.historical_periods[0]
        latest = metrics.historical_periods[-1]
        if earliest.revenue and latest.revenue:
            rev_change = ((latest.revenue - earliest.revenue) / earliest.revenue) * 100
            trend_lines.append(f"Revenue moved from {earliest.revenue:,.2f} ({earliest.period}) to {latest.revenue:,.2f} ({latest.period}), a {rev_change:+.1f}% change across {len(metrics.historical_periods)} recorded periods.")
        if earliest.net_margin_pct is not None and latest.net_margin_pct is not None:
            margin_diff = latest.net_margin_pct - earliest.net_margin_pct
            trend_lines.append(f"Net margin shifted from {earliest.net_margin_pct:.1f}% ({earliest.period}) to {latest.net_margin_pct:.1f}% ({latest.period}), a {margin_diff:+.1f}% margin change.")
    elif metrics.revenue_growth_pct is not None:
        trend_lines.append(f"Recent revenue growth stands at {metrics.revenue_growth_pct:+.1f}%.")
    else:
        trend_lines.append("Multi-period financial history is unavailable for detailed trend analysis.")

    historical_trend_analysis = " ".join(trend_lines)

    # Benchmark comparison string
    bm_lines: list[str] = []
    if metrics.pe_ratio is not None:
        val_status = "at a discount to" if metrics.pe_ratio < benchmark["pe_ratio"] else "at a premium to"
        bm_lines.append(f"P/E ratio of {metrics.pe_ratio:.1f} trades {val_status} the sector benchmark average of {benchmark['pe_ratio']:.1f}.")
    if metrics.roe_pct is not None:
        roe_status = "above" if metrics.roe_pct >= benchmark["roe_pct"] else "below"
        bm_lines.append(f"ROE of {metrics.roe_pct:.1f}% is {roe_status} the sector average of {benchmark['roe_pct']:.1f}%.")

    benchmark_comparison = " ".join(bm_lines) if bm_lines else f"Sector benchmark parameters for {holding.sector}: Target ROE {benchmark['roe_pct']}%, Target P/E {benchmark['pe_ratio']}."

    # Construct overall structured narrative
    narrative_parts = [
        f"{holding.ticker} ({holding.sector}) has a fundamental health score of {health_score}/100.",
        f"Positive highlights: {'; '.join(positives) if positives else 'No major positive developments flagged.'}",
        f"Deteriorating / Weakness flags: {'; '.join(weaknesses + deteriorating) if (weaknesses or deteriorating) else 'No severe financial weakness detected.'}",
        f"Data Insufficiency: {'; '.join(insufficient) if insufficient else 'Complete fundamental metrics available.'}",
        f"Trend & Benchmarks: {historical_trend_analysis} {benchmark_comparison}",
    ]
    narrative = " ".join(narrative_parts)

    key_metrics_dict: dict[str, float | str | None] = {
        "pe_ratio": metrics.pe_ratio,
        "pb_ratio": metrics.pb_ratio,
        "de_ratio": metrics.de_ratio,
        "roe_pct": metrics.roe_pct,
        "roce_pct": metrics.roce_pct,
        "gross_margin_pct": metrics.gross_margin_pct,
        "operating_margin_pct": metrics.operating_margin_pct,
        "net_margin_pct": metrics.net_margin_pct,
        "revenue_growth_pct": metrics.revenue_growth_pct,
        "earnings_growth_pct": metrics.earnings_growth_pct,
        "free_cash_flow": metrics.free_cash_flow,
    }

    return FundamentalFinding(
        ticker=holding.ticker,
        sector=holding.sector,
        health_score=health_score,
        key_metrics=key_metrics_dict,
        positive_developments=positives or ["No strong positive fundamental catalyst detected in available data."],
        deteriorating_metrics=deteriorating or ["No deteriorating fundamental metrics detected."],
        financial_weaknesses=weaknesses or ["No severe structural financial weaknesses identified."],
        insufficient_data_areas=insufficient,
        historical_trend_analysis=historical_trend_analysis,
        benchmark_comparison=benchmark_comparison,
        narrative=narrative,
    )
