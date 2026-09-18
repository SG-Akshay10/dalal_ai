"""Holding enrichment agent: prices, sector classification, and technical data."""

from __future__ import annotations

from .base import AgentResult
from ..schemas import PortfolioState
from ..tools import enrich_holding


class IngestionAgent:
    name = "ingestion"

    def run(self, state: PortfolioState, correction: str | None = None) -> AgentResult:
        return {"enriched_holdings": [enrich_holding(item) for item in state.raw_holdings]}


agent = IngestionAgent()
