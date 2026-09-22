import unittest
from datetime import datetime, timezone

from app.portfolio_agents import agents
from app.portfolio_agents.agent_modules.asset import AssetAgent
from app.portfolio_agents.agent_modules.technical import TechnicalAgent
from app.portfolio_agents.data import calculate_technicals
from app.portfolio_agents.schemas import (
    DataQuality,
    EnrichedHolding,
    FundamentalMetrics,
    HoldingInput,
    PortfolioState,
    Technicals,
)


def create_test_holding(
    ticker: str = "INFY",
    price: float = 1500.0,
    sma20: float = 1480.0,
    sma50: float = 1450.0,
    sma200: float = 1350.0,
    rsi14: float = 62.0,
    macd_hist: float = 4.5,
    crossover: str = "bullish",
    volume_surge: bool = True,
    vol_ratio: float = 1.6,
    support: float = 1400.0,
    resistance: float = 1550.0,
    bars: int = 200,
) -> EnrichedHolding:
    return EnrichedHolding(
        ticker=ticker,
        sector="Information Technology",
        quantity=10,
        buy_price=1400.0,
        current_price=price,
        market_value=price * 10,
        pnl_pct=7.14,
        technicals=Technicals(
            rsi14=rsi14,
            sma20=sma20,
            sma50=sma50,
            sma200=sma200,
            ema12=1490.0,
            ema26=1460.0,
            macd_line=12.5,
            macd_signal=8.0,
            macd_histogram=macd_hist,
            crossover=crossover,
            bollinger_upper=1540.0,
            bollinger_lower=1420.0,
            bollinger_bandwidth_pct=8.1,
            bollinger_squeeze=False,
            annualized_volatility_pct=22.5,
            momentum_14d_pct=4.2,
            avg_volume_20d=500000.0,
            latest_volume=800000.0,
            volume_ratio=vol_ratio,
            volume_surge=volume_surge,
            support=support,
            resistance=resistance,
            max_drawdown_pct=-8.5,
            historical_bars_count=bars,
        ),
        fundamentals=FundamentalMetrics(pe_ratio=25.0, roe_pct=20.0),
        data_quality=DataQuality(source="test", fresh=True, complete=True),
    )


class TechnicalAgentTests(unittest.TestCase):
    def test_calculate_technicals_with_expanded_metrics(self):
        """calculate_technicals computes expanded indicators including SMA20, EMAs, volume ratio, and drawdown."""
        history = [
            {"close": float(price), "volume": 100000 + (index * 2000),
             "sma20": float(price - 2), "sma50": float(price - 5), "sma200": float(price - 15),
             "ema12": float(price - 1), "ema26": float(price - 3),
             "rsi14": 50 + (index % 15), "macd": 2.0, "macd_signal": 1.0, "macd_histogram": 1.0,
             "bollinger_bandwidth_pct": 6.5, "avg_volume_20d": 100000.0}
            for index, price in enumerate(range(100, 160))
        ]
        indicators = {"sma_crossover": "bullish"}
        tech = calculate_technicals(history, indicators)

        self.assertEqual(tech.crossover, "bullish")
        self.assertEqual(tech.historical_bars_count, 60)
        self.assertIsNotNone(tech.sma20)
        self.assertIsNotNone(tech.sma50)
        self.assertIsNotNone(tech.sma200)
        self.assertIsNotNone(tech.ema12)
        self.assertIsNotNone(tech.ema26)
        self.assertIsNotNone(tech.volume_ratio)
        self.assertGreater(tech.support, 0)
        self.assertGreaterEqual(tech.resistance, tech.support)

    def test_technical_agent_pattern_detection_and_multi_indicator_analysis(self):
        """TechnicalAgent correctly detects multi-indicator patterns like Bullish Trend-Volume Confirmation."""
        holding = create_test_holding(
            ticker="TCS",
            price=3800.0,
            sma50=3700.0,
            sma200=3500.0,
            rsi14=65.0,
            macd_hist=5.0,
            crossover="bullish",
            volume_surge=True,
            vol_ratio=1.6,
        )
        state = PortfolioState(raw_holdings=[HoldingInput(ticker="TCS", quantity=5)], enriched_holdings=[holding])

        result = TechnicalAgent().run(state)
        tech_analysis = result.get("technical_analysis")

        asset_result = AssetAgent().run(state)
        asset_analysis = asset_result.get("asset_analysis")

        self.assertIsNotNone(tech_analysis)
        self.assertIsNotNone(asset_analysis)
        self.assertTrue(tech_analysis.detailed_mode)
        self.assertEqual(len(tech_analysis.findings), 1)

        finding = tech_analysis.findings[0]
        self.assertEqual(finding.ticker, "TCS")
        self.assertEqual(finding.trend, "Bullish")
        self.assertEqual(finding.momentum, "Strong Positive")
        self.assertIn("Golden Cross Moving-Average Alignment", finding.detected_patterns)
        self.assertIn("Bullish Trend-Volume Confirmation", finding.detected_patterns)

        # Ensure narrative length >= 100 words in detailed mode
        word_count = len(finding.narrative.split())
        self.assertGreaterEqual(word_count, 100)
        self.assertIn("TCS", finding.narrative)
        self.assertIn("200-bar", finding.narrative)

    def test_technical_agent_reversal_pattern(self):
        """TechnicalAgent identifies RSI oversold reversal setups."""
        holding = create_test_holding(
            ticker="HDFCBANK",
            price=1400.0,
            sma50=1500.0,
            sma200=1550.0,
            rsi14=32.0,
            macd_hist=1.2,
            crossover="bearish",
            volume_surge=False,
            vol_ratio=0.9,
            support=1390.0,
        )
        state = PortfolioState(raw_holdings=[HoldingInput(ticker="HDFCBANK", quantity=10)], enriched_holdings=[holding])

        result = agents.technical_agent(state)
        finding = result["technical_analysis"].findings[0]

        self.assertEqual(finding.ticker, "HDFCBANK")
        self.assertIn("RSI Oversold Reversal Setup", finding.detected_patterns)
        self.assertIn("Support Test & Hold Zone", finding.detected_patterns)

    def test_technical_agent_large_portfolio_summary_mode(self):
        """Portfolios with >20 holdings switch to summary mode."""
        holdings = [create_test_holding(ticker=f"STOCK{i}") for i in range(22)]
        state = PortfolioState(
            raw_holdings=[HoldingInput(ticker=f"STOCK{i}", quantity=1) for i in range(22)],
            enriched_holdings=holdings,
        )
        result = TechnicalAgent().run(state)
        tech_analysis = result["technical_analysis"]

        self.assertFalse(tech_analysis.detailed_mode)
        self.assertEqual(len(tech_analysis.findings), 0)
        self.assertIn(">20 holdings", tech_analysis.summary)


if __name__ == "__main__":
    unittest.main()
