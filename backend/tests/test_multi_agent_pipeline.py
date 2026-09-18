import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.portfolio_agents import agents
from app.portfolio_agents.graph import PortfolioAnalysisUnavailable, run_portfolio_pipeline
from app.portfolio_agents.schemas import AssetAnalysis, AssetFinding, EnrichedHolding, HoldingInput, PortfolioState, Technicals
from app.portfolio_agents.tools import calculate_technicals, diversification_score, enrich_holding, market_data_is_fresh
from app.services.sarvam import SarvamStructuredOutputError


def fake_enrich(holding):
    price = holding.current_price or 100
    return EnrichedHolding(ticker=(holding.ticker or holding.symbol).upper(), sector=holding.sector or "Information Technology", quantity=holding.quantity, buy_price=holding.buy_price or 100, current_price=price, market_value=price * holding.quantity, pnl_pct=0, technicals=Technicals(rsi14=55, sma50=98, sma200=90, macd_histogram=1.2, crossover="bullish", support=90, resistance=110, max_drawdown_pct=-12))


def fake_text_completion(*_args, **_kwargs):
    return "This is a valid Sarvam-generated executive portfolio narrative."


def fake_no_news(*_args, **_kwargs):
    return []


class MultiAgentPipelineTests(unittest.TestCase):
    def test_indicator_and_diversification_calculations(self):
        technicals = calculate_technicals([{"close": price, "sma50": 100, "sma200": 90} for price in range(90, 151)], {"rsi14": 60, "macd_histogram": 2, "sma_crossover": "bullish"})
        self.assertEqual(technicals.crossover, "bullish")
        self.assertIsNotNone(technicals.support)
        self.assertLess(diversification_score({"Tech": 100}, 100), 1)

    @patch("app.portfolio_agents.tools.market_snapshot")
    def test_enrichment_uses_supplied_history_without_refetching_it(self, snapshot):
        holding = enrich_holding(HoldingInput(symbol="INFY", quantity=2, buy_price=100, current_price=120, market_data_as_of=datetime.now(timezone.utc).isoformat(), historical_prices=[
            {"time": "2026-01-01", "close": 100, "sma50": 95, "sma200": 90, "rsi14": 55, "macd_histogram": 1},
            {"time": "2026-01-02", "close": 120, "sma50": 100, "sma200": 91, "rsi14": 60, "macd_histogram": 2},
        ]))
        snapshot.assert_not_called()
        self.assertEqual(holding.current_price, 120)
        self.assertEqual(holding.technicals.crossover, "bullish")
        self.assertEqual(holding.technicals.rsi14, 60)

    def test_dashboard_market_data_expires_after_ten_minutes(self):
        self.assertTrue(market_data_is_fresh(datetime.now(timezone.utc).isoformat()))
        self.assertFalse(market_data_is_fresh((datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()))

    @patch("app.portfolio_agents.agent_modules.sector_thesis.fetch_sector_news", side_effect=fake_no_news)
    @patch("app.portfolio_agents.agent_modules.stock_thesis.fetch_rss_news", side_effect=fake_no_news)
    @patch("app.portfolio_agents.agent_modules.synthesis.text_completion", side_effect=fake_text_completion)
    @patch("app.portfolio_agents.agent_modules.ingestion.enrich_holding", side_effect=fake_enrich)
    def test_pipeline_generates_detailed_report_for_twenty_or_fewer(self, *_):
        state = run_portfolio_pipeline([{"symbol": "INFY", "quantity": 2, "buy_price": 100, "current_price": 100}])
        self.assertTrue(state.report)
        self.assertTrue(state.asset_analysis.detailed_mode)
        self.assertGreaterEqual(len(state.asset_analysis.findings[0].narrative.split()), 100)
        self.assertTrue(state.stock_thesis.applicable)
        self.assertTrue(state.sector_thesis.findings)

    @patch("app.portfolio_agents.agent_modules.sector_thesis.fetch_sector_news", side_effect=fake_no_news)
    @patch("app.portfolio_agents.agent_modules.stock_thesis.fetch_rss_news", side_effect=fake_no_news)
    @patch("app.portfolio_agents.agent_modules.synthesis.text_completion", side_effect=fake_text_completion)
    @patch("app.portfolio_agents.agent_modules.ingestion.enrich_holding", side_effect=fake_enrich)
    def test_pipeline_uses_sector_only_mode_above_twenty_holdings(self, *_):
        state = run_portfolio_pipeline([{"symbol": f"STOCK{index}", "quantity": 1, "buy_price": 100, "current_price": 100} for index in range(21)])
        self.assertFalse(state.asset_analysis.detailed_mode)
        self.assertEqual(state.asset_analysis.findings, [])
        self.assertFalse(state.stock_thesis.applicable)
        self.assertTrue(state.sector_thesis.findings)

    def test_critic_rejects_short_asset_narrative(self):
        state = PortfolioState(raw_holdings=[], asset_analysis=AssetAnalysis(detailed_mode=True, findings=[AssetFinding(ticker="INFY", trend="Bullish", momentum="Neutral", narrative="Too short")]))
        result = agents.critic_agent(state)["critic"]
        self.assertFalse(result.passed)

    @patch("app.portfolio_agents.agent_modules.sector_thesis.fetch_sector_news", side_effect=fake_no_news)
    @patch("app.portfolio_agents.agent_modules.stock_thesis.fetch_rss_news", side_effect=fake_no_news)
    @patch("app.portfolio_agents.agent_modules.synthesis.text_completion", side_effect=SarvamStructuredOutputError("unavailable"))
    @patch("app.portfolio_agents.agent_modules.ingestion.enrich_holding", side_effect=fake_enrich)
    def test_sarvam_failure_hides_report_via_typed_error(self, *_):
        with self.assertRaises(PortfolioAnalysisUnavailable):
            run_portfolio_pipeline([{"symbol": "INFY", "quantity": 1, "buy_price": 100}])


if __name__ == "__main__":
    unittest.main()
