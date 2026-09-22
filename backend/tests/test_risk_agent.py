import unittest
from datetime import datetime, timezone

from app.portfolio_agents import agents
from app.portfolio_agents.agent_modules.risk import RiskAgent
from app.portfolio_agents.data.risk import (
    evaluate_earnings_risk,
    evaluate_leverage_risk,
    evaluate_liquidity_risk,
    evaluate_sector_sensitivity,
    evaluate_valuation_risk,
    extract_risk_finding,
)
from app.portfolio_agents.schemas import (
    DataQuality,
    EnrichedHolding,
    FundamentalMetrics,
    PortfolioState,
    RiskFinding,
    Technicals,
)


def make_holding(
    ticker="INFY",
    sector="Information Technology",
    drawdown=-28.0,
    volatility=36.0,
    de_ratio=1.6,
    pe_ratio=32.0,
    earnings_growth=-5.0,
    price=1500.0,
):
    return EnrichedHolding(
        ticker=ticker,
        sector=sector,
        quantity=10,
        buy_price=1400.0,
        current_price=price,
        market_value=price * 10,
        pnl_pct=7.14,
        technicals=Technicals(
            momentum_14d_pct=4.5,
            annualized_volatility_pct=volatility,
            max_drawdown_pct=drawdown,
            support=1400.0,
            volume_ratio=0.5,
            avg_volume_20d=100000.0,
            latest_volume=50000.0,
        ),
        fundamentals=FundamentalMetrics(
            pe_ratio=pe_ratio,
            de_ratio=de_ratio,
            earnings_growth_pct=earnings_growth,
            revenue_growth_pct=10.0,
            roe_pct=18.0,
        ),
        data_quality=DataQuality(source="client-supplied", fresh=True, complete=True),
    )


class RiskAgentUnitTests(unittest.TestCase):
    def test_risk_sub_evaluators(self):
        self.assertIn("High leverage", evaluate_leverage_risk(1.6))
        self.assertIn("Low liquidity", evaluate_liquidity_risk(0.5, 50000, 100000))
        self.assertIn("Elevated valuation", evaluate_valuation_risk(45.0, 26.0))
        self.assertIn("Deteriorating earnings", evaluate_earnings_risk(-8.0))
        self.assertIn("Defensive", evaluate_sector_sensitivity("Consumer Goods"))
        self.assertIn("High cyclical", evaluate_sector_sensitivity("Metals & Mining"))

    def test_extract_risk_finding(self):
        holding = make_holding()
        finding = extract_risk_finding(holding)

        self.assertIsInstance(finding, RiskFinding)
        self.assertEqual(finding.ticker, "INFY")
        self.assertEqual(finding.severity, "High")
        self.assertEqual(finding.drawdown_pct, -28.0)
        self.assertEqual(finding.volatility_pct, 36.0)

        # Check evidence vs hypothetical risks
        self.assertTrue(len(finding.evidence_backed_risks) > 0)
        self.assertTrue(len(finding.hypothetical_risks) > 0)
        self.assertTrue(any("28.0%" in item for item in finding.evidence_backed_risks))

        # Check downside scenarios & invalidation conditions
        self.assertTrue(len(finding.downside_scenarios) > 0)

        # Check agent disagreements
        self.assertTrue(len(finding.agent_disagreements) > 0)

        # Narrative length >= 100 words
        self.assertGreaterEqual(len(finding.narrative.split()), 100)
        self.assertIn("educational risk diagnostic", finding.narrative.lower())

    def test_risk_agent_run_detailed_mode(self):
        holding = make_holding()
        state = PortfolioState(raw_holdings=[], enriched_holdings=[holding])
        result = RiskAgent().run(state)

        self.assertIn("risk_analysis", result)
        analysis = result["risk_analysis"]
        self.assertTrue(analysis.applicable)
        self.assertEqual(len(analysis.findings), 1)
        self.assertEqual(analysis.findings[0].ticker, "INFY")
        self.assertEqual(analysis.portfolio_risk_level, "High")
        self.assertGreaterEqual(len(analysis.findings[0].narrative.split()), 100)

    def test_risk_agent_run_skipped_mode(self):
        holdings = [make_holding(ticker=f"STOCK{i}") for i in range(22)]
        state = PortfolioState(raw_holdings=[], enriched_holdings=holdings)
        result = RiskAgent().run(state)

        analysis = result["risk_analysis"]
        self.assertFalse(analysis.applicable)
        self.assertIn("omitted", analysis.concentration_risk_summary)


if __name__ == "__main__":
    unittest.main()
