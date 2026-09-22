"""Valuation Analysis Agent evaluating price multiples, historical ranges, comparative benchmarks, and growth adjustments."""

from __future__ import annotations

from app.services.sarvam import SarvamStructuredOutputError, structured_completion

from .base import AgentResult
from ..data import extract_valuation_finding
from ..schemas import (
    STOCK_LEVEL_ANALYSIS_LIMIT,
    PortfolioState,
    ValuationAnalysis,
    ValuationFinding,
)


class ValuationAgent:
    name = "valuation"
    prompt = """You are the dedicated Valuation Analysis Agent responsible for analyzing company valuation relative to historical ranges and comparative peer benchmarks. Analyze P/E, P/B, EV/EBITDA, PEG, P/S, and earnings growth. Compare current valuation levels against company historical valuation ranges rather than interpreting ratios in isolation. Incorporate earnings and profitability growth when interpreting valuation metrics. Clearly distinguish observed valuation data (empirical market facts) from analytical modeling assumptions (projected growth, cost of capital, fair PEG targets). Provide grounded educational narratives containing at least 100 words per stock in detailed mode."""

    @staticmethod
    def fallback(holding) -> ValuationFinding:
        return extract_valuation_finding(holding)

    def run(self, state: PortfolioState, correction: str | None = None) -> AgentResult:
        detailed = len(state.enriched_holdings) <= STOCK_LEVEL_ANALYSIS_LIMIT
        if not detailed:
            return {
                "valuation_analysis": ValuationAnalysis(
                    applicable=False,
                    reason_if_not_applicable=f"Portfolio holds more than {STOCK_LEVEL_ANALYSIS_LIMIT} individual holdings; individual valuation analysis skipped in favor of sector-wide analysis.",
                    portfolio_valuation_summary=f"Portfolio contains {len(state.enriched_holdings)} holdings (> {STOCK_LEVEL_ANALYSIS_LIMIT}). Individual valuation multiples and historical ranges omitted.",
                    overall_valuation_stance="Fair",
                )
            }

        findings: list[ValuationFinding] = []
        for holding in state.enriched_holdings:
            payload = {
                "ticker": holding.ticker,
                "sector": holding.sector,
                "current_price": holding.current_price,
                "fundamentals": holding.fundamentals.model_dump(),
            }
            try:
                finding = structured_completion(self.prompt, payload, ValuationFinding, correction=correction, max_tokens=1200)
                if len(finding.narrative.split()) < 100 or not finding.data_vs_assumptions_breakdown:
                    finding = self.fallback(holding)
            except (SarvamStructuredOutputError, Exception):
                finding = self.fallback(holding)
            findings.append(finding)

        if not findings:
            stance = "Fair"
            summary = "No holdings were available for valuation analysis."
        else:
            undervalued_count = sum(1 for item in findings if item.valuation_assessment == "Undervalued")
            overvalued_count = sum(1 for item in findings if item.valuation_assessment == "Overvalued")
            speculative_count = sum(1 for item in findings if item.valuation_assessment == "Speculative / High Growth")
            
            if undervalued_count > overvalued_count and undervalued_count >= len(findings) // 2:
                stance = "Attractive"
            elif overvalued_count > undervalued_count and overvalued_count >= len(findings) // 2:
                stance = "Elevated"
            elif speculative_count >= len(findings) // 2:
                stance = "Elevated"
            else:
                stance = "Fair" if (undervalued_count == overvalued_count == 0) else "Mixed"

            summary = (
                f"Portfolio valuation stance is {stance}. Analyzed {len(findings)} holdings: "
                f"{undervalued_count} undervalued, {sum(1 for item in findings if item.valuation_assessment == 'Fairly Valued')} fairly valued, "
                f"{overvalued_count} overvalued, and {speculative_count} speculative/high-growth metrics relative to historical ranges and sector benchmarks."
            )

        return {
            "valuation_analysis": ValuationAnalysis(
                applicable=True,
                findings=findings,
                portfolio_valuation_summary=summary,
                overall_valuation_stance=stance,
            )
        }


agent = ValuationAgent()
