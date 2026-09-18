"""Deterministic report builder and evidence claim trace compiler for Phase 14."""

from __future__ import annotations

from typing import Any
from ..schemas import (
    ConsolidatedFinding,
    ExecutiveReport,
    ExecutiveSynthesis,
    PortfolioState,
    TraceableClaim,
    STOCK_LEVEL_ANALYSIS_LIMIT,
)



def extract_traceable_claims(state: PortfolioState) -> list[TraceableClaim]:
    """Extract claims mapped to source analytical findings and underlying empirical metrics."""
    claims: list[TraceableClaim] = []

    # 1. Fundamental claims
    if state.fundamental_analysis and state.fundamental_analysis.findings:
        for ff in state.fundamental_analysis.findings:
            if ff.health_score >= 65:
                claim_text = f"{ff.ticker} demonstrates strong fundamental financial health."
            elif ff.health_score < 45:
                claim_text = f"{ff.ticker} exhibits weak fundamental health or elevated balance sheet vulnerability."
            else:
                claim_text = f"{ff.ticker} shows moderate fundamental stability with mixed growth metrics."

            claims.append(
                TraceableClaim(
                    claim=claim_text,
                    ticker=ff.ticker,
                    dimension="Fundamental",
                    supporting_metrics=ff.key_metrics or ff.evidence.supporting_metrics,
                    supporting_observations=ff.positive_developments + ff.deteriorating_metrics,
                    confidence_score=ff.evidence.confidence_score if ff.evidence else 0.85,
                )
            )

    # 2. Technical claims
    if state.technical_analysis and state.technical_analysis.findings:
        for tf in state.technical_analysis.findings:
            claim_text = f"{tf.ticker} exhibits a {tf.trend.lower()} price trend with {tf.momentum.lower()} momentum."
            claims.append(
                TraceableClaim(
                    claim=claim_text,
                    ticker=tf.ticker,
                    dimension="Technical",
                    supporting_metrics=tf.evidence.supporting_metrics,
                    supporting_observations=tf.detected_patterns + ([tf.volatility_assessment, tf.volume_assessment] if tf.volatility_assessment else []),
                    confidence_score=tf.evidence.confidence_score if tf.evidence else 0.80,
                )
            )

    # 3. Valuation claims
    if state.valuation_analysis and state.valuation_analysis.findings:
        for vf in state.valuation_analysis.findings:
            if vf.valuation_assessment not in ("Unavailable",):
                claim_text = f"{vf.ticker} is evaluated as {vf.valuation_assessment.lower()} relative to historical and sector benchmarks."
                claims.append(
                    TraceableClaim(
                        claim=claim_text,
                        ticker=vf.ticker,
                        dimension="Valuation",
                        supporting_metrics=vf.observed_metrics,
                        supporting_observations=[vf.historical_valuation_range, vf.comparative_benchmark_analysis] if vf.historical_valuation_range else [],
                        confidence_score=vf.evidence.confidence_score if vf.evidence else 0.85,
                    )
                )

    # 4. Market Context claims
    if state.market_context_analysis and state.market_context_analysis.findings:
        for mf in state.market_context_analysis.findings:
            claim_text = f"{mf.ticker} alignment: {mf.movement_alignment} relative to broad benchmark."
            claims.append(
                TraceableClaim(
                    claim=claim_text,
                    ticker=mf.ticker,
                    dimension="Market Context",
                    supporting_metrics=mf.observed_context_metrics,
                    supporting_observations=[f"RS vs Market: {mf.relative_strength_vs_market}%" if mf.relative_strength_vs_market is not None else ""],
                    confidence_score=mf.evidence.confidence_score if mf.evidence else 0.80,
                )
            )

    # 5. Risk claims
    if state.risk_analysis and state.risk_analysis.findings:
        for rf in state.risk_analysis.findings:
            claim_text = f"{rf.ticker} risk severity is rated {rf.severity.lower()}."
            metrics: dict[str, Any] = {}
            if rf.drawdown_pct is not None:
                metrics["max_drawdown_pct"] = rf.drawdown_pct
            if rf.volatility_pct is not None:
                metrics["volatility_pct"] = rf.volatility_pct
            claims.append(
                TraceableClaim(
                    claim=claim_text,
                    ticker=rf.ticker,
                    dimension="Risk",
                    supporting_metrics=metrics,
                    supporting_observations=rf.evidence_backed_risks + rf.downside_scenarios,
                    confidence_score=rf.evidence.confidence_score if rf.evidence else 0.85,
                )
            )

    # 6. Synthesis & Scenario claims
    if state.scenario_analysis and state.scenario_analysis.findings:
        for sc in state.scenario_analysis.findings:
            claim_text = f"{sc.ticker} scenario baseline assessment is '{sc.current_scenario_assessment}'."
            claims.append(
                TraceableClaim(
                    claim=claim_text,
                    ticker=sc.ticker,
                    dimension="Scenario",
                    supporting_metrics={},
                    supporting_observations=sc.inflection_points[:2],
                    confidence_score=0.85,
                )
            )

    return claims


def build_consolidated_findings(state: PortfolioState) -> list[ConsolidatedFinding]:
    """Consolidate overlapping analytical findings per holding into unified, non-redundant profiles."""
    consolidated: list[ConsolidatedFinding] = []

    for holding in state.enriched_holdings:
        ticker = holding.ticker
        sector = holding.sector

        drivers: list[str] = []
        risks: list[str] = []
        horizon_desc = ""
        scenario_leaning = "Base"

        # Gather Fundamental drivers & risks
        if state.fundamental_analysis and state.fundamental_analysis.findings:
            ff = next((f for f in state.fundamental_analysis.findings if f.ticker == ticker), None)
            if ff:
                drivers.extend(ff.positive_developments[:2])
                risks.extend(ff.deteriorating_metrics[:2] + ff.financial_weaknesses[:1])

        # Gather Technical drivers & risks
        if state.technical_analysis and state.technical_analysis.findings:
            tf = next((f for f in state.technical_analysis.findings if f.ticker == ticker), None)
            if tf:
                drivers.append(f"Technical trend: {tf.trend} ({tf.momentum} momentum)")

        # Gather Valuation stance
        val_stance = "Fairly Valued"
        if state.valuation_analysis and state.valuation_analysis.findings:
            vf = next((f for f in state.valuation_analysis.findings if f.ticker == ticker), None)
            if vf:
                val_stance = vf.valuation_assessment

        # Gather Risk factors
        if state.risk_analysis and state.risk_analysis.findings:
            rf = next((f for f in state.risk_analysis.findings if f.ticker == ticker), None)
            if rf:
                risks.extend(rf.evidence_backed_risks[:2])

        # Gather Scenario leaning
        if state.scenario_analysis and state.scenario_analysis.findings:
            sc = next((f for f in state.scenario_analysis.findings if f.ticker == ticker), None)
            if sc:
                scenario_leaning = sc.current_scenario_assessment

        # Gather Time Horizon alignment from Synthesis
        if state.report and state.report.synthesis and state.report.synthesis.time_horizon_theses:
            th = next((item for item in state.report.synthesis.time_horizon_theses if item.ticker == ticker), None)
            if th:
                horizon_desc = th.time_horizon_alignment

        consolidated.append(
            ConsolidatedFinding(
                ticker=ticker,
                sector=sector,
                overall_stance=val_stance,
                key_drivers=list(dict.fromkeys([d for d in drivers if d])),
                primary_risks=list(dict.fromkeys([r for r in risks if r])),
                scenario_leaning=scenario_leaning,
                time_horizon_summary=horizon_desc,
            )
        )

    return consolidated


def compile_analytical_limitations(state: PortfolioState) -> list[str]:
    """Compile portfolio-wide analytical limitations, data quality warnings, unavailable dimensions, and critic findings."""
    limitations: list[str] = []

    if state.partial_analysis or state.unavailable_dimensions:
        dims = ", ".join(state.unavailable_dimensions) if state.unavailable_dimensions else "unspecified"
        limitations.append(f"Partial Analysis Warning: The following analytical dimensions were unavailable or degraded: {dims}.")

    # Check state data errors and stale quality
    for h in state.enriched_holdings:
        if not h.data_quality.fresh:
            limitations.append(f"{h.ticker}: Market data snapshot is stale (>10 min old or client-supplied).")
        if not h.data_quality.complete:
            limitations.append(f"{h.ticker}: Missing fields detected ({', '.join(h.data_quality.missing_fields)}).")

    # Check critic non-fatal issues or retried notes
    if state.critic and not state.critic.passed:
        limitations.extend(state.critic.issues)

    # Check missing sectors / high risk flags
    if state.sector_analysis and state.sector_analysis.missing_sectors:
        limitations.append(f"Sector gaps: Portfolio lacks exposure to major sectors including {', '.join(state.sector_analysis.missing_sectors[:4])}.")

    return list(dict.fromkeys(limitations))



def build_executive_report_data(
    state: PortfolioState,
    llm_narrative: str,
) -> ExecutiveReport:
    """Build the final ExecutiveReport object cleanly separating analytics from formatting."""
    detailed = len(state.enriched_holdings) <= STOCK_LEVEL_ANALYSIS_LIMIT

    # 1. Sector Commentary
    sector_text = (
        "; ".join(f"{item.sector}: {item.allocation_pct:.1f}% ({item.risk_level.lower()} risk)" for item in state.sector_analysis.findings)
        + f". {state.sector_analysis.macro_commentary}"
        if state.sector_analysis
        else "Sector analysis was unavailable."
    )

    # 2. Asset Commentary
    asset_text = (
        "\n\n".join(item.narrative for item in (state.asset_analysis.findings if detailed and state.asset_analysis else []))
        if detailed and state.asset_analysis
        else ""
    )

    # 3. Risk Commentary
    if state.risk_analysis:
        high = sum(item.severity == "High" for item in state.risk_analysis.findings)
        medium = sum(item.severity == "Medium" for item in state.risk_analysis.findings)
        draws = [item.drawdown_pct for item in state.risk_analysis.findings if item.drawdown_pct is not None]
        risk_text = (
            f"{high} holding(s) are flagged high severity and {medium} medium severity, with an overall portfolio risk level of {state.risk_analysis.portfolio_risk_level.lower()}."
            + (f" The largest observed drawdown reference is {min(draws):.1f}%." if draws else "")
            + " Diagnostics use observed drawdown, volatility, and support as educational risk references rather than trade instructions."
        )
    else:
        risk_text = "Risk diagnostics were unavailable."

    # 4. Stock Thesis Commentary
    stock_text = (
        "\n".join(f"{item.ticker} ({item.sector}) — Pros: {'; '.join(item.pros) or 'none identified'}. Cons: {'; '.join(item.cons) or 'none identified'}." for item in state.stock_thesis.findings)
        if state.stock_thesis and state.stock_thesis.applicable and state.stock_thesis.findings
        else (state.stock_thesis.reason_if_not_applicable if state.stock_thesis and not state.stock_thesis.applicable else "Individual stock thesis analysis was unavailable.")
    )

    # 5. Sector Thesis Commentary
    sector_thesis_text = (
        "\n\n".join(
            f"{item.sector} — Growth drivers: {'; '.join(item.growth_drivers) or 'none identified'}. Headwinds: {'; '.join(item.headwinds) or 'none identified'}. Policy/geopolitical factors: {'; '.join(item.policy_geopolitical_factors) or 'none identified'}. Pros: {'; '.join(item.pros) or 'none identified'}. Cons: {'; '.join(item.cons) or 'none identified'}. {item.narrative}"
            for item in state.sector_thesis.findings
        )
        if state.sector_thesis and state.sector_thesis.findings
        else "Sector thesis analysis was unavailable."
    )

    # 6. Fundamental Commentary
    fundamental_text = (
        state.fundamental_analysis.overall_summary + "\n" + "\n".join(f"{item.ticker}: {item.narrative}" for item in state.fundamental_analysis.findings)
        if state.fundamental_analysis and state.fundamental_analysis.applicable and state.fundamental_analysis.findings
        else (state.fundamental_analysis.reason_if_not_applicable if state.fundamental_analysis and not state.fundamental_analysis.applicable else "Fundamental analysis was unavailable.")
    )

    # 7. Valuation Commentary
    valuation_text = (
        state.valuation_analysis.portfolio_valuation_summary + "\n" + "\n".join(f"{item.ticker}: {item.narrative}" for item in state.valuation_analysis.findings)
        if state.valuation_analysis and state.valuation_analysis.applicable and state.valuation_analysis.findings
        else (state.valuation_analysis.reason_if_not_applicable if state.valuation_analysis and not state.valuation_analysis.applicable else "Valuation analysis was unavailable.")
    )

    # 8. Market Context Commentary
    market_context_text = (
        state.market_context_analysis.overall_market_context_summary + "\n" + "\n".join(f"{item.ticker}: {item.narrative}" for item in state.market_context_analysis.findings)
        if state.market_context_analysis and state.market_context_analysis.applicable and state.market_context_analysis.findings
        else (state.market_context_analysis.reason_if_not_applicable if state.market_context_analysis and not state.market_context_analysis.applicable else "Market context analysis was unavailable.")
    )

    # 9. Scenario Commentary
    scenario_text = (
        state.scenario_analysis.portfolio_scenario_summary + "\n" + "\n".join(f"{item.ticker}: {item.current_vs_assumed_breakdown}" for item in state.scenario_analysis.findings)
        if state.scenario_analysis and state.scenario_analysis.applicable and state.scenario_analysis.findings
        else (state.scenario_analysis.reason_if_not_applicable if state.scenario_analysis and not state.scenario_analysis.applicable else "Scenario analysis was unavailable.")
    )

    # Extract claims, consolidated findings, and limitations
    traceable_claims = extract_traceable_claims(state)
    consolidated_findings = build_consolidated_findings(state)
    limitations = compile_analytical_limitations(state)
    synthesis_obj = state.report.synthesis if (state.report and state.report.synthesis) else ExecutiveSynthesis()


    return ExecutiveReport(
        headline="Portfolio Executive Analysis",
        executive_summary=llm_narrative,
        sector_commentary=sector_text,
        asset_commentary=asset_text,
        risk_commentary=risk_text,
        stock_thesis_commentary=stock_text,
        sector_thesis_commentary=sector_thesis_text,
        fundamental_commentary=fundamental_text,
        valuation_commentary=valuation_text,
        market_context_commentary=market_context_text,
        scenario_commentary=scenario_text,
        synthesis=synthesis_obj,
        traceable_claims=traceable_claims,
        consolidated_findings=consolidated_findings,
        analytical_limitations=limitations,
        recommendations=[
            "Review concentration and position-size limits against personal investment goals.",
            "Monitor material changes in sector exposure, price volatility, and key scenario inflection points.",
        ],
        disclaimer="Educational analysis only; not investment advice.",
    )

