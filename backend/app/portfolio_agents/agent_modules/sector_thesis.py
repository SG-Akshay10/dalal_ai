"""Sector-level thesis agent using only portfolio measurement evidence."""

from __future__ import annotations

from app.services.sarvam import SarvamStructuredOutputError, structured_completion

from .base import AgentResult
from ..schemas import PortfolioState, SectorThesis, SectorThesisFinding


class SectorThesisAgent:
    name = "sector_thesis"
    prompt = """You are the Sector Thesis Subagent for Indian equities. Use only supplied sector holdings, position returns, and market values. Explain observed concentration and performance characteristics, distinguishing unavailable macro, policy, geopolitical, fundamental, and news evidence rather than inventing it. Populate specific pros and cons and an educational narrative. Never issue direct buy/sell instructions."""

    @staticmethod
    def fallback(sector: str, holdings: list) -> SectorThesisFinding:
        returns = [item.pnl_pct for item in holdings if item.pnl_pct is not None]
        average = sum(returns) / len(returns) if returns else None
        growth = [f"Average unrealized return across measured {sector} holdings is {average:.1f}%."] if average is not None and average >= 0 else []
        headwinds = [f"Average unrealized return across measured {sector} holdings is {average:.1f}%."] if average is not None and average < 0 else []
        narrative = f"{sector} sector summary across {len(holdings)} tracked holding(s): " + (growth[0] if growth else headwinds[0] if headwinds else "Insufficient price data to characterize recent sector performance.") + " This deterministic fallback summary uses only portfolio measurements; macro, policy, geopolitical, fundamental, and news evidence were not supplied. Treat it as educational only, not investment advice."
        return SectorThesisFinding(sector=sector, growth_drivers=growth or ["No measured growth driver is available from portfolio data alone."], headwinds=headwinds or ["No measured headwind is available from portfolio data alone."], policy_geopolitical_factors=["No policy or geopolitical evidence was supplied for this analysis."], pros=["Provides diversification exposure to a distinct industry."], cons=["Sector-specific downturns can affect all holdings in this group simultaneously."], narrative=narrative)

    def run(self, state: PortfolioState, correction: str | None = None) -> AgentResult:
        grouped: dict[str, list] = {}
        for holding in state.enriched_holdings: grouped.setdefault(holding.sector, []).append(holding)
        findings = []
        for sector, holdings in grouped.items():
            payload = {"sector": sector, "holdings": [{"ticker": item.ticker, "pnl_pct": item.pnl_pct, "market_value": item.market_value} for item in holdings]}
            try: finding = structured_completion(self.prompt, payload, SectorThesisFinding, correction=correction, max_tokens=900)
            except SarvamStructuredOutputError: finding = self.fallback(sector, holdings)
            findings.append(finding)
        return {"sector_thesis": SectorThesis(findings=findings)}


agent = SectorThesisAgent()
