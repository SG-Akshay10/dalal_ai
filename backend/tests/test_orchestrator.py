import time
import unittest
from unittest.mock import patch

from app.portfolio_agents.orchestrator import ANALYTICAL_AGENTS, PortfolioOrchestrator
from app.portfolio_agents.schemas import (
    ExecutiveReport,
    HoldingInput,
    PortfolioState,
)


def fake_enrich(holding):
    from tests.test_multi_agent_pipeline import fake_enrich as base_fake_enrich
    return base_fake_enrich(holding)


def fake_text_completion(*_args, **_kwargs):
    return "This is a valid Sarvam-generated executive portfolio narrative."


class OrchestratorTests(unittest.TestCase):
    @patch("app.portfolio_agents.agent_modules.report_generator.text_completion", side_effect=fake_text_completion)
    @patch("app.portfolio_agents.agent_modules.ingestion.enrich_holding", side_effect=fake_enrich)
    def test_full_pipeline_orchestration(self, *_):
        orchestrator = PortfolioOrchestrator()
        initial = PortfolioState(raw_holdings=[
            HoldingInput(symbol="INFY", quantity=10, buy_price=100, current_price=110)
        ])
        state = orchestrator.run_pipeline(initial)
        self.assertIsNotNone(state.report)
        self.assertTrue(len(state.enriched_holdings) > 0)
        self.assertIsNotNone(state.sector_analysis)
        self.assertIsNotNone(state.technical_analysis)
        self.assertIsNotNone(state.fundamental_analysis)
        self.assertIsNotNone(state.valuation_analysis)
        self.assertIsNotNone(state.market_context_analysis)
        self.assertIsNotNone(state.critic)
        self.assertIsNotNone(state.scenario_analysis)

    @patch("app.portfolio_agents.agent_modules.report_generator.text_completion", side_effect=fake_text_completion)
    @patch("app.portfolio_agents.agent_modules.ingestion.enrich_holding", side_effect=fake_enrich)
    def test_selective_agent_enablement(self, *_):
        # Disable technical, valuation, and scenario agents
        enabled = ["ingestion", "sector", "asset", "risk", "fundamental", "critic", "synthesize", "report_generator"]
        orchestrator = PortfolioOrchestrator(enabled_agents=enabled)
        initial = PortfolioState(raw_holdings=[
            HoldingInput(symbol="TCS", quantity=5, buy_price=100, current_price=105)
        ])
        state = orchestrator.run_pipeline(initial)
        self.assertIsNotNone(state.report)
        self.assertIsNone(state.technical_analysis)
        self.assertIsNone(state.valuation_analysis)
        self.assertIsNone(state.scenario_analysis)
        self.assertIsNotNone(state.fundamental_analysis)
        self.assertIsNotNone(state.sector_analysis)

    def test_parallel_analytical_stage_concurrency(self):
        orchestrator = PortfolioOrchestrator(enabled_agents=ANALYTICAL_AGENTS, max_workers=8)

        def mock_slow_agent(name, state, correction=None):
            time.sleep(0.1)
            return {f"{name}_analysis_done": True}

        with patch("app.portfolio_agents.orchestrator.run", side_effect=mock_slow_agent):
            initial = PortfolioState(raw_holdings=[])
            start_time = time.time()
            updates = orchestrator._run_parallel_analytical_stage(initial)
            duration = time.time() - start_time

            # 9 analytical agents sleeping 0.1s each in parallel should take significantly less than 0.9s
            self.assertLess(duration, 0.4)
            self.assertEqual(len(updates), 9)


if __name__ == "__main__":
    unittest.main()
