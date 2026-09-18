"""Structural, evidence, and analytical quality gate for portfolio agent outputs."""

from __future__ import annotations

from .base import AgentResult
from ..data import evaluate_critic_rules
from ..schemas import PortfolioState


class CriticAgent:
    name = "critic"
    prompt = """Challenge multi-agent synthesis and individual agent outputs for unsupported claims, missing evidence, contradictory findings, calculation issues, excessive confidence, and overlooked risks."""

    def run(self, state: PortfolioState, correction: str | None = None) -> AgentResult:
        critic_result = evaluate_critic_rules(state)
        return {"critic": critic_result}


agent = CriticAgent()
