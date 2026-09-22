import unittest
from datetime import datetime, timezone

from app.portfolio_agents import agents
from app.portfolio_agents.agent_modules.market_context import MarketContextAgent
from app.portfolio_agents.data.market_context import (
    classify_movement_alignment,
    evaluate_relative_strength,
    extract_market_context_finding,
    get_broad_market_benchmark,
    get_sector_market_benchmark,
)
from app.portfolio_agents.schemas import (
    DataQuality,
    EnrichedHolding,
    HoldingInput,
    MarketContextFinding,
    PortfolioState,
    Technicals,
)


def make_holding(ticker="INFY", sector="Information Technology", momentum=4.5, volatility=18.0, price=1500.0):
    return EnrichedHolding(
        ticker=ticker,
        sector=sector,
        quantity=10,
        buy_price=1400.0,
        current_price=price,
        market_value=price * 10,
        pnl_pct=7.14,
        technicals=Technicals(
            momentum_14d_pct=momentum,
            annualized_volatility_pct=volatility,
            sma50=1450.0,
            sma200=1400.0,
            crossover="bullish",
            rsi14=62.0,
            macd_histogram=2.5,
        ),
        data_quality=DataQuality(source="client-supplied", fresh=True, complete=True),
    )


class MarketContextUnitTests(unittest.TestCase):
    def test_benchmark_providers(self):
        broad = get_broad_market_benchmark()
        self.assertEqual(broad["name"], "NIFTY 50")
        self.assertIn("momentum_14d_pct", broad)

        sector_bm = get_sector_market_benchmark("Information Technology")
        self.assertEqual(sector_bm["name"], "NIFTY IT")

        default_bm = get_sector_market_benchmark("NonExistentSector")
        self.assertEqual(default_bm["name"], "NIFTY 500")

    def test_relative_strength_calculation(self):
        rs = evaluate_relative_strength(5.5, 2.1)
        self.assertEqual(rs, 3.4)

        rs_none = evaluate_relative_strength(None, 2.1)
        self.assertIsNone(rs_none)

    def test_movement_alignment_classification(self):
        # Outperforming broad market & sector
        outperform = classify_movement_alignment(6.0, 1.8, 2.1)
        self.assertIn("Outperforming", outperform)

        # Diverging positively when market is down
        div_pos = classify_movement_alignment(3.0, -1.0, -1.5)
        self.assertEqual(div_pos, "Diverging Positively")

        # Diverging negatively when market is up
        div_neg = classify_movement_alignment(-2.0, 2.5, 3.0)
        self.assertEqual(div_neg, "Diverging Negatively")

        # Aligned
        aligned = classify_movement_alignment(2.2, 2.0, 2.1)
        self.assertEqual(aligned, "Aligned with Market & Sector")

    def test_extract_market_context_finding(self):
        holding = make_holding()
        finding = extract_market_context_finding(holding)

        self.assertIsInstance(finding, MarketContextFinding)
        self.assertEqual(finding.ticker, "INFY")
        self.assertEqual(finding.sector, "Information Technology")
        self.assertIsNotNone(finding.relative_strength_vs_market)
        self.assertIsNotNone(finding.relative_strength_vs_sector)
        self.assertIn("observed_context_metrics", finding.model_dump())
        self.assertIn("analytical_assumptions", finding.model_dump())
        self.assertGreaterEqual(len(finding.narrative.split()), 100)
        self.assertIn("educational market context analysis", finding.narrative.lower())

    def test_market_context_agent_run_detailed_mode(self):
        holding = make_holding()
        state = PortfolioState(raw_holdings=[], enriched_holdings=[holding])
        result = MarketContextAgent().run(state)

        self.assertIn("market_context_analysis", result)
        analysis = result["market_context_analysis"]
        self.assertTrue(analysis.applicable)
        self.assertEqual(len(analysis.findings), 1)
        self.assertEqual(analysis.findings[0].ticker, "INFY")
        self.assertGreaterEqual(len(analysis.findings[0].narrative.split()), 100)

    def test_market_context_agent_run_skipped_mode(self):
        holdings = [make_holding(ticker=f"STOCK{i}") for i in range(22)]
        state = PortfolioState(raw_holdings=[], enriched_holdings=holdings)
        result = MarketContextAgent().run(state)

        analysis = result["market_context_analysis"]
        self.assertFalse(analysis.applicable)
        self.assertIn("omitted", analysis.overall_market_context_summary)


if __name__ == "__main__":
    unittest.main()
