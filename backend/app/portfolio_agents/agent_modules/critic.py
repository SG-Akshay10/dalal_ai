"""Structural quality gate for independently-produced agent outputs."""

from __future__ import annotations

from .base import AgentResult
from ..schemas import CriticResult, PortfolioState, STOCK_LEVEL_ANALYSIS_LIMIT


class CriticAgent:
    name = "critic"
    prompt = """Reject missing sections, unsupported claims, direct buy/sell instructions, or asset/technical narratives below 100 words in detailed mode."""

    def run(self, state: PortfolioState, correction: str | None = None) -> AgentResult:
        issues = []
        if not state.sector_analysis or not state.risk_analysis:
            issues.append("Required sector or risk analysis is missing")
        if len(state.enriched_holdings) <= STOCK_LEVEL_ANALYSIS_LIMIT and state.risk_analysis and state.risk_analysis.applicable and any(len(item.narrative.split()) < 100 for item in state.risk_analysis.findings):
            issues.append("An individual risk analysis narrative is shorter than 100 words")
        if len(state.enriched_holdings) <= STOCK_LEVEL_ANALYSIS_LIMIT and any(len(item.narrative.split()) < 100 for item in (state.asset_analysis.findings if state.asset_analysis else [])):
            issues.append("An individual asset narrative is shorter than 100 words")
        if len(state.enriched_holdings) <= STOCK_LEVEL_ANALYSIS_LIMIT and state.technical_analysis and any(len(item.narrative.split()) < 100 for item in state.technical_analysis.findings):
            issues.append("An individual technical analysis narrative is shorter than 100 words")
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
        if len(state.enriched_holdings) <= STOCK_LEVEL_ANALYSIS_LIMIT and state.valuation_analysis and state.valuation_analysis.applicable and any(len(item.narrative.split()) < 100 for item in state.valuation_analysis.findings):
            issues.append("An individual valuation analysis narrative is shorter than 100 words")
        if not state.market_context_analysis:
            issues.append("Market context analysis is missing")
        if state.market_context_analysis and state.market_context_analysis.applicable and not state.market_context_analysis.findings:
            issues.append("Market context analysis findings are missing despite being applicable")
        if len(state.enriched_holdings) <= STOCK_LEVEL_ANALYSIS_LIMIT and state.market_context_analysis and state.market_context_analysis.applicable and any(len(item.narrative.split()) < 100 for item in state.market_context_analysis.findings):
            issues.append("An individual market context analysis narrative is shorter than 100 words")
        invalid_evidence = [item for item in state.evidence if not item.verified or item.quality_score < 0.7]
        if invalid_evidence:
            issues.append("External evidence failed verification or minimum quality requirements")
        return {"critic": CriticResult(passed=not issues, issues=issues)}


agent = CriticAgent()
