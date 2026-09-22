"""Deterministic per-holding asset technical narrative agent."""

from __future__ import annotations

from .base import AgentResult
from .technical import TechnicalAgent
from ..schemas import AssetAnalysis, AssetFinding, PortfolioState, STOCK_LEVEL_ANALYSIS_LIMIT


class AssetAgent:
    name = "asset"
    prompt = TechnicalAgent.prompt

    def run(self, state: PortfolioState, correction: str | None = None) -> AgentResult:
        detailed = len(state.enriched_holdings) <= STOCK_LEVEL_ANALYSIS_LIMIT
        if not detailed:
            return {"asset_analysis": AssetAnalysis(detailed_mode=False)}

        # Run technical logic to get rich multi-indicator narratives for asset findings
        tech_result = TechnicalAgent().run(state, correction)
        tech_analysis = tech_result.get("technical_analysis")

        asset_findings = []
        if tech_analysis and tech_analysis.findings:
            for item in tech_analysis.findings:
                asset_findings.append(
                    AssetFinding(
                        ticker=item.ticker,
                        trend=item.trend,
                        momentum=item.momentum,
                        support=item.support,
                        resistance=item.resistance,
                        narrative=item.narrative,
                    )
                )

        return {"asset_analysis": AssetAnalysis(detailed_mode=True, findings=asset_findings)}


agent = AssetAgent()
