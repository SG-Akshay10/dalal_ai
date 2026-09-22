import unittest

from app.portfolio_agents.agent_modules.critic import CriticAgent
from app.portfolio_agents.data.critic import evaluate_critic_rules
from app.portfolio_agents.data.fundamental import extract_fundamental_finding
from app.portfolio_agents.data.market_context import extract_market_context_finding
from app.portfolio_agents.data.risk import extract_risk_finding
from app.portfolio_agents.data.valuation import extract_valuation_finding
from app.portfolio_agents.schemas import (
    AssetAnalysis,
    AssetFinding,
    CriticResult,
    DataQuality,
    EnrichedHolding,
    EvidenceRecord,
    FundamentalAnalysis,
    FundamentalMetrics,
    MarketContextAnalysis,
    PortfolioState,
    RiskAnalysis,
    SectorAnalysis,
    SectorFinding,
    SectorThesis,
    SectorThesisFinding,
    TechnicalAnalysis,
    TechnicalFinding,
    Technicals,
    ValuationAnalysis,
)


def sample_enriched_holding(ticker="INFY", vol=20.0, pe=25.0, benchmark_pe=25.0, smas=(1450.0, 1400.0)):
    return EnrichedHolding(
        ticker=ticker,
        sector="Information Technology",
        quantity=10,
        buy_price=1400.0,
        current_price=1500.0,
        market_value=15000.0,
        pnl_pct=7.14,
        technicals=Technicals(
            rsi14=55.0,
            sma50=smas[0],
            sma200=smas[1],
            crossover="bullish",
            annualized_volatility_pct=vol,
            max_drawdown_pct=-10.0,
            support=1400.0,
            resistance=1600.0,
        ),
        fundamentals=FundamentalMetrics(
            pe_ratio=pe,
            benchmark_pe=benchmark_pe,
            roe_pct=22.0,
            earnings_growth_pct=15.0,
            free_cash_flow=5000000.0,
        ),
        data_quality=DataQuality(source="client-supplied", fresh=True, complete=True),
    )


def sample_valid_state():
    holding = sample_enriched_holding()
    long_narrative = "Sample long narrative paragraph for critic validation testing. " * 15
    return PortfolioState(
        raw_holdings=[],
        enriched_holdings=[holding],
        sector_analysis=SectorAnalysis(
            findings=[SectorFinding(sector="Information Technology", allocation_pct=100.0, market_value=15000.0, risk_level="Low", commentary="Dominant sector exposure")],
            diversification_score=0.1,
            macro_commentary="High concentration in IT",
        ),
        asset_analysis=AssetAnalysis(detailed_mode=True, findings=[AssetFinding(ticker="INFY", trend="Bullish", momentum="Neutral", narrative=long_narrative)]),
        technical_analysis=TechnicalAnalysis(detailed_mode=True, findings=[TechnicalFinding(ticker="INFY", trend="Bullish", momentum="Neutral", volatility_assessment="Low", volume_assessment="Average", narrative=long_narrative)]),
        risk_analysis=RiskAnalysis(applicable=True, findings=[extract_risk_finding(holding)]),
        sector_thesis=SectorThesis(findings=[SectorThesisFinding(sector="Information Technology", narrative=long_narrative)]),
        fundamental_analysis=FundamentalAnalysis(applicable=True, findings=[extract_fundamental_finding(holding)]),
        valuation_analysis=ValuationAnalysis(applicable=True, findings=[extract_valuation_finding(holding)]),
        market_context_analysis=MarketContextAnalysis(applicable=True, findings=[extract_market_context_finding(holding)]),
    )


class CriticAgentUnitTests(unittest.TestCase):
    def test_valid_portfolio_passes_critic(self):
        state = sample_valid_state()
        result = evaluate_critic_rules(state)
        self.assertTrue(result.passed)
        self.assertEqual(len(result.issues), 0)

    def test_missing_required_analysis_fails_critic(self):
        state = sample_valid_state()
        state.sector_analysis = None
        result = evaluate_critic_rules(state)
        self.assertFalse(result.passed)
        self.assertTrue(any("Required sector or risk analysis is missing" in issue for issue in result.issues))

    def test_excessive_confidence_detection(self):
        state = sample_valid_state()
        # Mark data incomplete but set high confidence
        state.enriched_holdings[0].data_quality.complete = False
        state.fundamental_analysis.findings[0].evidence.confidence_score = 0.95
        result = evaluate_critic_rules(state)
        self.assertFalse(result.passed)
        self.assertTrue(len(result.excessive_confidence) > 0)
        self.assertIn("INFY", result.excessive_confidence[0])

    def test_calculation_issues_detection(self):
        state = sample_valid_state()
        # Trend Bullish but SMA50 far below SMA200
        state.enriched_holdings[0].technicals.sma50 = 1000.0
        state.enriched_holdings[0].technicals.sma200 = 1500.0
        result = evaluate_critic_rules(state)
        self.assertFalse(result.passed)
        self.assertTrue(len(result.calculation_issues) > 0)
        self.assertIn("SMA50", result.calculation_issues[0])

    def test_overlooked_risk_detection(self):
        state = sample_valid_state()
        # High volatility but severity rated Low
        state.enriched_holdings[0].technicals.annualized_volatility_pct = 48.0
        state.risk_analysis.findings[0].severity = "Low"
        result = evaluate_critic_rules(state)
        self.assertFalse(result.passed)
        self.assertTrue(len(result.overlooked_risks) > 0)
        self.assertIn("volatility", result.overlooked_risks[0])

    def test_critic_agent_module_wrapper(self):
        state = sample_valid_state()
        res_dict = CriticAgent().run(state)
        self.assertIn("critic", res_dict)
        self.assertIsInstance(res_dict["critic"], CriticResult)
        self.assertTrue(res_dict["critic"].passed)


if __name__ == "__main__":
    unittest.main()
