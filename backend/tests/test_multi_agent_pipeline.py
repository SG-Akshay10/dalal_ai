import unittest
from unittest.mock import patch

from app.portfolio_agents import agents
from app.portfolio_agents.graph import PortfolioAnalysisUnavailable, run_portfolio_pipeline
from app.portfolio_agents.schemas import AssetAnalysis, AssetFinding, EnrichedHolding, PortfolioState, Technicals
from app.portfolio_agents.tools import calculate_technicals, diversification_score
from app.services.sarvam import SarvamStructuredOutputError


def fake_enrich(holding):
    price = holding.current_price or 100
    return EnrichedHolding(ticker=(holding.ticker or holding.symbol).upper(), sector=holding.sector or "Information Technology", quantity=holding.quantity, buy_price=holding.buy_price or 100, current_price=price, market_value=price * holding.quantity, pnl_pct=0, technicals=Technicals(rsi14=55, sma50=98, sma200=90, macd_histogram=1.2, crossover="bullish", support=90, resistance=110, max_drawdown_pct=-12))


def fake_text_completion(*_args, **_kwargs):
    return "This is a valid Sarvam-generated executive portfolio narrative."


class MultiAgentPipelineTests(unittest.TestCase):
    def test_indicator_and_diversification_calculations(self):
        technicals = calculate_technicals([{"close": price, "sma50": 100, "sma200": 90} for price in range(90, 151)], {"rsi14": 60, "macd_histogram": 2, "sma_crossover": "bullish"})
        self.assertEqual(technicals.crossover, "bullish")
        self.assertIsNotNone(technicals.support)
        self.assertLess(diversification_score({"Tech": 100}, 100), 1)

    @patch.object(agents, "text_completion", side_effect=fake_text_completion)
    @patch.object(agents, "enrich_holding", side_effect=fake_enrich)
    def test_pipeline_generates_detailed_report_for_ten_or_fewer(self, *_):
        state = run_portfolio_pipeline([{"symbol": "INFY", "quantity": 2, "buy_price": 100, "current_price": 100}])
        self.assertTrue(state.report)
        self.assertTrue(state.asset_analysis.detailed_mode)
        self.assertGreaterEqual(len(state.asset_analysis.findings[0].narrative.split()), 100)

    @patch.object(agents, "text_completion", side_effect=fake_text_completion)
    @patch.object(agents, "enrich_holding", side_effect=fake_enrich)
    def test_pipeline_uses_sector_only_mode_above_ten_holdings(self, *_):
        state = run_portfolio_pipeline([{"symbol": f"STOCK{index}", "quantity": 1, "buy_price": 100, "current_price": 100} for index in range(11)])
        self.assertFalse(state.asset_analysis.detailed_mode)
        self.assertEqual(state.asset_analysis.findings, [])

    def test_critic_rejects_short_asset_narrative(self):
        state = PortfolioState(raw_holdings=[], asset_analysis=AssetAnalysis(detailed_mode=True, findings=[AssetFinding(ticker="INFY", trend="Bullish", momentum="Neutral", narrative="Too short")]))
        result = agents.critic_agent(state)["critic"]
        self.assertFalse(result.passed)

    @patch.object(agents, "text_completion", side_effect=SarvamStructuredOutputError("unavailable"))
    @patch.object(agents, "enrich_holding", side_effect=fake_enrich)
    def test_sarvam_failure_hides_report_via_typed_error(self, *_):
        with self.assertRaises(PortfolioAnalysisUnavailable):
            run_portfolio_pipeline([{"symbol": "INFY", "quantity": 1, "buy_price": 100}])


if __name__ == "__main__":
    unittest.main()
