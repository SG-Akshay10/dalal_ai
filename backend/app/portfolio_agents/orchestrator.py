"""Central orchestrator for agent pipeline execution and parallel analytical stages."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import time
from typing import Sequence

from app.services.sarvam import SarvamStructuredOutputError
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


def _timed_run(agent_name: str, state: PortfolioState, correction: str | None = None) -> tuple[dict[str, object], float]:
    """Execute agent and measure execution latency in milliseconds."""
    t0 = time.perf_counter()
    res = run(agent_name, state, correction)
    t1 = time.perf_counter()
    return res or {}, round((t1 - t0) * 1000, 2)


class PortfolioOrchestrator:
    """Orchestrates agent selection, execution stages, parallel processing, latency measurement, and fault tolerance.

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

    def _run_agent(
        self, agent_name: str, state: PortfolioState, correction: str | None = None
    ) -> dict[str, object]:
        if not self.is_enabled(agent_name):
            return {}
        try:
            res, lat = _timed_run(agent_name, state, correction)
            res["_agent_latency"] = lat
            return res
        except Exception as exc:
            if isinstance(exc, SarvamStructuredOutputError):
                raise exc
            err_msg = f"Agent '{agent_name}' failed: {exc}"
            updates: dict[str, object] = {
                "errors": [err_msg],
                "partial_analysis": True,
                "unavailable_dimensions": [agent_name],
            }
            if agent_name == "report_generator":
                updates["report"] = None
            return updates

    def _run_parallel_analytical_stage(
        self, state: PortfolioState, correction: str | None = None
    ) -> dict[str, object]:
        active_analytical_agents = [name for name in ANALYTICAL_AGENTS if self.is_enabled(name)]
        if not active_analytical_agents:
            return {}

        results: dict[str, object] = {}
        agent_latencies: dict[str, float] = {}
        unavailable: list[str] = []
        errors: list[str] = []

        with ThreadPoolExecutor(max_workers=min(len(active_analytical_agents), self.max_workers)) as executor:
            future_to_agent = {
                executor.submit(_timed_run, agent_name, state, correction): agent_name
                for agent_name in active_analytical_agents
            }
            for future in as_completed(future_to_agent):
                agent_name = future_to_agent[future]
                try:
                    agent_output, latency_ms = future.result()
                    agent_latencies[agent_name] = latency_ms
                    if agent_output:
                        results.update(agent_output)
                except Exception as exc:
                    unavailable.append(agent_name)
                    errors.append(f"Agent '{agent_name}' failed during parallel execution: {exc}")

        if unavailable:
            results.setdefault("unavailable_dimensions", [])
            if isinstance(results["unavailable_dimensions"], list):
                results["unavailable_dimensions"].extend(unavailable)
            results["partial_analysis"] = True

        if errors:
            results.setdefault("errors", [])
            if isinstance(results["errors"], list):
                results["errors"].extend(errors)

        self._last_parallel_latencies = agent_latencies
        return results

    def run_pipeline(self, initial_state: PortfolioState) -> PortfolioState:
        """Run the full multi-stage pipeline, returning normalized PortfolioState with latency metrics."""
        t_pipeline_start = time.perf_counter()
        current = initial_state.model_copy(deep=True)
        stage_latencies: dict[str, float] = dict(current.stage_latencies_ms)
        agent_latencies: dict[str, float] = dict(current.agent_latencies_ms)
        unavailable_dims: set[str] = set(current.unavailable_dimensions)

        # Stage 1: Ingestion
        if self.is_enabled("ingestion"):
            t0 = time.perf_counter()
            ingestion_updates = self._run_agent("ingestion", current)
            stage_latencies["ingestion"] = round((time.perf_counter() - t0) * 1000, 2)
            ing_lat = ingestion_updates.pop("_agent_latency", stage_latencies["ingestion"])
            agent_latencies["ingestion"] = ing_lat
            if ingestion_updates.get("unavailable_dimensions"):
                unavailable_dims.update(ingestion_updates["unavailable_dimensions"])
            current = PortfolioState.model_validate({**current.model_dump(), **ingestion_updates})

        # Stage 2: Parallel Analytical Execution
        t0 = time.perf_counter()
        analytical_updates = self._run_parallel_analytical_stage(current)
        stage_latencies["parallel_analytical"] = round((time.perf_counter() - t0) * 1000, 2)
        parallel_latencies = getattr(self, "_last_parallel_latencies", {})
        if isinstance(parallel_latencies, dict):
            agent_latencies.update(parallel_latencies)
        if analytical_updates.get("unavailable_dimensions"):
            unavailable_dims.update(analytical_updates["unavailable_dimensions"])
        current = PortfolioState.model_validate({**current.model_dump(), **analytical_updates})

        # Stage 3: Critic & Retry Loop
        if self.is_enabled("critic"):
            t0 = time.perf_counter()
            critic_updates = self._run_agent("critic", current)
            stage_latencies["critic"] = round((time.perf_counter() - t0) * 1000, 2)
            critic_lat = critic_updates.pop("_agent_latency", stage_latencies["critic"])
            agent_latencies["critic"] = critic_lat
            current = PortfolioState.model_validate({**current.model_dump(), **critic_updates})

            retry_count = 0
            while current.critic and not current.critic.passed and retry_count < self.max_retries:
                feedback = "; ".join(current.critic.issues)
                retry_count += 1
                retry_updates = self._run_parallel_analytical_stage(current, correction=feedback)
                retry_latencies = retry_updates.pop("_agent_latencies", {})
                if isinstance(retry_latencies, dict):
                    agent_latencies.update(retry_latencies)
                current_dict = {
                    **current.model_dump(),
                    **retry_updates,
                    "retry_count": retry_count,
                }
                current = PortfolioState.model_validate(current_dict)

                recheck_critic = self._run_agent("critic", current)
                recheck_lat = recheck_critic.pop("_agent_latency", 0.0)
                agent_latencies["critic_recheck"] = recheck_lat
                current = PortfolioState.model_validate({**current.model_dump(), **recheck_critic})

        # Stage 4: Synthesis Stage
        if self.is_enabled("synthesize"):
            t0 = time.perf_counter()
            synthesis_updates = self._run_agent("synthesize", current)
            stage_latencies["synthesis"] = round((time.perf_counter() - t0) * 1000, 2)
            synth_lat = synthesis_updates.pop("_agent_latency", stage_latencies["synthesis"])
            agent_latencies["synthesize"] = synth_lat
            current = PortfolioState.model_validate({**current.model_dump(), **synthesis_updates})

        # Stage 5: Scenario Analysis Stage
        if self.is_enabled("scenario_analysis"):
            t0 = time.perf_counter()
            scenario_updates = self._run_agent("scenario_analysis", current)
            stage_latencies["scenario"] = round((time.perf_counter() - t0) * 1000, 2)
            scen_lat = scenario_updates.pop("_agent_latency", stage_latencies["scenario"])
            agent_latencies["scenario_analysis"] = scen_lat
            current = PortfolioState.model_validate({**current.model_dump(), **scenario_updates})

        # Stage 6: Report Generation Stage
        if self.is_enabled("report_generator"):
            t0 = time.perf_counter()
            report_updates = self._run_agent("report_generator", current)
            stage_latencies["report_generator"] = round((time.perf_counter() - t0) * 1000, 2)
            rep_lat = report_updates.pop("_agent_latency", stage_latencies["report_generator"])
            agent_latencies["report_generator"] = rep_lat
            current = PortfolioState.model_validate({**current.model_dump(), **report_updates})

        total_latency = round((time.perf_counter() - t_pipeline_start) * 1000, 2)
        final_dict = {
            **current.model_dump(),
            "stage_latencies_ms": stage_latencies,
            "agent_latencies_ms": agent_latencies,
            "total_latency_ms": total_latency,
            "partial_analysis": current.partial_analysis or bool(current.unavailable_dimensions or unavailable_dims),
            "unavailable_dimensions": list(set(current.unavailable_dimensions) | unavailable_dims),
        }
        return PortfolioState.model_validate(final_dict)
