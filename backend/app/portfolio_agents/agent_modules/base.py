"""Shared contract for independently deployable portfolio agents."""

from __future__ import annotations

from typing import Protocol

from ..schemas import PortfolioState


AgentResult = dict[str, object]


class PortfolioAgent(Protocol):
    """A stateless agent that consumes and returns only structured state."""

    name: str

    def run(self, state: PortfolioState, correction: str | None = None) -> AgentResult:
        """Return the state fields owned by this agent, without mutating input."""
        ...
