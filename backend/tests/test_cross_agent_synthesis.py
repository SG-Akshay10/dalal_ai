import unittest

from app.portfolio_agents.data.fundamental import extract_fundamental_finding
from app.portfolio_agents.data.market_context import extract_market_context_finding
from app.portfolio_agents.data.risk import extract_risk_finding
from app.portfolio_agents.data.synthesis import (
    extract_holding_signals,
    synthesize_cross_agent_findings,
)
from app.portfolio_agents.data.valuation import extract_valuation_finding
from app.portfolio_agents.schemas import (
    DataQuality,
    EnrichedHolding,
    ExecutiveSynthesis,
    FundamentalAnalysis,
    FundamentalMetrics,
    MarketContextAnalysis,
    PortfolioState,
    RiskAnalysis,
    TechnicalAnalysis,
    TechnicalFinding,
    Technicals,
    ValuationAnalysis,
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


class CrossAgentSynthesisUnitTests(unittest.TestCase):
    def test_synthesis_signal_extraction_and_agreement(self):
        holding = make_sample_holding()
        fundamental_finding = extract_fundamental_finding(holding)
        valuation_finding = extract_valuation_finding(holding)
        market_finding = extract_market_context_finding(holding)
        risk_finding = extract_risk_finding(holding)
        tech_finding = TechnicalFinding(
            ticker="INFY",
            trend="Bullish",
            momentum="Strong Positive",
            volatility_assessment="Moderate",
            volume_assessment="Above Average",
            narrative="Technical momentum is strong above SMA 50 and SMA 200.",
        )

        state = PortfolioState(
            raw_holdings=[],
            enriched_holdings=[holding],
            technical_analysis=TechnicalAnalysis(detailed_mode=True, findings=[tech_finding]),
            fundamental_analysis=FundamentalAnalysis(applicable=True, findings=[fundamental_finding]),
            valuation_analysis=ValuationAnalysis(applicable=True, findings=[valuation_finding]),
            market_context_analysis=MarketContextAnalysis(applicable=True, findings=[market_finding]),
            risk_analysis=RiskAnalysis(applicable=True, findings=[risk_finding]),
        )

        signals = extract_holding_signals(state, "INFY")
        self.assertIn("Technical", signals)
        self.assertIn("Fundamental", signals)
        self.assertIn("Valuation", signals)
        self.assertIn("Market Context", signals)
        self.assertIn("Risk", signals)

        synthesis = synthesize_cross_agent_findings(state)
        self.assertIsInstance(synthesis, ExecutiveSynthesis)
        self.assertTrue(len(synthesis.agreements) > 0)
        self.assertEqual(synthesis.agreements[0].ticker, "INFY")
        self.assertGreaterEqual(synthesis.agreements[0].evidence_count, 2)
        self.assertTrue(len(synthesis.time_horizon_theses) > 0)
        self.assertEqual(synthesis.time_horizon_theses[0].ticker, "INFY")

    def test_explicit_contradiction_handling(self):
        holding = make_sample_holding()

        # Bullish Technical
        tech_finding = TechnicalFinding(
            ticker="INFY",
            trend="Bullish",
            momentum="Strong Positive",
            volatility_assessment="Low",
            volume_assessment="High",
            narrative="Bullish continuation pattern",
        )
        # Bearish Risk (High severity)
        risk_finding = extract_risk_finding(holding)
        risk_finding.severity = "High"

        state = PortfolioState(
            raw_holdings=[],
            enriched_holdings=[holding],
            technical_analysis=TechnicalAnalysis(detailed_mode=True, findings=[tech_finding]),
            risk_analysis=RiskAnalysis(applicable=True, findings=[risk_finding]),
        )

        synthesis = synthesize_cross_agent_findings(state)
        self.assertTrue(len(synthesis.contradictions) > 0)
        contradiction = synthesis.contradictions[0]
        self.assertEqual(contradiction.ticker, "INFY")
        self.assertIn("Technical", contradiction.dimensions_in_conflict)
        self.assertIn("Risk", contradiction.dimensions_in_conflict)
        self.assertIn("Direct analytical contradiction", contradiction.conflict_description)
        self.assertTrue(len(contradiction.resolution_narrative) > 0)


if __name__ == "__main__":
    unittest.main()
