import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.portfolio_agents import agents
from app.portfolio_agents.graph import PortfolioAnalysisUnavailable, run_portfolio_pipeline
from app.portfolio_agents.schemas import (
    AssetAnalysis,
    AssetFinding,
    DataQuality,
    EnrichedHolding,
    EvidenceRecord,
    HoldingInput,
    PortfolioState,
    Technicals,
)
from app.portfolio_agents.data import (
    calculate_technicals,
    diversification_score,
    enrich_holding,
    holding_quality,
    market_data_is_fresh,
)
from app.services.sarvam import SarvamStructuredOutputError


def fake_enrich(holding):
    price = holding.current_price or 100
    return EnrichedHolding(
        ticker=(holding.ticker or holding.symbol).upper(),
        sector=holding.sector or "Information Technology",
        quantity=holding.quantity,
        buy_price=holding.buy_price or 100,
        current_price=price,
        market_value=price * holding.quantity,
        pnl_pct=0,
        technicals=Technicals(
            rsi14=55, sma50=98, sma200=90, macd_histogram=1.2,
            crossover="bullish", support=90, resistance=110, max_drawdown_pct=-12,
        ),
        data_quality=DataQuality(
            source="client-supplied", as_of=datetime.now(timezone.utc).isoformat(),
            fresh=True, complete=True,
        ),
    )


def fake_text_completion(*_args, **_kwargs):
    return "This is a valid Sarvam-generated executive portfolio narrative."


class MultiAgentPipelineTests(unittest.TestCase):
    def test_indicator_and_diversification_calculations(self):
        technicals = calculate_technicals(
            [{"close": price, "sma50": 100, "sma200": 90} for price in range(90, 151)],
            {"rsi14": 60, "macd_histogram": 2, "sma_crossover": "bullish"},
        )
        self.assertEqual(technicals.crossover, "bullish")
        self.assertIsNotNone(technicals.support)
        self.assertLess(diversification_score({"Tech": 100}, 100), 1)

    # ------------------------------------------------------------------
    # Data-quality metadata
    # ------------------------------------------------------------------

    def test_holding_quality_fresh_and_complete(self):
        """holding_quality correctly marks a fresh, complete snapshot."""
        quality = holding_quality(
            source="client-supplied",
            as_of=datetime.now(timezone.utc).isoformat(),
            errors=[],
            missing_fields=[],
        )
        self.assertTrue(quality.fresh)
        self.assertTrue(quality.complete)
        self.assertEqual(quality.source, "client-supplied")

    def test_holding_quality_stale_and_incomplete(self):
        """holding_quality marks a ten-minute-old snapshot as stale and flags missing fields."""
        stale_ts = (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()
        quality = holding_quality(
            source="Yahoo Finance (delayed)",
            as_of=stale_ts,
            errors=["Current price unavailable"],
            missing_fields=["current_price"],
        )
        self.assertFalse(quality.fresh)
        self.assertFalse(quality.complete)
        self.assertIn("current_price", quality.missing_fields)

    @patch("app.portfolio_agents.data.market.market_snapshot")
    def test_enrichment_propagates_data_quality_on_success(self, mock_snapshot):
        """enrich_holding populates data_quality when client-supplied data is fresh."""
        holding = enrich_holding(HoldingInput(
            symbol="INFY", quantity=2, buy_price=100, current_price=120,
            market_data_as_of=datetime.now(timezone.utc).isoformat(),
            historical_prices=[
                {"time": "2026-01-01", "close": 100, "sma50": 95, "sma200": 90,
                 "rsi14": 55, "macd_histogram": 1},
                {"time": "2026-01-02", "close": 120, "sma50": 100, "sma200": 91,
                 "rsi14": 60, "macd_histogram": 2},
            ],
        ))
        mock_snapshot.assert_not_called()
        self.assertEqual(holding.current_price, 120)
        self.assertEqual(holding.technicals.crossover, "bullish")
        self.assertEqual(holding.technicals.rsi14, 60)
        self.assertTrue(holding.data_quality.fresh)
        self.assertTrue(holding.data_quality.complete)
        self.assertEqual(holding.data_quality.source, "client-supplied")

    @patch("app.portfolio_agents.data.market.market_snapshot")
    def test_enrichment_marks_stale_data_quality(self, mock_snapshot):
        """enrich_holding falls back to Yahoo and marks data as not from client when stale."""
        mock_snapshot.return_value = {
            "price": 150, "history": [
                {"close": 140, "sma50": 138, "sma200": 130},
                {"close": 150, "sma50": 145, "sma200": 132},
            ],
            "indicators": {"rsi14": 58, "macd_histogram": 0.5, "sma_crossover": "bullish"},
            "as_of": datetime.now(timezone.utc).isoformat(),
        }
        stale_ts = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
        holding = enrich_holding(HoldingInput(
            symbol="TCS", quantity=1, buy_price=130, current_price=140,
            market_data_as_of=stale_ts,
            historical_prices=[{"time": "2026-01-01", "close": 140}],
        ))
        mock_snapshot.assert_called_once()
        self.assertEqual(holding.data_quality.source, "Yahoo Finance (delayed)")

    # ------------------------------------------------------------------
    # Market-data freshness
    # ------------------------------------------------------------------

    def test_dashboard_market_data_expires_after_ten_minutes(self):
        self.assertTrue(market_data_is_fresh(datetime.now(timezone.utc).isoformat()))
        self.assertFalse(market_data_is_fresh(
            (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()
        ))

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------

    @patch("app.portfolio_agents.agent_modules.synthesis.text_completion",
           side_effect=fake_text_completion)
    @patch("app.portfolio_agents.agent_modules.ingestion.enrich_holding",
           side_effect=fake_enrich)
    def test_pipeline_generates_detailed_report_for_twenty_or_fewer(self, *_):
        state = run_portfolio_pipeline([
            {"symbol": "INFY", "quantity": 2, "buy_price": 100, "current_price": 100}
        ])
        self.assertTrue(state.report)
        self.assertTrue(state.asset_analysis.detailed_mode)
        self.assertGreaterEqual(len(state.asset_analysis.findings[0].narrative.split()), 100)
        self.assertTrue(state.stock_thesis.applicable)
        self.assertTrue(state.sector_thesis.findings)

    @patch("app.portfolio_agents.agent_modules.synthesis.text_completion",
           side_effect=fake_text_completion)
    @patch("app.portfolio_agents.agent_modules.ingestion.enrich_holding",
           side_effect=fake_enrich)
    def test_pipeline_uses_sector_only_mode_above_twenty_holdings(self, *_):
        state = run_portfolio_pipeline([
            {"symbol": f"STOCK{index}", "quantity": 1, "buy_price": 100, "current_price": 100}
            for index in range(21)
        ])
        self.assertFalse(state.asset_analysis.detailed_mode)
        self.assertEqual(state.asset_analysis.findings, [])
        self.assertFalse(state.stock_thesis.applicable)
        self.assertTrue(state.sector_thesis.findings)

    @patch("app.portfolio_agents.agent_modules.synthesis.text_completion",
           side_effect=fake_text_completion)
    @patch("app.portfolio_agents.agent_modules.ingestion.enrich_holding",
           side_effect=fake_enrich)
    def test_enriched_holdings_carry_data_quality_in_pipeline(self, *_):
        """Every enriched holding in a pipeline run must carry a DataQuality record."""
        state = run_portfolio_pipeline([
            {"symbol": "HDFCBANK", "quantity": 5, "buy_price": 1500, "current_price": 1600}
        ])
        for holding in state.enriched_holdings:
            self.assertIsNotNone(holding.data_quality)
            self.assertIsInstance(holding.data_quality, DataQuality)

    def test_critic_rejects_short_asset_narrative(self):
        state = PortfolioState(
            raw_holdings=[],
            asset_analysis=AssetAnalysis(
                detailed_mode=True,
                findings=[AssetFinding(ticker="INFY", trend="Bullish", momentum="Neutral", narrative="Too short")],
            ),
        )
        result = agents.critic_agent(state)["critic"]
        self.assertFalse(result.passed)

    def test_critic_rejects_unverified_external_evidence(self):
        state = PortfolioState(
            raw_holdings=[],
            evidence=[EvidenceRecord(
                source="future-news", subject="INFY", claim="Unverified claim",
                retrieved_at="2026-01-01T00:00:00Z", quality_score=0.4, verified=False,
            )],
        )
        result = agents.critic_agent(state)["critic"]
        self.assertFalse(result.passed)
        self.assertIn("External evidence failed verification or minimum quality requirements", result.issues)

    @patch("app.portfolio_agents.agent_modules.synthesis.text_completion",
           side_effect=SarvamStructuredOutputError("unavailable"))
    @patch("app.portfolio_agents.agent_modules.ingestion.enrich_holding",
           side_effect=fake_enrich)
    def test_sarvam_failure_hides_report_via_typed_error(self, *_):
        with self.assertRaises(PortfolioAnalysisUnavailable):
            run_portfolio_pipeline([{"symbol": "INFY", "quantity": 1, "buy_price": 100}])


if __name__ == "__main__":
    unittest.main()
