"""Deterministic sector-allocation and diversification agent."""

from __future__ import annotations

from .base import AgentResult
from ..schemas import PortfolioState, SectorAnalysis, SectorFinding
from ..tools import allocation, diversification_score, missing_sectors


class SectorAgent:
    name = "sector"
    prompt = """You are the Sector Allocation Subagent for an Indian equity portfolio. Analyze only supplied figures. Identify concentration, diversification and macro sensitivities. Use educational language; never issue direct trade instructions."""

    def run(self, state: PortfolioState, correction: str | None = None) -> AgentResult:
        values, total = allocation(state.enriched_holdings)
        findings, flags = [], []
        for sector, value in sorted(values.items(), key=lambda item: item[1], reverse=True):
            pct = round(value / total * 100, 2) if total else 0
            level = "High" if pct >= 35 else "Medium" if pct >= 15 else "Low"
            if pct >= 35:
                flags.append(f"{sector} is {pct}% of measured portfolio value")
            findings.append(SectorFinding(sector=sector, allocation_pct=pct, market_value=round(value, 2), risk_level=level, commentary=f"{sector} represents {pct}% of measured portfolio value. Concentration and sector-specific macro sensitivity should be assessed against the investor's objectives."))
        return {"sector_analysis": SectorAnalysis(findings=findings, concentration_flags=flags, missing_sectors=missing_sectors(values, total), diversification_score=diversification_score(values, total), macro_commentary="Sector exposure is calculated from current measured market values; macro sensitivity varies with rates, commodity prices, currency, regulation, and economic growth.")}


agent = SectorAgent()
