"""Deterministic multi-agent cross-synthesis logic.

Evaluates signals across Fundamental, Technical, Valuation, Market Context, and Risk modules.
Identifies signal agreements, explicit contradictions, multi-evidence convictions,
and multi-time-horizon alignment (Short/Medium/Long term).
"""

from __future__ import annotations

from typing import Any
from ..schemas import (
    ContradictionAnalysis,
    ExecutiveSynthesis,
    PortfolioState,
    SynthesisSignalAgreement,
    TimeHorizonThesis,
)


def extract_holding_signals(state: PortfolioState, ticker: str) -> dict[str, dict[str, Any]]:
    """Extract classified stance/signals across analytical dimensions for a single ticker."""
    signals: dict[str, dict[str, Any]] = {}

    # 1. Technical signal
    if state.technical_analysis and state.technical_analysis.findings:
        tf = next((item for item in state.technical_analysis.findings if item.ticker == ticker), None)
        if tf:
            direction = "Bullish" if tf.trend in ("Bullish",) else ("Bearish" if tf.trend in ("Bearish",) else "Neutral")
            signals["Technical"] = {
                "direction": direction,
                "detail": f"Trend is {tf.trend}, momentum is {tf.momentum}",
                "evidence_score": tf.evidence.confidence_score if tf.evidence else 0.8,
            }

    # 2. Fundamental signal
    if state.fundamental_analysis and state.fundamental_analysis.findings:
        ff = next((item for item in state.fundamental_analysis.findings if item.ticker == ticker), None)
        if ff:
            direction = "Bullish" if ff.health_score >= 65 else ("Bearish" if ff.health_score < 45 else "Neutral")
            signals["Fundamental"] = {
                "direction": direction,
                "detail": f"Health score is {ff.health_score:.1f}/100",
                "evidence_score": ff.evidence.confidence_score if ff.evidence else 0.8,
            }

    # 3. Valuation signal
    if state.valuation_analysis and state.valuation_analysis.findings:
        vf = next((item for item in state.valuation_analysis.findings if item.ticker == ticker), None)
        if vf:
            if vf.valuation_assessment in ("Undervalued",):
                direction = "Bullish"
            elif vf.valuation_assessment in ("Overvalued",):
                direction = "Bearish"
            else:
                direction = "Neutral"
            signals["Valuation"] = {
                "direction": direction,
                "detail": f"Valuation assessment is {vf.valuation_assessment}",
                "evidence_score": vf.evidence.confidence_score if vf.evidence else 0.8,
            }

    # 4. Market Context signal
    if state.market_context_analysis and state.market_context_analysis.findings:
        mf = next((item for item in state.market_context_analysis.findings if item.ticker == ticker), None)
        if mf:
            direction = "Bullish" if mf.relative_strength_vs_market and mf.relative_strength_vs_market > 0 else (
                "Bearish" if mf.relative_strength_vs_market and mf.relative_strength_vs_market < -3.0 else "Neutral"
            )
            signals["Market Context"] = {
                "direction": direction,
                "detail": f"Movement alignment is {mf.movement_alignment}, RS vs Market: {mf.relative_strength_vs_market}%",
                "evidence_score": mf.evidence.confidence_score if mf.evidence else 0.8,
            }

    # 5. Risk signal
    if state.risk_analysis and state.risk_analysis.findings:
        rf = next((item for item in state.risk_analysis.findings if item.ticker == ticker), None)
        if rf:
            direction = "Bearish" if rf.severity == "High" else ("Neutral" if rf.severity == "Medium" else "Bullish")
            signals["Risk"] = {
                "direction": direction,
                "detail": f"Risk severity is {rf.severity}, max drawdown reference: {rf.drawdown_pct}%",
                "evidence_score": rf.evidence.confidence_score if rf.evidence else 0.8,
            }

    return signals


def synthesize_cross_agent_findings(state: PortfolioState) -> ExecutiveSynthesis:
    """Perform deterministic cross-agent synthesis across all holdings and state dimensions."""
    agreements: list[SynthesisSignalAgreement] = []
    contradictions: list[ContradictionAnalysis] = []
    time_horizon_theses: list[TimeHorizonThesis] = []
    conviction_drivers: list[str] = []

    tickers = [h.ticker for h in state.enriched_holdings]

    for ticker in tickers:
        signals = extract_holding_signals(state, ticker)
        if not signals:
            continue

        bullish_dims = [dim for dim, data in signals.items() if data["direction"] == "Bullish"]
        bearish_dims = [dim for dim, data in signals.items() if data["direction"] == "Bearish"]
        neutral_dims = [dim for dim, data in signals.items() if data["direction"] == "Neutral"]

        # 1. Evaluate Agreements
        if len(bullish_dims) >= 2 or len(bearish_dims) >= 2:
            consensus_dir = "Bullish / Positive Alignment" if len(bullish_dims) >= len(bearish_dims) else "Bearish / Risk Alignment"
            agreeing = bullish_dims if len(bullish_dims) >= len(bearish_dims) else bearish_dims
            details = [f"{dim} ({signals[dim]['detail']})" for dim in agreeing]
            agreements.append(
                SynthesisSignalAgreement(
                    ticker=ticker,
                    agreeing_dimensions=agreeing,
                    consensus_signal=consensus_dir,
                    evidence_count=len(agreeing),
                    supporting_evidence_summary=f"Strong multi-agent consensus across {', '.join(agreeing)}: {'; '.join(details)}.",
                )
            )
            if len(agreeing) >= 3:
                conviction_drivers.append(f"{ticker}: Strong multi-dimensional confirmation across {', '.join(agreeing)}.")

        # 2. Evaluate Contradictions explicitly instead of blending/averaging
        if bullish_dims and bearish_dims:
            bull_factors = [f"{dim}: {signals[dim]['detail']}" for dim in bullish_dims]
            bear_factors = [f"{dim}: {signals[dim]['detail']}" for dim in bearish_dims]
            conflict_desc = f"Direct analytical contradiction identified: {', '.join(bullish_dims)} indicate bullish/positive indicators, whereas {', '.join(bearish_dims)} highlight bearish/elevated risk factors."
            res_narrative = (
                f"For {ticker}, short-term tactical momentum ({', '.join(bullish_dims if 'Technical' in bullish_dims else bearish_dims)}) "
                f"conflicts with structural risk/valuation considerations ({', '.join(bearish_dims if 'Technical' in bullish_dims else bullish_dims)}). "
                "Rather than averaging these signals into a vague neutral score, investors should weigh tactical entry points against fundamental or valuation risk limits."
            )
            contradictions.append(
                ContradictionAnalysis(
                    ticker=ticker,
                    dimensions_in_conflict=bullish_dims + bearish_dims,
                    conflict_description=conflict_desc,
                    bullish_case_factors=bull_factors,
                    bearish_case_factors=bear_factors,
                    resolution_narrative=res_narrative,
                )
            )

        # 3. Construct Time-Horizon distinction
        # Short-term (0-3m): Technical + Market Context
        # Medium-term (3-12m): Valuation + Sector/Market Context
        # Long-term (1-5y): Fundamental + Business Thesis / Risk
        tech_dir = signals.get("Technical", {}).get("direction", "Neutral")
        mkt_dir = signals.get("Market Context", {}).get("direction", "Neutral")
        val_dir = signals.get("Valuation", {}).get("direction", "Neutral")
        fund_dir = signals.get("Fundamental", {}).get("direction", "Neutral")
        risk_dir = signals.get("Risk", {}).get("direction", "Neutral")

        st_outlook = f"Tactical momentum is {tech_dir.lower()} with relative market strength classified as {mkt_dir.lower()}."
        mt_outlook = f"Cyclical valuation profile is {val_dir.lower()} relative to historical and sector baselines."
        lt_outlook = f"Structural fundamental health is {fund_dir.lower()} with risk level evaluated as {risk_dir.lower()}."

        if tech_dir == fund_dir == val_dir:
            alignment = "Aligned Across Horizons"
        elif tech_dir == "Bullish" and (fund_dir == "Bearish" or val_dir == "Bearish"):
            alignment = "Short-Term Bullish / Long-Term Cautious"
        elif tech_dir == "Bearish" and fund_dir == "Bullish":
            alignment = "Short-Term Bearish / Long-Term Bullish"
        else:
            alignment = "Divergent Across Horizons"

        time_horizon_theses.append(
            TimeHorizonThesis(
                ticker=ticker,
                short_term_outlook=st_outlook,
                medium_term_outlook=mt_outlook,
                long_term_outlook=lt_outlook,
                time_horizon_alignment=alignment,
            )
        )

    # General portfolio overall thesis summary construction
    total_holdings = len(tickers)
    agreed_count = len(agreements)
    conflict_count = len(contradictions)
    thesis_summary = (
        f"Cross-agent synthesis evaluated {total_holdings} holding(s) across Technical, Fundamental, Valuation, Market Context, and Risk dimensions. "
        f"Identified {agreed_count} holding(s) with multi-agent signal consensus and {conflict_count} explicit signal contradiction(s). "
        "Analytical conclusions maintain explicit separation between tactical short-term momentum and structural long-term fundamentals."
    )

    return ExecutiveSynthesis(
        overall_portfolio_thesis=thesis_summary,
        agreements=agreements,
        contradictions=contradictions,
        time_horizon_theses=time_horizon_theses,
        key_conviction_drivers=conviction_drivers,
    )
