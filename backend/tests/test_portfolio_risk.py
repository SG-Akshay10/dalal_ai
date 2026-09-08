import unittest

from app.services.portfolio_risk import analyze_portfolio_risk


class PortfolioRiskAnalysisTests(unittest.TestCase):
    def analyze(self, holdings):
        return analyze_portfolio_risk(holdings, include_llm_insight=False)

    def test_concentrated_portfolio_flags_technology(self):
        result = self.analyze([
            {"ticker": "INFY", "quantity": 100, "current_price": 1500, "sector": "Information Technology", "annualized_volatility_pct": 28, "market_cap": 700_000_000_000, "beta": 1.1},
            {"ticker": "TCS", "quantity": 10, "current_price": 4000, "sector": "Information Technology", "annualized_volatility_pct": 22, "market_cap": 1_000_000_000_000},
            {"ticker": "ITC", "quantity": 10, "current_price": 400, "sector": "Consumer Goods", "annualized_volatility_pct": 18, "market_cap": 600_000_000_000},
        ])
        analysis = result["portfolio_diversification_analysis"]
        self.assertEqual(analysis["concentration_flags"][0]["sector"], "Information Technology")
        self.assertIn("Information Technology", analysis["summary_verdict"])

    def test_diversified_portfolio_has_no_concentration_flag(self):
        sectors = ["Financial Services", "Information Technology", "Healthcare", "Energy", "Utilities"]
        holdings = [{"ticker": f"STOCK{index}", "quantity": 10, "current_price": 100, "sector": sector, "annualized_volatility_pct": 20, "market_cap": 500_000_000_000} for index, sector in enumerate(sectors)]
        result = self.analyze(holdings)
        analysis = result["portfolio_diversification_analysis"]
        self.assertEqual(analysis["concentration_flags"], [])
        self.assertEqual(analysis["summary_verdict"], "Well diversified")

    def test_missing_sector_data_is_reported_without_failure(self):
        result = self.analyze([{"ticker": "UNKNOWN", "quantity": 5, "current_price": 200, "annualized_volatility_pct": 30}])
        stock = result["stock_level_risk_profiles"][0]
        diversification = result["portfolio_diversification_analysis"]
        self.assertIn("Missing sector", stock["data_quality"]["errors"])
        self.assertFalse(diversification["data_quality"]["complete"])
        self.assertIn("Healthcare", diversification["under_exposed_or_missing_sectors"])


if __name__ == "__main__":
    unittest.main()
