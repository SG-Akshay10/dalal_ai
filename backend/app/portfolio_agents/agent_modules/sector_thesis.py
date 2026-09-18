"""Sector-level thesis agent, using portfolio measurements and optional headlines."""

from __future__ import annotations

from app.services.ingestion import fetch_sector_news
from app.services.sarvam import SarvamStructuredOutputError, structured_completion

from .base import AgentResult
from ..schemas import PortfolioState, SectorThesis, SectorThesisFinding


class SectorThesisAgent:
    name = "sector_thesis"
    prompt = """You are the Sector Thesis Subagent for Indian equities. Use only supplied sector holdings and recent sector headlines to explain growth drivers, headwinds, and policy or geopolitical factors. Populate specific pros and cons and a detailed educational narrative. Never issue direct buy/sell instructions."""

    @staticmethod
    def fallback(sector: str, holdings: list) -> SectorThesisFinding:
        returns = [item.pnl_pct for item in holdings if item.pnl_pct is not None]
        average = sum(returns) / len(returns) if returns else None
        growth = [f"Average unrealized return across measured {sector} holdings is {average:.1f}%."] if average is not None and average >= 0 else []
        headwinds = [f"Average unrealized return across measured {sector} holdings is {average:.1f}%."] if average is not None and average < 0 else []
        narrative = f"{sector} sector summary across {len(holdings)} tracked holding(s): " + (growth[0] if growth else headwinds[0] if headwinds else "Insufficient price data to characterize recent sector performance.") + " This deterministic fallback summary was generated without live news context because the language model was unavailable; treat it as educational only, not investment advice."
        return SectorThesisFinding(sector=sector, growth_drivers=growth or ["No clear growth driver detected in available data."], headwinds=headwinds or ["No clear headwind detected in available data."], policy_geopolitical_factors=["No sector news was available to assess policy or geopolitical context."], pros=["Provides diversification exposure to a distinct industry."], cons=["Sector-specific downturns can affect all holdings in this group simultaneously."], narrative=narrative)

    def run(self, state: PortfolioState, correction: str | None = None) -> AgentResult:
        grouped: dict[str, list] = {}
        for holding in state.enriched_holdings: grouped.setdefault(holding.sector, []).append(holding)
        findings = []
        for sector, holdings in grouped.items():
            try: headlines = [item["title"] for item in fetch_sector_news(sector)][:10]
            except Exception: headlines = []
            payload = {"sector": sector, "holdings": [{"ticker": item.ticker, "pnl_pct": item.pnl_pct, "market_value": item.market_value} for item in holdings], "recent_sector_headlines": headlines}
            try: finding = structured_completion(self.prompt, payload, SectorThesisFinding, correction=correction, max_tokens=900)
            except SarvamStructuredOutputError: finding = self.fallback(sector, holdings)
            findings.append(finding)
        return {"sector_thesis": SectorThesis(findings=findings)}


agent = SectorThesisAgent()
