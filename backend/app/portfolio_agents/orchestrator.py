"""Central orchestrator for agent pipeline execution and parallel analytical stages."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from typing import Sequence

from .agents import AGENTS, run
from .schemas import PortfolioState

# Default list of analytical agents that can run concurrently in parallel
ANALYTICAL_AGENTS = [
    "sector",
    "asset",
    "technical",
    "risk",
    "stock_thesis",
    "sector_thesis",
    "fundamental",
    "valuation",
    "market_context",
]

ALL_AGENTS = [
    "ingestion",
    *ANALYTICAL_AGENTS,
    "critic",
    "synthesize",
    "scenario_analysis",
    "report_generator",
]


class PortfolioOrchestrator:
    """Orchestrates agent selection, execution stages, and parallel processing.

    Stages:
    1. Ingestion: Enrich raw holdings.
    2. Parallel Analytical Stage: Execute independent analytical agents concurrently.
    3. Critic & Refinement Stage: Evaluate output quality. Re-run analytical agents with correction feedback if needed.
    4. Synthesis Stage: Synthesize cross-agent findings.
    5. Scenario Stage: Derive non-deterministic positive/base/negative scenarios.
    6. Report Generation Stage: Build executive presentation report.
    """

    def __init__(
        self,
        enabled_agents: Sequence[str] | set[str] | None = None,
        max_workers: int | None = None,
        max_retries: int = 1,
    ) -> None:
        if enabled_agents is None:
            env_config = os.getenv("ENABLED_PORTFOLIO_AGENTS")
            if env_config:
                self.enabled_agents = {name.strip() for name in env_config.split(",") if name.strip()}
            else:
                self.enabled_agents = set(ALL_AGENTS)
        else:
            self.enabled_agents = set(enabled_agents)

        self.max_workers = max_workers or min(32, (os.cpu_count() or 1) + 4)
        self.max_retries = max_retries

    def is_enabled(self, agent_name: str) -> bool:
        return agent_name in self.enabled_agents and agent_name in AGENTS

    def _run_agent(self, agent_name: str, state: PortfolioState, correction: str | None = None) -> dict[str, object]:
        if not self.is_enabled(agent_name):
            return {}
        return run(agent_name, state, correction)

    def _run_parallel_analytical_stage(
        self, state: PortfolioState, correction: str | None = None
    ) -> dict[str, object]:
        active_analytical_agents = [name for name in ANALYTICAL_AGENTS if self.is_enabled(name)]
        if not active_analytical_agents:
            return {}

        results: dict[str, object] = {}
        with ThreadPoolExecutor(max_workers=min(len(active_analytical_agents), self.max_workers)) as executor:
            future_to_agent = {
                executor.submit(run, agent_name, state, correction): agent_name
                for agent_name in active_analytical_agents
            }
            for future in as_completed(future_to_agent):
                agent_name = future_to_agent[future]
                try:
                    agent_output = future.result()
                    if agent_output:
                        results.update(agent_output)
                except Exception as exc:
                    results.setdefault("errors", [])
                    if isinstance(results["errors"], list):
                        results["errors"].append(f"Agent '{agent_name}' failed during parallel execution: {exc}")

        return results

    def run_pipeline(self, initial_state: PortfolioState) -> PortfolioState:
        """Run the full multi-stage pipeline, returning normalized PortfolioState."""
        current = initial_state.model_copy(deep=True)

        # Stage 1: Ingestion
        if self.is_enabled("ingestion"):
            ingestion_updates = self._run_agent("ingestion", current)
            current = PortfolioState.model_validate({**current.model_dump(), **ingestion_updates})

        # Stage 2: Parallel Analytical Execution
        analytical_updates = self._run_parallel_analytical_stage(current)
        current = PortfolioState.model_validate({**current.model_dump(), **analytical_updates})

        # Stage 3: Critic & Retry Loop
        if self.is_enabled("critic"):
            critic_updates = self._run_agent("critic", current)
            current = PortfolioState.model_validate({**current.model_dump(), **critic_updates})

            retry_count = 0
            while current.critic and not current.critic.passed and retry_count < self.max_retries:
                feedback = "; ".join(current.critic.issues)
                retry_count += 1
                retry_analytical_updates = self._run_parallel_analytical_stage(current, correction=feedback)
                current_dict = {
                    **current.model_dump(),
                    **retry_analytical_updates,
                    "retry_count": retry_count,
                }
                current = PortfolioState.model_validate(current_dict)

                recheck_critic = self._run_agent("critic", current)
                current = PortfolioState.model_validate({**current.model_dump(), **recheck_critic})

        # Stage 4: Synthesis Stage
        if self.is_enabled("synthesize"):
            synthesis_updates = self._run_agent("synthesize", current)
            current = PortfolioState.model_validate({**current.model_dump(), **synthesis_updates})

        # Stage 5: Scenario Analysis Stage
        if self.is_enabled("scenario_analysis"):
            scenario_updates = self._run_agent("scenario_analysis", current)
            current = PortfolioState.model_validate({**current.model_dump(), **scenario_updates})

        # Stage 6: Report Generation Stage
        if self.is_enabled("report_generator"):
            report_updates = self._run_agent("report_generator", current)
            current = PortfolioState.model_validate({**current.model_dump(), **report_updates})

        return current
