import unittest
from datetime import datetime, timezone

from app.portfolio_agents.data.fundamental import extract_fundamental_finding
from app.portfolio_agents.data.market_context import extract_market_context_finding
from app.portfolio_agents.data.risk import extract_risk_finding
from app.portfolio_agents.data.valuation import extract_valuation_finding
from app.portfolio_agents.schemas import (
    AnalyticalEvidence,
    DataQuality,
    EnrichedHolding,
    FundamentalFinding,
    FundamentalMetrics,
    MarketContextFinding,
    RiskFinding,
    Technicals,
    ValuationFinding,
)


def make_sample_holding():
    return EnrichedHolding(
        ticker="INFY",
        sector="Information Technology",
        quantity=10,
        buy_price=1400.0,
        current_price=1500.0,
        market_value=15000.0,
        pnl_pct=7.14,
        technicals=Technicals(
            rsi14=58.0,
            sma50=1450.0,
            sma200=1400.0,
            crossover="bullish",
            macd_histogram=1.5,
            annualized_volatility_pct=22.0,
            max_drawdown_pct=-14.0,
            support=1420.0,
            momentum_14d_pct=3.5,
            volume_ratio=1.1,
        ),
        fundamentals=FundamentalMetrics(
            pe_ratio=25.0,
            pb_ratio=6.0,
            de_ratio=0.2,
            roe_pct=24.0,
            operating_margin_pct=18.0,
            revenue_growth_pct=10.0,
            earnings_growth_pct=12.0,
            free_cash_flow=4000000.0,
        ),
        data_quality=DataQuality(source="client-supplied", fresh=True, complete=True),
    )


class EvidenceLayerUnitTests(unittest.TestCase):
    def test_fundamental_finding_contains_analytical_evidence(self):
        holding = make_sample_holding()
        finding = extract_fundamental_finding(holding)

        self.assertIsInstance(finding, FundamentalFinding)
        self.assertIsNotNone(finding.evidence)
        self.assertIsInstance(finding.evidence, AnalyticalEvidence)
        self.assertIn("pe_ratio", finding.evidence.supporting_metrics)
        self.assertEqual(finding.evidence.supporting_metrics["pe_ratio"], 25.0)
        self.assertGreaterEqual(finding.evidence.confidence_score, 0.80)
        self.assertEqual(finding.evidence.data_quality_rating, "High")
        self.assertIsNotNone(finding.evidence.interpretation)

    def test_valuation_finding_contains_analytical_evidence(self):
        holding = make_sample_holding()
        finding = extract_valuation_finding(holding)

        self.assertIsInstance(finding, ValuationFinding)
        self.assertIsNotNone(finding.evidence)
        self.assertIsInstance(finding.evidence, AnalyticalEvidence)
        self.assertIn("trailing_pe", finding.evidence.supporting_metrics)
        self.assertGreaterEqual(finding.evidence.confidence_score, 0.80)
        self.assertTrue(len(finding.evidence.limitations) > 0)

    def test_market_context_finding_contains_analytical_evidence(self):
        holding = make_sample_holding()
        finding = extract_market_context_finding(holding)

        self.assertIsInstance(finding, MarketContextFinding)
        self.assertIsNotNone(finding.evidence)
        self.assertIsInstance(finding.evidence, AnalyticalEvidence)
        self.assertIn("relative_strength_vs_market_pct", finding.evidence.supporting_metrics)
        self.assertIn("broad_market", finding.evidence.comparisons)
        self.assertEqual(finding.evidence.data_quality_rating, "High")

    def test_risk_finding_contains_analytical_evidence(self):
        holding = make_sample_holding()
        finding = extract_risk_finding(holding)

        self.assertIsInstance(finding, RiskFinding)
        self.assertIsNotNone(finding.evidence)
        self.assertIsInstance(finding.evidence, AnalyticalEvidence)
        self.assertEqual(finding.evidence.supporting_metrics["max_drawdown_pct"], -14.0)
        self.assertTrue(len(finding.evidence.historical_observations) > 0)
        self.assertIn("leverage_threshold", finding.evidence.comparisons)


if __name__ == "__main__":
    unittest.main()
