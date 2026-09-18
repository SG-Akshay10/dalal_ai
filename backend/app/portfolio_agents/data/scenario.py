"""Deterministic scenario analysis construction.

Converts multi-agent evidence into three structured scenario cases
(Positive / Base / Negative) per holding.  Every condition is explicitly
tagged as *observed* (derived from current price or financial data) or
*assumption* (forward-looking inference not yet confirmed by data), fulfilling
the Phase 13 requirement to distinguish current conditions from projected ones.

No LLM is involved — scenarios are built purely from the typed signals that
prior agents have already validated and structured.
"""

from __future__ import annotations

from ..schemas import (
    PortfolioState,
    ScenarioAnalysis,
    ScenarioCase,
    ScenarioCondition,
    ScenarioFinding,
)
from .synthesis import extract_holding_signals


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _obs(description: str, dimension: str) -> ScenarioCondition:
    """Shorthand for an *observed* condition (derived from current data)."""
    return ScenarioCondition(description=description, dimension=dimension, is_observed=True)


def _asm(description: str, dimension: str) -> ScenarioCondition:
    """Shorthand for an *assumption* (forward-looking, not yet confirmed)."""
    return ScenarioCondition(description=description, dimension=dimension, is_observed=False)


def _assess_current_scenario(
    bullish_count: int, bearish_count: int, neutral_count: int, total: int
) -> str:
    """Classify the current scenario leaning from signal counts."""
    if total == 0:
        return "Highly Uncertain"
    bull_ratio = bullish_count / total
    bear_ratio = bearish_count / total
    if bull_ratio >= 0.6:
        return "Leaning Positive"
    if bear_ratio >= 0.6:
        return "Leaning Negative"
    if bull_ratio == 0 and bear_ratio == 0:
        return "Base"
    if abs(bull_ratio - bear_ratio) < 0.15:
        return "Highly Uncertain"
    if bull_ratio > bear_ratio:
        return "Leaning Positive"
    if bear_ratio > bull_ratio:
        return "Leaning Negative"
    return "Base"


# ---------------------------------------------------------------------------
# Per-ticker scenario construction
# ---------------------------------------------------------------------------

def _build_scenario_finding(
    ticker: str,
    sector: str,
    state: PortfolioState,
) -> ScenarioFinding:
    """Construct a three-scenario finding for a single holding."""
    signals = extract_holding_signals(state, ticker)

    tech = signals.get("Technical", {})
    fund = signals.get("Fundamental", {})
    val  = signals.get("Valuation", {})
    mkt  = signals.get("Market Context", {})
    risk = signals.get("Risk", {})

    tech_dir = tech.get("direction", "Neutral")
    fund_dir = fund.get("direction", "Neutral")
    val_dir  = val.get("direction",  "Neutral")
    mkt_dir  = mkt.get("direction",  "Neutral")
    risk_dir = risk.get("direction", "Neutral")

    bullish_dims = [d for d, v in signals.items() if v.get("direction") == "Bullish"]
    bearish_dims = [d for d, v in signals.items() if v.get("direction") == "Bearish"]
    neutral_dims = [d for d, v in signals.items() if v.get("direction") == "Neutral"]

    tech_detail = tech.get("detail", "")
    fund_detail = fund.get("detail", "")
    val_detail  = val.get("detail",  "")
    mkt_detail  = mkt.get("detail",  "")
    risk_detail = risk.get("detail", "")

    # -----------------------------------------------------------------------
    # POSITIVE CASE
    # -----------------------------------------------------------------------
    pos_observed: list[ScenarioCondition] = []
    pos_assumptions: list[ScenarioCondition] = []
    pos_strengthen: list[str] = []
    pos_weaken: list[str] = []
    pos_evidence: list[str] = []

    for dim in bullish_dims:
        detail = signals[dim].get("detail", "")
        pos_observed.append(_obs(f"{dim} signals are constructive: {detail}", dim))
        pos_evidence.append(dim)

    for dim in bearish_dims:
        detail = signals[dim].get("detail", "")
        pos_assumptions.append(_asm(
            f"{dim} conditions improve or reverse from current elevated risk: {detail}", dim
        ))

    for dim in neutral_dims:
        pos_assumptions.append(_asm(
            f"{dim} moves toward constructive territory from current neutral stance", dim
        ))

    if tech_dir != "Bullish":
        pos_strengthen.append("RSI stabilizes above 55 and price sustains above the 50-day SMA, confirming bullish momentum")
    if fund_dir != "Bullish":
        pos_strengthen.append("Fundamental health score rises above 65, driven by margin expansion or revenue acceleration")
    if val_dir != "Bullish":
        pos_strengthen.append("Valuation re-rating to Undervalued or Fairly Valued as earnings growth catches up to current multiples")
    if mkt_dir != "Bullish":
        pos_strengthen.append("Relative strength vs. broad market turns positive; stock outperforms benchmark over 20+ trading days")
    if risk_dir != "Bullish":
        pos_strengthen.append("Risk severity downgraded from High/Medium as drawdown stabilizes and volatility contracts below historical average")

    pos_weaken.append("Any confirmed deterioration in fundamental health score below current level")
    pos_weaken.append("Valuation assessment upgrades to Overvalued as price appreciates faster than earnings")
    if bullish_dims:
        pos_weaken.append(f"Loss of current bullish signals in {', '.join(bullish_dims)}")

    pos_thesis = (
        f"All analytical dimensions align constructively for {ticker}. "
        f"{'Current bullish signals from ' + ', '.join(bullish_dims) + ' provide observed foundation. ' if bullish_dims else ''}"
        f"Positive scenario requires {'resolution of bearish conditions in ' + ', '.join(bearish_dims) + ' ' if bearish_dims else 'maintenance of current strengths '}"
        f"and continuation of favorable market and sector environment."
    )

    positive_case = ScenarioCase(
        label="Positive",
        probability_label=(
            "More Likely" if len(bullish_dims) >= 3
            else ("Likely" if len(bullish_dims) >= 2 else "Less Likely")
        ),
        thesis_summary=pos_thesis,
        observed_conditions=pos_observed,
        assumptions=pos_assumptions,
        thesis_strengthening_changes=pos_strengthen,
        thesis_weakening_changes=pos_weaken,
        supporting_evidence_keys=pos_evidence,
    )

    # -----------------------------------------------------------------------
    # BASE CASE
    # -----------------------------------------------------------------------
    base_observed: list[ScenarioCondition] = []
    base_assumptions: list[ScenarioCondition] = []
    base_strengthen: list[str] = []
    base_weaken: list[str] = []
    base_evidence: list[str] = []

    if tech_detail:
        base_observed.append(_obs(f"Technical: {tech_detail}", "Technical"))
        base_evidence.append("Technical")
    if fund_detail:
        base_observed.append(_obs(f"Fundamental: {fund_detail}", "Fundamental"))
        base_evidence.append("Fundamental")
    if val_detail:
        base_observed.append(_obs(f"Valuation: {val_detail}", "Valuation"))
        base_evidence.append("Valuation")
    if mkt_detail:
        base_observed.append(_obs(f"Market Context: {mkt_detail}", "Market Context"))
        base_evidence.append("Market Context")
    if risk_detail:
        base_observed.append(_obs(f"Risk: {risk_detail}", "Risk"))
        base_evidence.append("Risk")

    base_assumptions.append(_asm(
        "Broad market and sector environment remain broadly stable without major regime shift", "Market Context"
    ))
    base_assumptions.append(_asm(
        "No material change in company fundamentals or earnings guidance within the analytical horizon", "Fundamental"
    ))

    if len(bullish_dims) > len(bearish_dims):
        base_strengthen.append("Continuation of current bullish signal majority without deterioration in weaker dimensions")
    elif len(bearish_dims) > len(bullish_dims):
        base_strengthen.append("Reduction in bearish signal count through operational improvement or market re-rating")
    base_strengthen.append("Confirmation of stable or improving earnings trajectory over next one to two reporting cycles")

    base_weaken.append("Simultaneous deterioration across more than two analytical dimensions")
    base_weaken.append("Significant negative surprise in earnings, regulatory environment, or sector macro factors")
    if risk_dir == "Bearish":
        base_weaken.append("Escalation of elevated risk conditions already flagged by the Risk agent")

    if len(bullish_dims) > len(bearish_dims):
        base_tone = "moderately constructive with bullish signals outnumbering bearish ones"
    elif len(bearish_dims) > len(bullish_dims):
        base_tone = "cautious with bearish signals outnumbering bullish ones"
    else:
        base_tone = "mixed with equal bullish and bearish signal counts"

    base_thesis = (
        f"The base scenario for {ticker} is {base_tone}. "
        + (
            f"Multi-agent consensus: {', '.join(bullish_dims if len(bullish_dims) >= len(bearish_dims) else bearish_dims)}. "
            if (bullish_dims or bearish_dims)
            else ""
        )
        + "Current conditions are observed and documented; forward outlook assumes macro and sector stability."
    )

    base_case = ScenarioCase(
        label="Base",
        probability_label="Likely",
        thesis_summary=base_thesis,
        observed_conditions=base_observed,
        assumptions=base_assumptions,
        thesis_strengthening_changes=base_strengthen,
        thesis_weakening_changes=base_weaken,
        supporting_evidence_keys=list(set(base_evidence)),
    )

    # -----------------------------------------------------------------------
    # NEGATIVE CASE
    # -----------------------------------------------------------------------
    neg_observed: list[ScenarioCondition] = []
    neg_assumptions: list[ScenarioCondition] = []
    neg_strengthen: list[str] = []
    neg_weaken: list[str] = []
    neg_evidence: list[str] = []

    for dim in bearish_dims:
        detail = signals[dim].get("detail", "")
        neg_observed.append(_obs(f"{dim} signals indicate risk or weakness: {detail}", dim))
        neg_evidence.append(dim)

    for dim in bullish_dims:
        detail = signals[dim].get("detail", "")
        neg_assumptions.append(_asm(
            f"{dim} favorable conditions deteriorate from current reading: {detail}", dim
        ))

    for dim in neutral_dims:
        neg_assumptions.append(_asm(
            f"{dim} deteriorates from current neutral reading toward risk territory", dim
        ))

    neg_assumptions.append(_asm(
        "Macro headwinds or sector-level pressure materializes and sustains over the analytical horizon", "Market Context"
    ))

    neg_strengthen.append("Fundamental metrics stabilize or recover before negative pressures compound")
    neg_strengthen.append("Technical levels hold key support and prevent further price deterioration")
    if val_dir == "Bullish":
        neg_strengthen.append("Undervaluation provides a valuation floor that limits downside even in risk scenario")

    neg_weaken.append("Fundamental health deteriorates further or earnings miss consensus expectations materially")
    neg_weaken.append("Loss of key technical support levels leading to accelerated downward price movement")
    if risk_dir == "Bearish":
        neg_weaken.append("Existing high-severity risk conditions escalate without corrective operational or market signals")
    neg_weaken.append("Liquidity events, margin calls, or forced selling that overwhelm normal price discovery")

    neg_thesis = (
        f"The negative scenario for {ticker} is driven by "
        f"{'observed bearish conditions in ' + ', '.join(bearish_dims) if bearish_dims else 'a reversal of currently constructive signals'}. "
        f"Materialization requires {'current bearish signals to compound' if bearish_dims else 'a deterioration of current conditions'} "
        "and assumptions about unfavorable macro or operational changes to hold."
    )

    negative_case = ScenarioCase(
        label="Negative",
        probability_label=(
            "More Likely" if len(bearish_dims) >= 3
            else ("Likely" if len(bearish_dims) >= 2 else "Less Likely")
        ),
        thesis_summary=neg_thesis,
        observed_conditions=neg_observed,
        assumptions=neg_assumptions,
        thesis_strengthening_changes=neg_strengthen,
        thesis_weakening_changes=neg_weaken,
        supporting_evidence_keys=neg_evidence,
    )

    # -----------------------------------------------------------------------
    # Inflection points (specific observable threshold crossings)
    # -----------------------------------------------------------------------
    inflection_points: list[str] = []

    tf_finding = None
    if state.technical_analysis and state.technical_analysis.findings:
        tf_finding = next((f for f in state.technical_analysis.findings if f.ticker == ticker), None)
    if tf_finding:
        if tf_finding.support is not None:
            inflection_points.append(
                f"[Technical / Negative trigger] Price breaks below observed support at {tf_finding.support:.2f} — "
                "would signal trend breakdown and shift scenario toward Negative"
            )
        if tf_finding.resistance is not None:
            inflection_points.append(
                f"[Technical / Positive trigger] Price sustains above observed resistance at {tf_finding.resistance:.2f} — "
                "would confirm breakout and shift scenario toward Positive"
            )

    ff_finding = None
    if state.fundamental_analysis and state.fundamental_analysis.findings:
        ff_finding = next((f for f in state.fundamental_analysis.findings if f.ticker == ticker), None)
    if ff_finding:
        if ff_finding.health_score < 65:
            inflection_points.append(
                f"[Fundamental / Positive trigger] Health score rises above 65 from current {ff_finding.health_score:.1f} — "
                "would upgrade fundamental stance from cautious to constructive"
            )
        else:
            inflection_points.append(
                f"[Fundamental / Negative trigger] Health score drops below 45 from current {ff_finding.health_score:.1f} — "
                "would signal deteriorating fundamentals and shift scenario toward Negative"
            )

    vf_finding = None
    if state.valuation_analysis and state.valuation_analysis.findings:
        vf_finding = next((f for f in state.valuation_analysis.findings if f.ticker == ticker), None)
    if vf_finding and vf_finding.valuation_assessment not in ("Unavailable",):
        if vf_finding.valuation_assessment == "Overvalued":
            inflection_points.append(
                "[Valuation / Negative trigger] Current Overvalued assessment persists without earnings catching up — "
                "increases downside risk on any negative catalyst"
            )
        elif vf_finding.valuation_assessment == "Undervalued":
            inflection_points.append(
                "[Valuation / Positive trigger] Current Undervalued assessment holds as earnings are confirmed — "
                "provides margin of safety and supports Positive scenario"
            )

    rf_finding = None
    if state.risk_analysis and state.risk_analysis.findings:
        rf_finding = next((f for f in state.risk_analysis.findings if f.ticker == ticker), None)
    if rf_finding and rf_finding.severity == "High":
        if rf_finding.drawdown_pct is not None:
            inflection_points.append(
                f"[Risk / Negative trigger] Drawdown of {rf_finding.drawdown_pct:.1f}% already at elevated level — "
                "further deterioration would confirm Negative scenario trajectory"
            )
        if rf_finding.stop_loss_reference is not None:
            inflection_points.append(
                f"[Risk / Boundary] Stop-loss reference at {rf_finding.stop_loss_reference:.2f} — "
                "a confirmed close below this level is an observable Negative scenario signal"
            )

    # -----------------------------------------------------------------------
    # Current assessment & observed vs. assumed breakdown
    # -----------------------------------------------------------------------
    current_assessment = _assess_current_scenario(
        len(bullish_dims), len(bearish_dims), len(neutral_dims), len(signals)
    )

    observed_summary = (
        f"Observed conditions ({len(bullish_dims)} bullish, {len(bearish_dims)} bearish, "
        f"{len(neutral_dims)} neutral across {len(signals)} analytical dimension(s)): "
        + (
            "; ".join(
                f"{d} is {signals[d]['direction'].lower()} — {signals[d]['detail']}"
                for d in signals
            )
            or "no signals available"
        )
        + "."
    )
    assumption_summary = (
        "Assumed (not yet confirmed by data): macro and sector environment stability; "
        "no material earnings guidance revision; continuation of current management strategy."
    )
    breakdown = f"{observed_summary} {assumption_summary}"

    return ScenarioFinding(
        ticker=ticker,
        sector=sector,
        positive_case=positive_case,
        base_case=base_case,
        negative_case=negative_case,
        inflection_points=inflection_points,
        current_scenario_assessment=current_assessment,
        current_vs_assumed_breakdown=breakdown,
    )


# ---------------------------------------------------------------------------
# Portfolio-level scenario analysis
# ---------------------------------------------------------------------------

def build_scenario_analysis(state: PortfolioState) -> ScenarioAnalysis:
    """Build a full portfolio scenario analysis from validated multi-agent state.

    Returns a :class:`ScenarioAnalysis` with per-holding findings and a
    portfolio-level summary of inflection points and scenario distribution.
    """
    if not state.enriched_holdings:
        return ScenarioAnalysis(
            applicable=False,
            reason_if_not_applicable="No enriched holdings available for scenario construction.",
        )

    findings: list[ScenarioFinding] = []
    for holding in state.enriched_holdings:
        finding = _build_scenario_finding(holding.ticker, holding.sector, state)
        findings.append(finding)

    leaning_positive = sum(1 for f in findings if f.current_scenario_assessment == "Leaning Positive")
    leaning_negative = sum(1 for f in findings if f.current_scenario_assessment == "Leaning Negative")
    base_count = sum(1 for f in findings if f.current_scenario_assessment == "Base")
    uncertain_count = sum(1 for f in findings if f.current_scenario_assessment == "Highly Uncertain")
    total = len(findings)

    distribution_desc = (
        f"{leaning_positive} holding(s) lean Positive, {base_count} are in Base territory, "
        f"{leaning_negative} lean Negative, and {uncertain_count} are Highly Uncertain "
        f"out of {total} holding(s) analysed."
    ) if total else "No holdings were assessed."

    portfolio_inflections: list[str] = []

    if state.market_context_analysis and state.market_context_analysis.findings:
        unique_regimes = {f.market_trend_environment for f in state.market_context_analysis.findings}
        if "Bearish" in unique_regimes or "High Volatility" in unique_regimes:
            portfolio_inflections.append(
                "[Portfolio-wide / Negative trigger] Broad market regime currently Bearish or High Volatility — "
                "a sustained reversal to Bullish regime would shift multiple holdings toward Positive scenario"
            )
        elif "Bullish" in unique_regimes:
            portfolio_inflections.append(
                "[Portfolio-wide / Positive support] Broad market trend is Bullish — "
                "a regime shift to Bearish would be the primary portfolio-level negative scenario trigger"
            )

    if state.sector_analysis and state.sector_analysis.concentration_flags:
        portfolio_inflections.append(
            "[Portfolio-wide / Risk trigger] Sector concentration flags detected: "
            + "; ".join(state.sector_analysis.concentration_flags[:3])
            + " — concentrated sector downturn would accelerate portfolio-level Negative scenario"
        )

    if state.risk_analysis and state.risk_analysis.macro_downside_scenarios:
        for scenario_text in state.risk_analysis.macro_downside_scenarios[:2]:
            portfolio_inflections.append(f"[Portfolio-wide / Macro risk] {scenario_text}")

    if leaning_positive > leaning_negative:
        portfolio_tone = "moderately constructive"
    elif leaning_negative > leaning_positive:
        portfolio_tone = "cautious with more holdings leaning toward risk scenarios"
    else:
        portfolio_tone = "balanced across scenario outcomes"

    portfolio_summary = (
        f"Portfolio scenario distribution is {portfolio_tone}. {distribution_desc} "
        "Scenarios are constructed from observed multi-agent signals and explicitly tagged assumptions — "
        "forward-looking conditions should be re-evaluated as new financial data becomes available."
    )

    return ScenarioAnalysis(
        applicable=True,
        findings=findings,
        portfolio_scenario_summary=portfolio_summary,
        portfolio_level_inflection_points=portfolio_inflections,
    )
