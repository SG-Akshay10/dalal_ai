"""Deterministic criticism and adversarial validation rules for portfolio agent findings."""

from __future__ import annotations

from typing import Any
from ..schemas import CriticResult, PortfolioState, STOCK_LEVEL_ANALYSIS_LIMIT


def evaluate_critic_rules(state: PortfolioState) -> CriticResult:
    """Evaluate structural completeness, mathematical alignment, claim evidence, confidence bounds, and thesis grounding."""
    issues: list[str] = []
    unsupported_claims: list[str] = []
    contradictory_findings: list[str] = []
    calculation_issues: list[str] = []
    excessive_confidence: list[str] = []
    reasoning_errors: list[str] = []
    overlooked_risks: list[str] = []

    # 1. Structural Checks
    if not state.sector_analysis or not state.risk_analysis:
        issues.append("Required sector or risk analysis is missing")

    if len(state.enriched_holdings) <= STOCK_LEVEL_ANALYSIS_LIMIT:
        if state.risk_analysis and state.risk_analysis.applicable and any(len(item.narrative.split()) < 100 for item in state.risk_analysis.findings):
            issues.append("An individual risk analysis narrative is shorter than 100 words")
        if any(len(item.narrative.split()) < 100 for item in (state.asset_analysis.findings if state.asset_analysis else [])):
            issues.append("An individual asset narrative is shorter than 100 words")
        if state.technical_analysis and any(len(item.narrative.split()) < 100 for item in state.technical_analysis.findings):
            issues.append("An individual technical analysis narrative is shorter than 100 words")
        if state.valuation_analysis and state.valuation_analysis.applicable and any(len(item.narrative.split()) < 100 for item in state.valuation_analysis.findings):
            issues.append("An individual valuation analysis narrative is shorter than 100 words")
        if state.market_context_analysis and state.market_context_analysis.applicable and any(len(item.narrative.split()) < 100 for item in state.market_context_analysis.findings):
            issues.append("An individual market context analysis narrative is shorter than 100 words")

    if not state.sector_thesis or not state.sector_thesis.findings:
        issues.append("Sector thesis analysis is missing")
    if state.stock_thesis and state.stock_thesis.applicable and not state.stock_thesis.findings:
        issues.append("Stock thesis analysis is missing despite being applicable")
    if not state.fundamental_analysis:
        issues.append("Fundamental analysis is missing")
    if state.fundamental_analysis and state.fundamental_analysis.applicable and not state.fundamental_analysis.findings:
        issues.append("Fundamental analysis findings are missing despite being applicable")
    if not state.valuation_analysis:
        issues.append("Valuation analysis is missing")
    if state.valuation_analysis and state.valuation_analysis.applicable and not state.valuation_analysis.findings:
        issues.append("Valuation analysis findings are missing despite being applicable")
    if not state.market_context_analysis:
        issues.append("Market context analysis is missing")
    if state.market_context_analysis and state.market_context_analysis.applicable and not state.market_context_analysis.findings:
        issues.append("Market context analysis findings are missing despite being applicable")

    # 2. External Evidence Verification
    invalid_evidence = [item for item in state.evidence if not item.verified or item.quality_score < 0.7]
    if invalid_evidence:
        issues.append("External evidence failed verification or minimum quality requirements")
        unsupported_claims.append(f"{len(invalid_evidence)} external evidence record(s) failed quality or verification gates.")

    # 3. Deterministic Data & Evidence Backing Checks
    for holding in state.enriched_holdings:
        ticker = holding.ticker

        # Verify Fundamental evidence backing
        if state.fundamental_analysis and state.fundamental_analysis.findings:
            ff = next((f for f in state.fundamental_analysis.findings if f.ticker == ticker), None)
            if ff and ff.evidence:
                if ff.evidence.confidence_score > 0.85 and (not holding.data_quality.fresh or not holding.data_quality.complete):
                    excessive_confidence.append(
                        f"{ticker}: Fundamental confidence score of {ff.evidence.confidence_score:.2f} is excessively high given incomplete or stale data quality."
                    )
                if not ff.evidence.supporting_metrics:
                    unsupported_claims.append(f"{ticker}: Fundamental finding lacks supporting quantitative metrics payload.")

        # Verify Valuation evidence & math consistency
        if state.valuation_analysis and state.valuation_analysis.findings:
            vf = next((f for f in state.valuation_analysis.findings if f.ticker == ticker), None)
            if vf:
                if vf.valuation_assessment == "Undervalued" and holding.fundamentals.pe_ratio and holding.fundamentals.benchmark_pe:
                    if holding.fundamentals.pe_ratio > holding.fundamentals.benchmark_pe * 1.5 and holding.fundamentals.earnings_growth_pct and holding.fundamentals.earnings_growth_pct < 5:
                        reasoning_errors.append(
                            f"{ticker}: Classified as Undervalued despite P/E ({holding.fundamentals.pe_ratio:.1f}) substantially exceeding sector benchmark ({holding.fundamentals.benchmark_pe:.1f}) without strong earnings growth."
                        )
                if vf.evidence and vf.evidence.confidence_score > 0.90 and not vf.historical_pe_min:
                    excessive_confidence.append(
                        f"{ticker}: Valuation confidence score of {vf.evidence.confidence_score:.2f} is excessively high without historical valuation range parameters."
                    )

        # Verify Technical calculation consistency
        if state.technical_analysis and state.technical_analysis.findings:
            tf = next((f for f in state.technical_analysis.findings if f.ticker == ticker), None)
            if tf:
                if tf.trend == "Bullish" and holding.technicals.sma50 and holding.technicals.sma200:
                    if holding.technicals.sma50 < holding.technicals.sma200 * 0.90:
                        calculation_issues.append(
                            f"{ticker}: Technical trend classified as Bullish while SMA50 ({holding.technicals.sma50:.1f}) is significantly below SMA200 ({holding.technicals.sma200:.1f})."
                        )

        # Verify Risk oversight
        if state.risk_analysis and state.risk_analysis.findings:
            rf = next((f for f in state.risk_analysis.findings if f.ticker == ticker), None)
            if rf:
                if rf.severity == "Low" and holding.technicals.annualized_volatility_pct and holding.technicals.annualized_volatility_pct > 40.0:
                    overlooked_risks.append(
                        f"{ticker}: Risk severity rated Low despite high annualized volatility ({holding.technicals.annualized_volatility_pct:.1f}%)."
                    )

    # 4. Check synthesis contradiction recognition
    if state.fundamental_analysis and state.technical_analysis:
        for holding in state.enriched_holdings:
            ticker = holding.ticker
            ff = next((f for f in (state.fundamental_analysis.findings if state.fundamental_analysis.applicable else []) if f.ticker == ticker), None)
            tf = next((f for f in state.technical_analysis.findings if f.ticker == ticker), None)
            if ff and tf:
                fund_bullish = ff.health_score >= 65
                fund_bearish = ff.health_score < 45
                tech_bullish = tf.trend == "Bullish"
                tech_bearish = tf.trend == "Bearish"

                if (fund_bullish and tech_bearish) or (fund_bearish and tech_bullish):
                    contradiction_key = f"{ticker}: Fundamental signal ({'Bullish' if fund_bullish else 'Bearish'}) conflicts with Technical trend ({tf.trend})."
                    contradictory_findings.append(contradiction_key)

    # Compile total issues list
    all_criticism_details = (
        issues
        + unsupported_claims
        + contradictory_findings
        + calculation_issues
        + excessive_confidence
        + reasoning_errors
        + overlooked_risks
    )

    passed = len(all_criticism_details) == 0

    return CriticResult(
        passed=passed,
        issues=all_criticism_details,
        unsupported_claims=unsupported_claims,
        contradictory_findings=contradictory_findings,
        calculation_issues=calculation_issues,
        excessive_confidence=excessive_confidence,
        reasoning_errors=reasoning_errors,
        overlooked_risks=overlooked_risks,
    )
