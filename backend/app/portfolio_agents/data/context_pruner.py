"""Context pruning utilities to structure agent inputs and prevent context bloat."""

from __future__ import annotations

from typing import Any
from ..schemas import EnrichedHolding, HoldingInput, PortfolioState


def prune_holding_input(holding: HoldingInput) -> dict[str, Any]:
    """Strip bulky historical prices array while preserving essential quote metadata."""
    dump = holding.model_dump()
    # Replace full array of price bars with summary metadata
    bars_count = len(holding.historical_prices)
    dump["historical_prices"] = f"[{bars_count} bars available]"
    return dump


def prune_enriched_holding(holding: EnrichedHolding, max_history_bars: int = 10) -> dict[str, Any]:
    """Create a lightweight representation of an enriched holding for agent consumption."""
    dump = holding.model_dump()
    return dump


def get_pruned_synthesis_context(state: PortfolioState) -> dict[str, Any]:
    """Extract structured findings from analytical agents without passing raw ingestion payloads.

    This passes only agent-relevant findings to synthesis and report generation layers.
    """
    context: dict[str, Any] = {
        "holding_count": len(state.enriched_holdings),
        "tickers": [h.ticker for h in state.enriched_holdings],
        "unavailable_dimensions": state.unavailable_dimensions,
        "partial_analysis": state.partial_analysis,
    }

    if state.sector_analysis:
        context["sector_analysis"] = state.sector_analysis.model_dump()
    if state.asset_analysis:
        context["asset_analysis"] = state.asset_analysis.model_dump()
    if state.technical_analysis:
        context["technical_analysis"] = state.technical_analysis.model_dump()
    if state.risk_analysis:
        context["risk_analysis"] = state.risk_analysis.model_dump()
    if state.stock_thesis:
        context["stock_thesis"] = state.stock_thesis.model_dump()
    if state.sector_thesis:
        context["sector_thesis"] = state.sector_thesis.model_dump()
    if state.fundamental_analysis:
        context["fundamental_analysis"] = state.fundamental_analysis.model_dump()
    if state.valuation_analysis:
        context["valuation_analysis"] = state.valuation_analysis.model_dump()
    if state.market_context_analysis:
        context["market_context_analysis"] = state.market_context_analysis.model_dump()
    if state.scenario_analysis:
        context["scenario_analysis"] = state.scenario_analysis.model_dump()

    return context
