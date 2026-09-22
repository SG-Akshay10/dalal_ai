"""Executive-report synthesis agent consuming only typed analysis outputs."""

from __future__ import annotations

from .base import AgentResult
from ..data.synthesis import synthesize_cross_agent_findings
from ..schemas import ExecutiveReport, PortfolioState


class SynthesisAgent:
    name = "synthesize"

    def run(self, state: PortfolioState, correction: str | None = None) -> AgentResult:
        synthesis_result = synthesize_cross_agent_findings(state)
        # Store synthesis_result under state.report placeholder so downstream report generator can access it
        dummy_report = state.report.model_copy() if state.report else ExecutiveReport(
            headline="Temporary Synthesis",
            executive_summary="",
            sector_commentary="",
            risk_commentary="",
            synthesis=synthesis_result,
            recommendations=["Review allocations"],
            disclaimer="Educational",
        )
        dummy_report.synthesis = synthesis_result
        return {"report": dummy_report}


agent = SynthesisAgent()
