"""Unit tests for Phase 16 — Context & Latency Optimization."""

import time
import unittest
from unittest.mock import patch

from app.portfolio_agents.data.cache import AgentDataCache, global_data_cache
from app.portfolio_agents.data.context_pruner import (
    get_pruned_synthesis_context,
    prune_holding_input,
)
from app.portfolio_agents.orchestrator import PortfolioOrchestrator
from app.portfolio_agents.schemas import (
    EnrichedHolding,
    HoldingInput,
    PortfolioState,
)


class ContextAndLatencyTests(unittest.TestCase):
    def setUp(self):
        global_data_cache.clear()

    def test_cache_hit_and_miss_and_ttl(self):
        cache = AgentDataCache(default_ttl_seconds=0.2)
        key = cache.make_key("test_op", "INFY", quantity=10)

        # First call is a miss
        self.assertIsNone(cache.get(key))
        cache.set(key, {"computed_val": 42})

        # Second call is a hit
        self.assertEqual(cache.get(key), {"computed_val": 42})
        stats = cache.get_stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)

        # After TTL expires
        time.sleep(0.25)
        self.assertIsNone(cache.get(key))

    def test_context_pruning_removes_raw_history(self):
        holding = HoldingInput(
            symbol="TCS",
            quantity=5,
            buy_price=3000,
            current_price=3200,
            historical_prices=[{"close": 3100 + i, "date": f"2026-01-{i+1:02d}"} for i in range(50)],
        )

        pruned = prune_holding_input(holding)
        self.assertEqual(pruned["symbol"], "TCS")
        self.assertEqual(pruned["historical_prices"], "[50 bars available]")

    def test_pruned_synthesis_context_summarizes_findings(self):
        state = PortfolioState(
            raw_holdings=[HoldingInput(symbol="TCS", quantity=5, buy_price=3000, current_price=3200)],
            enriched_holdings=[EnrichedHolding(ticker="TCS", quantity=5, buy_price=3000, current_price=3200)],
            unavailable_dimensions=["valuation"],
            partial_analysis=True,
        )

        ctx = get_pruned_synthesis_context(state)
        self.assertEqual(ctx["holding_count"], 1)
        self.assertIn("valuation", ctx["unavailable_dimensions"])
        self.assertTrue(ctx["partial_analysis"])

    @patch("app.portfolio_agents.agent_modules.report_generator.text_completion")
    def test_pipeline_tracks_latencies(self, mock_text):
        mock_text.return_value = "Mock narrative summary"
        orchestrator = PortfolioOrchestrator(enabled_agents=["ingestion", "sector", "synthesize", "report_generator"])

        initial = PortfolioState(
            raw_holdings=[HoldingInput(symbol="INFY", quantity=10, buy_price=1500, current_price=1600)]
        )

        state = orchestrator.run_pipeline(initial)

        self.assertGreater(state.total_latency_ms, 0.0)
        self.assertIn("ingestion", state.stage_latencies_ms)
        self.assertIn("parallel_analytical", state.stage_latencies_ms)
        self.assertIn("report_generator", state.stage_latencies_ms)

    def test_fault_tolerance_records_unavailable_dimension(self):
        orchestrator = PortfolioOrchestrator(enabled_agents=["technical", "fundamental"])

        def failing_run(name, state, correction=None):
            if name == "technical":
                raise RuntimeError("Market feed timeout")
            return {f"{name}_analysis_done": True}

        with patch("app.portfolio_agents.orchestrator.run", side_effect=failing_run):
            initial = PortfolioState(raw_holdings=[])
            state = orchestrator.run_pipeline(initial)

            self.assertTrue(state.partial_analysis)
            self.assertIn("technical", state.unavailable_dimensions)
            self.assertTrue(any("technical" in err for err in state.errors))


if __name__ == "__main__":
    unittest.main()
