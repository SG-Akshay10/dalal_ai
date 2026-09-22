import unittest
from datetime import datetime, timezone

from app.portfolio_agents.agent_modules.report_generator import ReportGeneratorAgent
from app.portfolio_agents.data.report import (
    build_consolidated_findings,
    build_executive_report_data,
    compile_analytical_limitations,
    extract_traceable_claims,
)
from app.portfolio_agents.schemas import (
    DataQuality,
    EnrichedHolding,
    FundamentalAnalysis,
    FundamentalFinding,
    HoldingInput,
    MarketContextAnalysis,
    MarketContextFinding,
    PortfolioState,
    RiskAnalysis,
    RiskFinding,
    TechnicalAnalysis,
    TechnicalFinding,
    ValuationAnalysis,
    ValuationFinding,
)


def create_mock_state():
    holding = EnrichedHolding(
        ticker="TCS",
        sector="Information Technology",
        quantity=10,
        buy_price=3000.0,
        current_price=3500.0,
        market_value=35000.0,
        data_quality=DataQuality(fresh=True, complete=True),
    )

    fund_finding = FundamentalFinding(
        ticker="TCS",
        sector="Information Technology",
        health_score=75.0,
        key_metrics={"pe_ratio": 28.0, "roe_pct": 30.0},
        positive_developments=["Robust margin expansion"],
    )

    tech_finding = TechnicalFinding(
        ticker="TCS",
        trend="Bullish",
        momentum="Strong Positive",
        volatility_assessment="Low Volatility",
        volume_assessment="Above Average Volume",
    )

    val_finding = ValuationFinding(
        ticker="TCS",
        sector="Information Technology",
        current_price=3500.0,
        valuation_assessment="Fairly Valued",
        observed_metrics={"pe_ratio": 28.0},
    )

    mkt_finding = MarketContextFinding(
        ticker="TCS",
        sector="Information Technology",
        relative_strength_vs_market=4.5,
        movement_alignment="Outperforming Broad Market",
    )

    risk_finding = RiskFinding(
        ticker="TCS",
        severity="Low",
        drawdown_pct=-8.0,
        volatility_pct=15.0,
    )

    return PortfolioState(
        raw_holdings=[HoldingInput(ticker="TCS", quantity=10, buy_price=3000.0)],
        enriched_holdings=[holding],
        fundamental_analysis=FundamentalAnalysis(applicable=True, findings=[fund_finding]),
        technical_analysis=TechnicalAnalysis(detailed_mode=True, findings=[tech_finding]),
        valuation_analysis=ValuationAnalysis(applicable=True, findings=[val_finding]),
        market_context_analysis=MarketContextAnalysis(applicable=True, findings=[mkt_finding]),
        risk_analysis=RiskAnalysis(applicable=True, findings=[risk_finding]),
    )


class ReportGeneratorUnitTests(unittest.TestCase):
    def test_extract_traceable_claims(self):
        state = create_mock_state()
        claims = extract_traceable_claims(state)
        self.assertGreater(len(claims), 0)
        tcs_claims = [c for c in claims if c.ticker == "TCS"]
        self.assertTrue(any(c.dimension == "Fundamental" for c in tcs_claims))
        self.assertTrue(any(c.dimension == "Technical" for c in tcs_claims))
        self.assertTrue(any(c.dimension == "Valuation" for c in tcs_claims))

    def test_build_consolidated_findings(self):
        state = create_mock_state()
        consolidated = build_consolidated_findings(state)
        self.assertEqual(len(consolidated), 1)
        self.assertEqual(consolidated[0].ticker, "TCS")
        self.assertEqual(consolidated[0].overall_stance, "Fairly Valued")
        self.assertIn("Robust margin expansion", consolidated[0].key_drivers)

    def test_compile_analytical_limitations(self):
        state = create_mock_state()
        state.enriched_holdings[0].data_quality.fresh = False
        limitations = compile_analytical_limitations(state)
        self.assertTrue(any("stale" in lim for lim in limitations))

    def test_report_generator_agent_execution(self):
        state = create_mock_state()
        agent = ReportGeneratorAgent()
        res = agent.run(state)
        self.assertIn("report", res)
        report = res["report"]
        self.assertGreater(len(report.traceable_claims), 0)
        self.assertGreater(len(report.consolidated_findings), 0)
        self.assertEqual(report.headline, "Portfolio Executive Analysis")


if __name__ == "__main__":
    unittest.main()
