"""Compatibility facade for independently implemented portfolio agents."""

from __future__ import annotations

from .agent_modules.asset import agent as asset
from .agent_modules.critic import agent as critic
from .agent_modules.fundamental import agent as fundamental
from .agent_modules.ingestion import agent as ingestion
from .agent_modules.market_context import agent as market_context
from .agent_modules.risk import agent as risk
from .agent_modules.scenario import agent as scenario_analysis
from .agent_modules.sector import agent as sector
from .agent_modules.sector_thesis import agent as sector_thesis
from .agent_modules.stock_thesis import agent as stock_thesis
from .agent_modules.synthesis import agent as synthesize
from .agent_modules.technical import agent as technical
from .agent_modules.valuation import agent as valuation
from .schemas import PortfolioState

AGENTS = {item.name: item for item in (ingestion, sector, asset, technical, risk, stock_thesis, sector_thesis, fundamental, valuation, market_context, critic, synthesize, scenario_analysis)}


def run(name: str, state: PortfolioState, correction: str | None = None) -> dict[str, object]:
    """Execute a registered agent through the common structured contract."""
    return AGENTS[name].run(state, correction)


def ingestion_agent(state: PortfolioState) -> dict[str, object]: return run("ingestion", state)
def sector_agent(state: PortfolioState, correction: str | None = None) -> dict[str, object]: return run("sector", state, correction)
def asset_agent(state: PortfolioState, correction: str | None = None) -> dict[str, object]: return run("asset", state, correction)
def technical_agent(state: PortfolioState, correction: str | None = None) -> dict[str, object]: return run("technical", state, correction)
def risk_agent(state: PortfolioState, correction: str | None = None) -> dict[str, object]: return run("risk", state, correction)
def stock_thesis_agent(state: PortfolioState, correction: str | None = None) -> dict[str, object]: return run("stock_thesis", state, correction)
def sector_thesis_agent(state: PortfolioState, correction: str | None = None) -> dict[str, object]: return run("sector_thesis", state, correction)
def fundamental_agent(state: PortfolioState, correction: str | None = None) -> dict[str, object]: return run("fundamental", state, correction)
def valuation_agent(state: PortfolioState, correction: str | None = None) -> dict[str, object]: return run("valuation", state, correction)
def market_context_agent(state: PortfolioState, correction: str | None = None) -> dict[str, object]: return run("market_context", state, correction)
def critic_agent(state: PortfolioState) -> dict[str, object]: return run("critic", state)
def synthesizer_agent(state: PortfolioState) -> dict[str, object]: return run("synthesize", state)
def scenario_analysis_agent(state: PortfolioState) -> dict[str, object]: return run("scenario_analysis", state)
