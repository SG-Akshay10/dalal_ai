"""Per-stock thesis agent, grounded in supplied technical data and optional headlines."""

from __future__ import annotations

from app.services.ingestion import fetch_rss_news
from app.services.sarvam import SarvamStructuredOutputError, structured_completion

from .base import AgentResult
from ..schemas import PortfolioState, STOCK_LEVEL_ANALYSIS_LIMIT, StockThesis, StockThesisFinding


class StockThesisAgent:
    name = "stock_thesis"
    prompt = """You are the Stock Thesis Subagent for an Indian equity portfolio. Using only supplied technicals, fundamentals if present, and recent news headlines, identify concrete growth drivers, decline risks, pros, and cons. Keep every phrase specific and grounded in supplied data. Use educational language only; never issue direct buy/sell instructions."""

    @staticmethod
    def fallback(holding) -> StockThesisFinding:
        technicals, growth, decline = holding.technicals, [], []
        if technicals.crossover == "bullish": growth.append("50-day moving average is above the 200-day average, a historically bullish trend signal.")
        elif technicals.crossover == "bearish": decline.append("50-day moving average is below the 200-day average, a historically bearish trend signal.")
        if (technicals.macd_histogram or 0) > 0: growth.append("MACD histogram is positive, indicating strengthening momentum.")
        elif (technicals.macd_histogram or 0) < 0: decline.append("MACD histogram is negative, indicating weakening momentum.")
        if holding.pnl_pct is not None and holding.pnl_pct >= 0: growth.append(f"Position is up {holding.pnl_pct}% from the recorded buy price.")
        elif holding.pnl_pct is not None: decline.append(f"Position is down {abs(holding.pnl_pct)}% from the recorded buy price.")
        narrative = f"{holding.ticker} ({holding.sector}): " + ("; ".join((growth + decline)[:2]) or "Limited signal available.") + " (Deterministic fallback; language model unavailable.)"
        return StockThesisFinding(ticker=holding.ticker, sector=holding.sector, growth_drivers=growth or ["No strong growth signal detected in available data."], decline_risks=decline or ["No strong decline signal detected in available data."], pros=growth[:2] or ["Insufficient data to determine pros."], cons=decline[:2] or ["Insufficient data to determine cons."], narrative=narrative)

    def run(self, state: PortfolioState, correction: str | None = None) -> AgentResult:
        if len(state.enriched_holdings) > STOCK_LEVEL_ANALYSIS_LIMIT:
            return {"stock_thesis": StockThesis(applicable=False, reason_if_not_applicable=f"Portfolio holds more than {STOCK_LEVEL_ANALYSIS_LIMIT} individual stocks; individual stock thesis is skipped in favor of sector-wide analysis.")}
        findings = []
        for holding in state.enriched_holdings:
            try: headlines = [item["title"] for item in fetch_rss_news(holding.ticker)][:8]
            except Exception: headlines = []
            payload = {"ticker": holding.ticker, "sector": holding.sector, "market_value": holding.market_value, "pnl_pct": holding.pnl_pct, "technicals": holding.technicals.model_dump(), "recent_headlines": headlines}
            try: finding = structured_completion(self.prompt, payload, StockThesisFinding, correction=correction, max_tokens=900)
            except SarvamStructuredOutputError: finding = self.fallback(holding)
            findings.append(finding)
        return {"stock_thesis": StockThesis(applicable=True, findings=findings)}


agent = StockThesisAgent()
