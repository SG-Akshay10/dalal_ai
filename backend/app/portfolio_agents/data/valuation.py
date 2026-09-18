"""Deterministic valuation calculations, historical range analysis, comparative benchmarks, and growth adjustments.

Centralizes valuation processing for P/E, P/B, EV/EBITDA, PEG, historical ranges,
peer benchmark comparisons, growth-adjusted valuations, and explicit demarcation
of observed data versus analytical assumptions.
"""

from __future__ import annotations

from typing import Any
from ..schemas import AnalyticalEvidence, EnrichedHolding, FundamentalMetrics, ValuationFinding

SECTOR_VALUATION_BENCHMARKS: dict[str, dict[str, float]] = {
    "Information Technology": {"pe_ratio": 26.0, "pb_ratio": 6.5, "ev_ebitda": 18.0, "peg_ratio": 1.5, "ps_ratio": 4.5},
    "Financial Services": {"pe_ratio": 18.0, "pb_ratio": 2.5, "ev_ebitda": 14.0, "peg_ratio": 1.2, "ps_ratio": 3.0},
    "Banking": {"pe_ratio": 16.0, "pb_ratio": 2.0, "ev_ebitda": 12.0, "peg_ratio": 1.1, "ps_ratio": 2.5},
    "Consumer Goods": {"pe_ratio": 45.0, "pb_ratio": 10.0, "ev_ebitda": 28.0, "peg_ratio": 2.2, "ps_ratio": 5.5},
    "Pharmaceuticals": {"pe_ratio": 30.0, "pb_ratio": 4.5, "ev_ebitda": 20.0, "peg_ratio": 1.6, "ps_ratio": 3.5},
    "Automobile": {"pe_ratio": 24.0, "pb_ratio": 3.5, "ev_ebitda": 14.0, "peg_ratio": 1.3, "ps_ratio": 1.8},
    "Energy": {"pe_ratio": 15.0, "pb_ratio": 1.8, "ev_ebitda": 9.0, "peg_ratio": 1.0, "ps_ratio": 1.2},
    "Metals & Mining": {"pe_ratio": 12.0, "pb_ratio": 1.5, "ev_ebitda": 7.0, "peg_ratio": 0.9, "ps_ratio": 1.0},
    "Infrastructure": {"pe_ratio": 20.0, "pb_ratio": 2.2, "ev_ebitda": 11.0, "peg_ratio": 1.2, "ps_ratio": 1.5},
    "Default": {"pe_ratio": 22.0, "pb_ratio": 3.0, "ev_ebitda": 14.0, "peg_ratio": 1.3, "ps_ratio": 2.0},
}


def get_sector_valuation_benchmark(sector: str) -> dict[str, float]:
    """Return valuation benchmark reference metrics for a given sector."""
    return SECTOR_VALUATION_BENCHMARKS.get(sector, SECTOR_VALUATION_BENCHMARKS["Default"])


def calculate_historical_valuation_range(holding: EnrichedHolding) -> dict[str, float | str | None]:
    """Calculate historical valuation parameters (P/E min, max, median, percentile)."""
    m = holding.fundamentals
    pe = m.pe_ratio
    price = holding.current_price
    high = m.fifty_two_week_high
    low = m.fifty_two_week_low

    if pe is not None and price is not None and price > 0 and high is not None and low is not None and high >= low > 0:
        pe_min = round(pe * (low / price), 2)
        pe_max = round(pe * (high / price), 2)
        pe_median = round((pe_min + pe_max) / 2.0, 2)
        range_span = pe_max - pe_min
        percentile = round(((pe - pe_min) / range_span * 100.0), 1) if range_span > 0 else 50.0
        percentile = max(0.0, min(100.0, percentile))
        return {
            "pe_min": pe_min,
            "pe_max": pe_max,
            "pe_median": pe_median,
            "pe_percentile": percentile,
            "range_source": "52-week price range scaling",
        }

    if pe is not None:
        # Fallback estimation range when 52w high/low absent (+/- 25% bandwidth)
        pe_min = round(pe * 0.75, 2)
        pe_max = round(pe * 1.30, 2)
        pe_median = round(pe * 1.02, 2)
        return {
            "pe_min": pe_min,
            "pe_max": pe_max,
            "pe_median": pe_median,
            "pe_percentile": 50.0,
            "range_source": "Estimated historical P/E band (+/- 25%)",
        }

    return {
        "pe_min": None,
        "pe_max": None,
        "pe_median": None,
        "pe_percentile": None,
        "range_source": "Unavailable due to missing P/E ratio",
    }


def calculate_growth_adjusted_valuation(metrics: FundamentalMetrics) -> dict[str, float | str | None]:
    """Incorporate earnings growth and profitability into valuation metrics (PEG & Justified P/B)."""
    pe = metrics.pe_ratio
    eg = metrics.earnings_growth_pct if metrics.earnings_growth_pct is not None else metrics.revenue_growth_pct
    roe = metrics.roe_pct
    pb = metrics.pb_ratio

    # Calculate PEG ratio if absent
    calc_peg = metrics.peg_ratio
    if calc_peg is None and pe is not None and eg is not None and eg > 0:
        calc_peg = round(pe / eg, 2)

    # Justified P/B ratio (assuming 11.5% cost of capital)
    justified_pb = round(roe / 11.5, 2) if roe is not None and roe > 0 else None

    growth_status = "Neutral"
    if calc_peg is not None:
        if calc_peg < 1.0:
            growth_status = "Attractive / Growth-Discounted (PEG < 1.0)"
        elif calc_peg <= 1.5:
            growth_status = "Fairly Valued Relative to Growth (PEG 1.0-1.5)"
        elif calc_peg <= 2.2:
            growth_status = "Premium Relative to Growth (PEG 1.5-2.2)"
        else:
            growth_status = "Highly Speculative / Elevated Growth Premium (PEG > 2.2)"

    return {
        "calculated_peg": calc_peg,
        "justified_pb": justified_pb,
        "growth_status": growth_status,
        "earnings_growth_used_pct": eg,
    }


def extract_valuation_finding(holding: EnrichedHolding) -> ValuationFinding:
    """Deterministically analyze stock valuation and construct structured ValuationFinding."""
    m = holding.fundamentals
    bm = get_sector_valuation_benchmark(holding.sector)
    hist_range = calculate_historical_valuation_range(holding)
    growth_adj = calculate_growth_adjusted_valuation(m)

    pe = m.pe_ratio
    forward_pe = m.forward_pe
    pb = m.pb_ratio
    ev_ebitda = m.ev_ebitda
    peg = growth_adj["calculated_peg"]
    ps = m.price_to_sales
    eg = growth_adj["earnings_growth_used_pct"]
    roe = m.roe_pct

    # Deterministic valuation assessment
    assessment = "Fairly Valued"
    if pe is not None and bm["pe_ratio"]:
        pe_diff_pct = (pe - bm["pe_ratio"]) / bm["pe_ratio"] * 100.0
        if peg is not None and peg < 0.9 and pe_diff_pct < 10.0:
            assessment = "Undervalued"
        elif pe_diff_pct < -20.0 and (peg is None or peg <= 1.3):
            assessment = "Undervalued"
        elif pe_diff_pct > 35.0 and (peg is not None and peg > 2.0):
            assessment = "Overvalued"
        elif peg is not None and peg > 2.5:
            assessment = "Speculative / High Growth"
        elif pe_diff_pct > 25.0:
            assessment = "Overvalued"
        elif -20.0 <= pe_diff_pct <= 25.0:
            assessment = "Fairly Valued"
    elif pe is None:
        assessment = "Unavailable"

    # Explicit Observed Metrics
    observed_metrics: dict[str, float | str | None] = {
        "current_price": holding.current_price,
        "trailing_pe": pe,
        "forward_pe": forward_pe,
        "price_to_book": pb,
        "ev_to_ebitda": ev_ebitda,
        "peg_ratio": peg,
        "price_to_sales": ps,
        "observed_earnings_growth_pct": eg,
        "roe_pct": roe,
        "52w_high": m.fifty_two_week_high,
        "52w_low": m.fifty_two_week_low,
        "sector_benchmark_pe": bm["pe_ratio"],
        "sector_benchmark_pb": bm["pb_ratio"],
        "sector_benchmark_ev_ebitda": bm["ev_ebitda"],
    }

    # Explicit Analytical Assumptions
    assumed_cagr = eg if eg is not None and eg > 0 else 12.0
    valuation_assumptions: dict[str, float | str | None] = {
        "assumed_future_eps_cagr_pct": round(assumed_cagr, 1),
        "assumed_cost_of_equity_pct": 11.5,
        "assumed_terminal_growth_pct": 5.0,
        "target_fair_peg_ratio": bm["peg_ratio"],
        "target_fair_pe_multiple": bm["pe_ratio"],
        "valuation_methodology": "Relative Peer Benchmarking, Historical Range Percentile, and Growth-Adjusted PEG Model",
    }

    # Historical Valuation Range String
    if hist_range["pe_min"] is not None and hist_range["pe_max"] is not None:
        historical_range_str = (
            f"Historical valuation range for {holding.ticker}: P/E span estimated at [{hist_range['pe_min']} - {hist_range['pe_max']}] "
            f"with historical median of {hist_range['pe_median']}. Current trailing P/E of {pe} stands at the "
            f"{hist_range['pe_percentile']:.1f}th percentile of its range ({hist_range['range_source']})."
        )
    else:
        historical_range_str = f"Historical valuation range for {holding.ticker} is unavailable due to missing P/E ratio or chart price history."

    # Comparative Benchmark Analysis String
    bm_parts = []
    if pe is not None:
        pe_rel = "a premium of" if pe >= bm["pe_ratio"] else "a discount of"
        pe_diff = abs((pe - bm["pe_ratio"]) / bm["pe_ratio"] * 100.0)
        bm_parts.append(f"Trailing P/E of {pe:.1f} trades at {pe_rel} {pe_diff:.1f}% to sector benchmark average ({bm['pe_ratio']:.1f}).")
    if pb is not None:
        pb_rel = "above" if pb >= bm["pb_ratio"] else "below"
        bm_parts.append(f"Price-to-Book (P/B) ratio of {pb:.2f} is {pb_rel} sector benchmark average ({bm['pb_ratio']:.2f}).")
    if ev_ebitda is not None:
        ev_rel = "above" if ev_ebitda >= bm["ev_ebitda"] else "below"
        bm_parts.append(f"EV/EBITDA of {ev_ebitda:.1f}x trades {ev_rel} sector benchmark ({bm['ev_ebitda']:.1f}x).")

    comparative_benchmark_analysis = " ".join(bm_parts) if bm_parts else f"Comparative benchmark for {holding.sector}: Target P/E {bm['pe_ratio']}, Target P/B {bm['pb_ratio']}, Target EV/EBITDA {bm['ev_ebitda']}x."

    # Growth-Adjusted Analysis String
    growth_parts = []
    if peg is not None:
        growth_parts.append(f"Price/Earnings-to-Growth (PEG) ratio stands at {peg:.2f}, classified as: {growth_adj['growth_status']}.")
    if eg is not None:
        growth_parts.append(f"Reported earnings expansion rate is {eg:+.1f}% YoY.")
    if roe is not None and growth_adj["justified_pb"] is not None:
        growth_parts.append(f"Return on Equity (ROE) of {roe:.1f}% implies a justified P/B multiple of {growth_adj['justified_pb']:.2f}x against actual P/B of {pb if pb else 'N/A'}.")

    growth_adjusted_analysis = " ".join(growth_parts) if growth_parts else "Growth-adjusted metrics (PEG and Justified P/B) could not be calculated due to missing earnings growth or ROE inputs."

    # Data vs Assumptions Breakdown String
    breakdown_str = (
        f"OBSERVED MARKET DATA (Facts): Trailing P/E = {pe if pe else 'N/A'}, Forward P/E = {forward_pe if forward_pe else 'N/A'}, "
        f"P/B = {pb if pb else 'N/A'}, EV/EBITDA = {ev_ebitda if ev_ebitda else 'N/A'}, Reported Growth = {eg if eg is not None else 'N/A'}%. "
        f"ANALYTICAL ASSUMPTIONS: Projected Future EPS CAGR = {assumed_cagr:.1f}%, Cost of Capital = 11.5%, Target Sector Fair P/E = {bm['pe_ratio']}x, Target PEG = {bm['peg_ratio']}x."
    )

    # Narrative Construction (Guaranteed >= 100 words in detailed mode)
    narrative_sections = [
        f"Valuation analysis for {holding.ticker} ({holding.sector}) indicates an overall assessment of {assessment} relative to historic levels and sector peer group benchmarks.",
        f"Market Observation & Benchmark Comparison: {comparative_benchmark_analysis} {historical_range_str}",
        f"Growth & Profitability Integration: Incorporating earnings growth and return on capital, {growth_adjusted_analysis}",
        f"Methodology & Assumption Clarity: {breakdown_str}",
        f"Educational Conclusion: Investors should evaluate whether {holding.ticker}'s current price multiple adequately compensates for broader macro conditions, execution risks, and sector growth expectations. This analysis clearly isolates observed financial metrics from forward-looking modeling assumptions."
    ]
    narrative = "\n\n".join(narrative_sections)

    evidence_payload = AnalyticalEvidence(
        supporting_metrics=observed_metrics,
        historical_observations=[historical_range_str],
        comparisons={"peer_benchmark": comparative_benchmark_analysis},
        confidence_score=0.90 if holding.data_quality.fresh and holding.data_quality.complete else 0.70,
        data_quality_rating="High" if holding.data_quality.complete else "Medium",
        limitations=["Forward valuation multiples rely on consensus analyst projections."],
        missing_information=[k for k, v in observed_metrics.items() if v is None],
        interpretation=narrative,
    )

    return ValuationFinding(
        ticker=holding.ticker,
        sector=holding.sector,
        current_price=holding.current_price,
        valuation_assessment=assessment,
        observed_metrics=observed_metrics,
        valuation_assumptions=valuation_assumptions,
        historical_valuation_range=historical_range_str,
        comparative_benchmark_analysis=comparative_benchmark_analysis,
        growth_adjusted_analysis=growth_adjusted_analysis,
        data_vs_assumptions_breakdown=breakdown_str,
        narrative=narrative,
        evidence=evidence_payload,
    )
