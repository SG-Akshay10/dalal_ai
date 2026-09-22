"""Market & Sector Context Agent evaluating relative strength, benchmark performance, market trends, volatility, and movement alignment."""

from __future__ import annotations

from app.services.sarvam import SarvamStructuredOutputError, structured_completion

from .base import AgentResult
from ..data import extract_market_context_finding, get_broad_market_benchmark
from ..schemas import (
    STOCK_LEVEL_ANALYSIS_LIMIT,
    MarketContextAnalysis,
    MarketContextFinding,
    PortfolioState,
)


class MarketContextAgent:
    name = "market_context"
    prompt = """You are the dedicated Market & Sector Context Agent. Evaluate the stock relative to the broader market benchmark (NIFTY 50) and its relevant sector benchmark. Analyze benchmark performance, sector performance, relative strength, market trends, volatility, and movement alignment (consistent vs. diverging movements). Cleanly separate empirical market facts (observed returns, volatility, relative strength percentages) from analytical assumptions (regime classification, market bias). Do not independently determine final buy or sell suggestions. Provide grounded educational narratives containing at least 100 words per stock in detailed mode."""

    @staticmethod
    def fallback(holding) -> MarketContextFinding:
        return extract_market_context_finding(holding)

    def run(self, state: PortfolioState, correction: str | None = None) -> AgentResult:
        detailed = len(state.enriched_holdings) <= STOCK_LEVEL_ANALYSIS_LIMIT
        if not detailed:
            broad_bm = get_broad_market_benchmark()
            return {
                "market_context_analysis": MarketContextAnalysis(
                    applicable=False,
                    reason_if_not_applicable=f"Portfolio holds more than {STOCK_LEVEL_ANALYSIS_LIMIT} individual holdings; individual market context analysis skipped in favor of portfolio-level sector summary.",
                    broad_market_benchmark=broad_bm["name"],
                    market_regime_summary=f"Broad market ({broad_bm['name']}) environment is {broad_bm['trend_environment'].lower()} with 14-day momentum of {broad_bm['momentum_14d_pct']:+.2f}%.",
                    overall_market_context_summary=f"Portfolio contains {len(state.enriched_holdings)} holdings (> {STOCK_LEVEL_ANALYSIS_LIMIT}). Stock-level relative strength and benchmark divergence metrics omitted.",
                )
            }

        broad_bm = get_broad_market_benchmark()
        findings: list[MarketContextFinding] = []

        for holding in state.enriched_holdings:
            payload = {
                "ticker": holding.ticker,
                "sector": holding.sector,
                "current_price": holding.current_price,
                "technicals": holding.technicals.model_dump(),
                "broad_market_benchmark": broad_bm,
            }
            try:
                finding = structured_completion(
                    self.prompt,
                    payload,
                    MarketContextFinding,
                    correction=correction,
                    max_tokens=1200,
                )
                if len(finding.narrative.split()) < 100 or not finding.observed_context_metrics:
                    finding = self.fallback(holding)
            except (SarvamStructuredOutputError, Exception):
                finding = self.fallback(holding)
            findings.append(finding)

        if not findings:
            regime = "Neutral"
            summary = "No holdings were available for market context analysis."
        else:
            outperforming_count = sum(1 for f in findings if "Outperforming" in f.movement_alignment or f.movement_alignment == "Diverging Positively")
            underperforming_count = sum(1 for f in findings if "Underperforming" in f.movement_alignment or f.movement_alignment == "Diverging Negatively")
            aligned_count = sum(1 for f in findings if f.movement_alignment in ("Aligned with Market & Sector", "Synchronized Movement"))

            regime = broad_bm["trend_environment"]
            summary = (
                f"Broad market ({broad_bm['name']}) stance is {regime}. Analyzed market context for {len(findings)} holding(s): "
                f"{outperforming_count} outperforming/diverging positively, {aligned_count} aligned with market/sector, and "
                f"{underperforming_count} underperforming/lagging broad market benchmark trends."
            )

        return {
            "market_context_analysis": MarketContextAnalysis(
                applicable=True,
                broad_market_benchmark=broad_bm["name"],
                market_regime_summary=f"Broad market ({broad_bm['name']}) is {broad_bm['trend_environment'].lower()} with 14d momentum of {broad_bm['momentum_14d_pct']:+.2f}%.",
                findings=findings,
                overall_market_context_summary=summary,
            )
        }


agent = MarketContextAgent()
