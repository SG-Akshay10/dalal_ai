"""Fundamental Analysis Agent evaluating financial health, earnings, margins, ROE, debt, cash flows, trends, and benchmarks."""

from __future__ import annotations

from app.services.sarvam import SarvamStructuredOutputError, structured_completion

from .base import AgentResult
from ..data import extract_fundamental_finding
from ..schemas import (
    STOCK_LEVEL_ANALYSIS_LIMIT,
    FundamentalAnalysis,
    FundamentalFinding,
    PortfolioState,
)


class FundamentalAnalysisAgent:
    name = "fundamental"
    prompt = """You are the Fundamental Analysis Subagent for an Indian equity portfolio. Using only supplied financial fundamentals, ratios, multi-period metrics, and sector benchmarks, analyze company financial health, revenue, earnings, margins, ROE, ROCE/ROA, debt, and cash flow. Identify positive developments, deteriorating metrics, financial weaknesses, and data insufficiency areas. Ground every statement in numerical evidence using educational language; never issue buy/sell advice."""

    @staticmethod
    def fallback(holding) -> FundamentalFinding:
        return extract_fundamental_finding(holding)

    def run(self, state: PortfolioState, correction: str | None = None) -> AgentResult:
        if len(state.enriched_holdings) > STOCK_LEVEL_ANALYSIS_LIMIT:
            return {
                "fundamental_analysis": FundamentalAnalysis(
                    applicable=False,
                    reason_if_not_applicable=f"Portfolio holds more than {STOCK_LEVEL_ANALYSIS_LIMIT} individual stocks; individual fundamental analysis is skipped in favor of sector-wide analysis.",
                )
            }

        findings: list[FundamentalFinding] = []
        for holding in state.enriched_holdings:
            payload = {
                "ticker": holding.ticker,
                "sector": holding.sector,
                "market_value": holding.market_value,
                "pnl_pct": holding.pnl_pct,
                "fundamentals": holding.fundamentals.model_dump(),
            }
            try:
                finding = structured_completion(self.prompt, payload, FundamentalFinding, correction=correction, max_tokens=1000)
            except SarvamStructuredOutputError:
                finding = self.fallback(holding)
            findings.append(finding)

        if not findings:
            overall_health = "Moderate"
            overall_summary = "No holdings were available for fundamental analysis."
        else:
            avg_score = sum(item.health_score for item in findings) / len(findings)
            overall_health = "Strong" if avg_score >= 75 else "Moderate" if avg_score >= 50 else "Weak" if avg_score < 40 else "Mixed"
            positive_count = sum(len(item.positive_developments) for item in findings)
            weakness_count = sum(len(item.financial_weaknesses) for item in findings)
            overall_summary = f"Portfolio average fundamental health score is {avg_score:.1f}/100 ({overall_health}). Analyzed {len(findings)} holdings: identified {positive_count} positive fundamental developments and {weakness_count} financial weaknesses/deteriorating metrics across available financial reports."

        return {
            "fundamental_analysis": FundamentalAnalysis(
                applicable=True,
                findings=findings,
                portfolio_fundamental_health=overall_health,
                overall_summary=overall_summary,
            )
        }


agent = FundamentalAnalysisAgent()
