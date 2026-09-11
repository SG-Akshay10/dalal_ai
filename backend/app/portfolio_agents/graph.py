from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.services.sarvam import SarvamStructuredOutputError
from .agents import asset_agent, critic_agent, ingestion_agent, risk_agent, sector_agent, sector_thesis_agent, stock_thesis_agent, synthesizer_agent
from .schemas import PortfolioState


class PortfolioAnalysisUnavailable(Exception):
    """The report is intentionally unavailable when Sarvam cannot validate it."""


def _model(value: dict | PortfolioState) -> PortfolioState:
    return value if isinstance(value, PortfolioState) else PortfolioState.model_validate(value)


def _ingest(state):
    return ingestion_agent(_model(state))


def _sector(state):
    return sector_agent(_model(state))


def _asset(state):
    return asset_agent(_model(state))


def _risk(state):
    return risk_agent(_model(state))


def _stock_thesis(state):
    return stock_thesis_agent(_model(state))


def _sector_thesis(state):
    return sector_thesis_agent(_model(state))


def _critic(state):
    return critic_agent(_model(state))


def _retry(state):
    model = _model(state)
    feedback = "; ".join(model.critic.issues if model.critic else [])
    # Re-run every independent analyst once with the critic feedback before rechecking.
    updated = {**sector_agent(model, feedback), **asset_agent(model, feedback), **risk_agent(model, feedback), **stock_thesis_agent(model, feedback), **sector_thesis_agent(model, feedback)}
    return {**updated, "retry_count": model.retry_count + 1}


def _synthesize(state):
    return synthesizer_agent(_model(state))


def _route_after_critic(state):
    model = _model(state)
    if model.critic and model.critic.passed:
        return "synthesize"
    return "retry" if model.retry_count < 1 else "unavailable"


def build_portfolio_graph():
    graph = StateGraph(PortfolioState)
    graph.add_node("ingestion", _ingest)
    graph.add_node("sector", _sector)
    graph.add_node("asset", _asset)
    graph.add_node("risk", _risk)
    graph.add_node("stock_thesis", _stock_thesis)
    graph.add_node("sector_thesis", _sector_thesis)
    graph.add_node("critic", _critic)
    graph.add_node("retry", _retry)
    graph.add_node("synthesize", _synthesize)
    graph.add_edge(START, "ingestion")
    graph.add_edge("ingestion", "sector")
    graph.add_edge("ingestion", "asset")
    graph.add_edge("ingestion", "risk")
    graph.add_edge("ingestion", "stock_thesis")
    graph.add_edge("ingestion", "sector_thesis")
    graph.add_edge(["sector", "asset", "risk", "stock_thesis", "sector_thesis"], "critic")
    graph.add_conditional_edges("critic", _route_after_critic, {"retry": "retry", "synthesize": "synthesize", "unavailable": END})
    graph.add_edge("retry", "critic")
    graph.add_edge("synthesize", END)
    return graph.compile()


def run_portfolio_pipeline(holdings: list[dict]) -> PortfolioState:
    try:
        initial = PortfolioState(raw_holdings=holdings)
        result = build_portfolio_graph().invoke(initial)
        final = PortfolioState.model_validate(result)
        if final.report is None or (final.critic and not final.critic.passed):
            raise PortfolioAnalysisUnavailable("Sarvam could not produce a validated portfolio report")
        return final
    except SarvamStructuredOutputError as exc:
        raise PortfolioAnalysisUnavailable(str(exc)) from exc
