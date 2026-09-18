"""Scenario Analysis Agent — Phase 13.

Converts validated multi-agent evidence into three structured scenarios
(Positive / Base / Negative) per holding.  Runs deterministically after
the Synthesis stage with no LLM involvement, mirroring the Critic Agent's
design philosophy: all scenario conditions are derived from typed signals
already validated by prior agents.
"""

from __future__ import annotations

from .base import AgentResult
from ..data.scenario import build_scenario_analysis
from ..schemas import PortfolioState


class ScenarioAgent:
    name = "scenario_analysis"

    def run(self, state: PortfolioState, correction: str | None = None) -> AgentResult:
        """Build scenario analysis from current validated state.

        ``correction`` is accepted for interface compatibility but has no
        effect — scenarios are entirely deterministic and do not respond to
        LLM feedback cycles.
        """
        result = build_scenario_analysis(state)
        return {"scenario_analysis": result}


agent = ScenarioAgent()
