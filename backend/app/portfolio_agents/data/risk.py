"""Deterministic risk calculation engine analyzing volatility, drawdowns, leverage, liquidity, valuation, earnings risk, sector sensitivity, downside scenarios, and evidence vs. hypothetical risk separation."""

from __future__ import annotations

from typing import Any, Literal
from ..schemas import AnalyticalEvidence, EnrichedHolding, RiskFinding
from .fundamental import get_sector_benchmark


def evaluate_leverage_risk(de_ratio: float | None) -> str:
    if de_ratio is None:
        return "Debt-to-equity ratio unavailable for leverage risk measurement."
    if de_ratio > 1.5:
        return f"High leverage risk with D/E ratio of {de_ratio:.2f}x exceeding conservative threshold (0.8x)."
    if de_ratio > 0.8:
        return f"Moderate leverage risk with D/E ratio of {de_ratio:.2f}x."
    return f"Low leverage risk with conservative D/E ratio of {de_ratio:.2f}x."


def evaluate_liquidity_risk(vol_ratio: float | None, latest_vol: float | None, avg_vol: float | None) -> str:
    if vol_ratio is None or latest_vol is None:
        return "Volume ratio unavailable for liquidity evaluation."
    if vol_ratio < 0.6:
        return f"Low liquidity dry-up with recent volume trading at {vol_ratio:.2f}x 20-day average volume."
    if vol_ratio >= 1.5:
        return f"High volume expansion ({vol_ratio:.2f}x 20d avg) indicating active liquidity and institutional interest."
    return f"Normal liquidity profile trading at {vol_ratio:.2f}x 20-day average volume."


def evaluate_valuation_risk(pe_ratio: float | None, benchmark_pe: float | None) -> str:
    if pe_ratio is None or benchmark_pe is None:
        return "P/E ratio or sector benchmark P/E unavailable for valuation risk evaluation."
    if pe_ratio > benchmark_pe * 1.4 or pe_ratio > 40.0:
        return f"Elevated valuation risk with trailing P/E of {pe_ratio:.1f}x trading at a steep premium to sector benchmark ({benchmark_pe:.1f}x)."
    if pe_ratio < benchmark_pe * 0.7:
        return f"Discounted valuation with P/E of {pe_ratio:.1f}x vs sector benchmark ({benchmark_pe:.1f}x); monitor for value trap risks."
    return f"Fair valuation alignment with P/E of {pe_ratio:.1f}x near sector benchmark ({benchmark_pe:.1f}x)."


def evaluate_earnings_risk(eg_pct: float | None) -> str:
    if eg_pct is None:
        return "Earnings growth percentage unavailable for earnings risk evaluation."
    if eg_pct < 0:
        return f"Deteriorating earnings risk with net income contracting {abs(eg_pct):.1f}% year-over-year."
    if eg_pct < 5.0:
        return f"Sluggish earnings growth of {eg_pct:.1f}% YoY creating earnings disappointment risk."
    return f"Positive earnings momentum expanding {eg_pct:.1f}% YoY."


def evaluate_sector_sensitivity(sector: str) -> str:
    cyclical = {"Metals & Mining", "Automobile", "Real Estate", "Infrastructure", "Energy"}
    sensitive = {"Financial Services", "Banking", "Information Technology"}
    defensive = {"Consumer Goods", "Pharmaceuticals"}

    if sector in cyclical:
        return f"High cyclical sensitivity in {sector}; earnings and stock prices are vulnerable to commodity price shifts and economic downturns."
    if sector in sensitive:
        return f"Moderate macro sensitivity in {sector}; performance is influenced by interest rate decisions, global tech spending, and credit growth."
    if sector in defensive:
        return f"Defensive sector characteristic in {sector}; demand is relatively inelastic during broader market pullbacks."
    return f"Standard market sensitivity in {sector}."


def extract_risk_finding(holding: EnrichedHolding) -> RiskFinding:
    """Deterministically analyze multi-factor risks for a single holding."""
    t = holding.technicals
    f = holding.fundamentals
    bm = get_sector_benchmark(holding.sector)

    drawdown = t.max_drawdown_pct
    volatility = t.annualized_volatility_pct
    de_ratio = f.de_ratio
    eg_pct = f.earnings_growth_pct
    pe_ratio = f.pe_ratio
    bm_pe = bm.get("pe_ratio", 22.0)

    # Determine Severity
    is_high = (
        (drawdown is not None and drawdown <= -25.0)
        or (volatility is not None and volatility >= 35.0)
        or (de_ratio is not None and de_ratio > 1.5)
        or (eg_pct is not None and eg_pct <= -10.0)
    )
    is_med = (
        (drawdown is not None and drawdown <= -12.0)
        or (volatility is not None and volatility >= 22.0)
        or (de_ratio is not None and de_ratio > 0.8)
        or (pe_ratio is not None and pe_ratio > bm_pe * 1.3)
        or (eg_pct is not None and eg_pct < 0)
    )
    severity: Literal["Low", "Medium", "High"] = "High" if is_high else "Medium" if is_med else "Low"

    lev_risk = evaluate_leverage_risk(de_ratio)
    liq_risk = evaluate_liquidity_risk(t.volume_ratio, t.latest_volume, t.avg_volume_20d)
    val_risk = evaluate_valuation_risk(pe_ratio, bm_pe)
    earn_risk = evaluate_earnings_risk(eg_pct)
    sec_risk = evaluate_sector_sensitivity(holding.sector)

    # Separate Evidence-Backed vs Hypothetical Risks
    evidence_backed: list[str] = []
    hypothetical: list[str] = []
    downside_scenarios: list[str] = []
    disagreements: list[str] = []

    # Evidence-backed risks (grounded empirical facts)
    if drawdown is not None and drawdown <= -15.0:
        evidence_backed.append(f"Observed peak drawdown of {drawdown:.1f}% demonstrates historical downside pressure.")
    if volatility is not None and volatility >= 25.0:
        evidence_backed.append(f"Annualized price volatility of {volatility:.1f}% exceeds broad market baseline.")
    if de_ratio is not None and de_ratio > 1.0:
        evidence_backed.append(f"Debt-to-equity ratio of {de_ratio:.2f}x indicates elevated financial leverage.")
    if eg_pct is not None and eg_pct < 0:
        evidence_backed.append(f"Earnings contracted by {abs(eg_pct):.1f}% YoY in the latest reported period.")
    if pe_ratio is not None and pe_ratio > bm_pe * 1.2:
        evidence_backed.append(f"P/E ratio of {pe_ratio:.1f}x trades at a premium to sector benchmark ({bm_pe:.1f}x).")
    if not evidence_backed:
        evidence_backed.append("No major acute financial distress or severe volatility spike detected in empirical market data.")

    # Hypothetical risks (macro / external speculation)
    hypothetical.append(f"Macro interest rate increases or RBI monetary tightening could compress valuation multiples in {holding.sector}.")
    hypothetical.append("Unforeseen regulatory policy changes or raw input inflation could narrow operating profit margins.")

    # Downside scenarios & invalidation conditions
    if eg_pct is not None and eg_pct > 0:
        downside_scenarios.append(f"If revenue or earnings growth decelerates below 5%, P/E multiple compression could trigger an additional 15-20% drawdown.")
    else:
        downside_scenarios.append(f"Continued earnings contraction could result in further valuation de-rating and support level breakdown.")
    if t.support is not None:
        downside_scenarios.append(f"A breakdown below technical support at ₹{t.support:.2f} would invalidate short-term consolidation thesis.")

    # Disagreements with optimistic findings from fundamental/technical agents
    if pe_ratio is not None and pe_ratio > bm_pe * 1.3:
        disagreements.append(f"Disagrees with fundamental optimism: despite revenue growth, trailing P/E of {pe_ratio:.1f}x creates steep multiple compression risk.")
    if de_ratio is not None and de_ratio > 1.2:
        disagreements.append(f"Disagrees with technical trend alignment: high leverage (D/E {de_ratio:.2f}x) exposes the position to debt refinancing risk during market pullbacks.")
    if drawdown is not None and drawdown <= -20.0:
        disagreements.append(f"Disagrees with bullish momentum signals: severe drawdown of {drawdown:.1f}% indicates lingering institutional distribution pressure.")

    tax_obs = "A loss may warrant recordkeeping review; tax treatment depends on jurisdiction, holding period, and investor circumstances."
    stop_ref = t.support if t.support is not None else (holding.current_price * 0.90 if holding.current_price else None)
    commentary_text = "This diagnostic uses observed drawdown, volatility, leverage, and support as educational risk references rather than trade instructions."

    drawdown_str = f"{drawdown:.1f}%" if drawdown is not None else "unavailable"
    volatility_str = f"{volatility:.1f}%" if volatility is not None else "unavailable"
    price_str = f"₹{holding.current_price:.2f}" if holding.current_price is not None else "unavailable"
    stop_str = f"₹{stop_ref:.2f}" if stop_ref is not None else "unavailable"

    narrative = (
        f"{holding.ticker} ({holding.sector}) is assigned an overall risk severity rating of {severity} based on multi-factor risk diagnostics. "
        f"At a current stock price of {price_str}, the position displays an annualized volatility of {volatility_str} and a peak historical drawdown of {drawdown_str}, with technical support identified at {stop_str}. "
        f"Leverage diagnostic: {lev_risk} Liquidity diagnostic: {liq_risk} Valuation risk: {val_risk} Earnings risk: {earn_risk} Sector sensitivity: {sec_risk} "
        f"Evidence-backed empirical risks include: {'; '.join(evidence_backed)}. "
        f"Hypothetical risks and macro sensitivities include: {'; '.join(hypothetical)}. "
        f"Downside scenarios & invalidation conditions: {'; '.join(downside_scenarios)}. "
        f"Analytical disagreement flags: {'; '.join(disagreements) if disagreements else 'No major conflict with fundamental/technical alignment.'} "
        f"{tax_obs} Educational risk diagnostic analysis only; not investment advice."
    )

    evidence_payload = AnalyticalEvidence(
        supporting_metrics={
            "max_drawdown_pct": drawdown,
            "annualized_volatility_pct": volatility,
            "de_ratio": de_ratio,
            "pe_ratio": pe_ratio,
            "earnings_growth_pct": eg_pct,
            "stop_loss_reference": stop_ref,
        },
        historical_observations=evidence_backed,
        comparisons={
            "leverage_threshold": lev_risk,
            "valuation_benchmark": val_risk,
        },
        confidence_score=0.90 if holding.data_quality.fresh and holding.data_quality.complete else 0.70,
        data_quality_rating="High" if holding.data_quality.complete else "Medium",
        limitations=["Risk diagnostics evaluate historical drawdown and volatility; unmodeled macro events cannot be predicted with 100% precision."],
        missing_information=[k for k in ["max_drawdown_pct", "annualized_volatility_pct", "de_ratio", "pe_ratio", "earnings_growth_pct"] if getattr(f, k, None) is None and getattr(t, k, None) is None],
        interpretation=narrative,
    )

    return RiskFinding(
        ticker=holding.ticker,
        severity=severity,
        drawdown_pct=drawdown,
        volatility_pct=volatility,
        stop_loss_reference=stop_ref,
        tax_loss_observation=tax_obs,
        leverage_risk=lev_risk,
        liquidity_risk=liq_risk,
        valuation_risk=val_risk,
        earnings_risk=earn_risk,
        sector_sensitivity=sec_risk,
        downside_scenarios=downside_scenarios,
        evidence_backed_risks=evidence_backed,
        hypothetical_risks=hypothetical,
        agent_disagreements=disagreements,
        commentary=commentary_text,
        narrative=narrative,
        evidence=evidence_payload,
    )
