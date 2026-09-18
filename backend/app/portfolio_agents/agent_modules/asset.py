"""Deterministic per-holding technical narrative agent."""

from __future__ import annotations

from .base import AgentResult
from ..schemas import AssetAnalysis, AssetFinding, PortfolioState, STOCK_LEVEL_ANALYSIS_LIMIT


class AssetAgent:
    name = "asset"
    prompt = """You are the Asset Technical and Fundamental Subagent. Interpret supplied technical data without inventing fundamentals. For detailed mode, every asset narrative must contain at least 100 words, describe trend, RSI/MACD, support/resistance and data limitations. Use educational language only."""

    def run(self, state: PortfolioState, correction: str | None = None) -> AgentResult:
        detailed = len(state.enriched_holdings) <= STOCK_LEVEL_ANALYSIS_LIMIT
        if not detailed:
            return {"asset_analysis": AssetAnalysis(detailed_mode=False)}
        findings = []
        for holding in state.enriched_holdings:
            technicals = holding.technicals
            trend = technicals.crossover.title() if technicals.crossover != "unavailable" else "Unavailable"
            momentum = "Positive" if (technicals.macd_histogram or 0) > 0 else "Negative" if (technicals.macd_histogram or 0) < 0 else "Neutral"
            narrative = (f"{holding.ticker} is classified in {holding.sector}. Its current market value is {holding.market_value if holding.market_value is not None else 'unavailable'}, with a position return of {holding.pnl_pct if holding.pnl_pct is not None else 'unavailable'}%. " f"The moving-average signal is {trend.lower()}, based on the 50-day and 200-day averages where history is available. RSI-14 is {technicals.rsi14 if technicals.rsi14 is not None else 'unavailable'}, while the MACD histogram is {technicals.macd_histogram if technicals.macd_histogram is not None else 'unavailable'}, indicating {momentum.lower()} momentum under this technical framework. " f"Recent support is {technicals.support if technicals.support is not None else 'unavailable'} and resistance is {technicals.resistance if technicals.resistance is not None else 'unavailable'}; these are observed price zones, not predictions or trading instructions. Annualized volatility is {technicals.annualized_volatility_pct if technicals.annualized_volatility_pct is not None else 'unavailable'}%, and maximum observed drawdown is {technicals.max_drawdown_pct if technicals.max_drawdown_pct is not None else 'unavailable'}%. " "Technical indicators can change quickly and do not capture earnings, valuation, liquidity, corporate actions, or personal financial circumstances. Review this holding alongside its portfolio weight, sector exposure, time horizon, and risk tolerance. This is educational analysis only and is not a recommendation to buy, sell, hold, or alter any position.")
            findings.append(AssetFinding(ticker=holding.ticker, trend=trend, momentum=momentum, support=technicals.support, resistance=technicals.resistance, narrative=narrative))
        return {"asset_analysis": AssetAnalysis(detailed_mode=True, findings=findings)}


agent = AssetAgent()
