"""Deterministic Technical Analysis Agent evaluating multi-indicator technical patterns."""

from __future__ import annotations

from typing import Literal
from .base import AgentResult
from ..schemas import (
    AnalyticalEvidence,
    PortfolioState,
    STOCK_LEVEL_ANALYSIS_LIMIT,
    TechnicalAnalysis,
    TechnicalFinding,
)


class TechnicalAgent:
    name = "technical"
    prompt = """You are the dedicated Technical Analysis Agent. Interpret price, volume, momentum, volatility, and trend information deterministically. Evaluate combinations of indicators (trend + volume, RSI + MACD reversal, Bollinger squeeze breakout) and provide grounded educational narratives containing at least 100 words per stock in detailed mode."""

    @staticmethod
    def _evaluate_trend(price: float | None, sma50: float | None, sma200: float | None, crossover: str, squeeze: bool) -> Literal["Bullish", "Bearish", "Neutral", "Consolidating"]:
        if squeeze:
            return "Consolidating"
        if price is not None and sma50 is not None and sma200 is not None:
            if price >= sma50 >= sma200 or crossover == "bullish":
                return "Bullish"
            if price <= sma50 <= sma200 or crossover == "bearish":
                return "Bearish"
        if crossover == "bullish":
            return "Bullish"
        if crossover == "bearish":
            return "Bearish"
        return "Neutral"

    @staticmethod
    def _evaluate_momentum(rsi14: float | None, macd_hist: float | None, mom14: float | None) -> Literal["Strong Positive", "Weak Positive", "Neutral", "Weak Negative", "Strong Negative"]:
        rsi = rsi14 if rsi14 is not None else 50.0
        hist = macd_hist if macd_hist is not None else 0.0
        mom = mom14 if mom14 is not None else 0.0

        if rsi >= 60 and hist > 0 and mom >= 2.0:
            return "Strong Positive"
        if hist > 0 or rsi >= 55 or mom > 0:
            return "Weak Positive"
        if rsi <= 40 and hist < 0 and mom <= -2.0:
            return "Strong Negative"
        if hist < 0 or rsi <= 45 or mom < 0:
            return "Weak Negative"
        return "Neutral"

    @staticmethod
    def _evaluate_volatility(vol_pct: float | None, squeeze: bool, bw_pct: float | None) -> str:
        if squeeze:
            return "Bollinger Squeeze (Breakout Setup)"
        if vol_pct is not None:
            if vol_pct >= 35.0:
                return "High Volatility"
            if vol_pct <= 15.0:
                return "Low Volatility"
            return f"Moderate Volatility ({vol_pct:.1f}%)"
        if bw_pct is not None:
            return f"Bandwidth {bw_pct:.1f}%"
        return "Normal Volatility"

    @staticmethod
    def _evaluate_volume(vol_surge: bool, vol_ratio: float | None) -> str:
        if vol_surge or (vol_ratio is not None and vol_ratio >= 1.5):
            return f"Unusual Volume Surge ({vol_ratio:.2f}x 20d avg)"
        if vol_ratio is not None and vol_ratio >= 1.2:
            return f"High Volume Expansion ({vol_ratio:.2f}x 20d avg)"
        if vol_ratio is not None and vol_ratio <= 0.6:
            return f"Low Volume Dry-up ({vol_ratio:.2f}x 20d avg)"
        return "Normal Volume Activity"

    def _detect_patterns(
        self,
        trend: str,
        momentum: str,
        crossover: str,
        rsi14: float | None,
        macd_hist: float | None,
        vol_surge: bool,
        squeeze: bool,
        price: float | None,
        support: float | None,
        resistance: float | None,
        vol_ratio: float | None,
    ) -> list[str]:
        patterns = []
        if crossover == "bullish":
            patterns.append("Golden Cross Moving-Average Alignment")
        elif crossover == "bearish":
            patterns.append("Death Cross Moving-Average Alignment")

        if rsi14 is not None and rsi14 <= 35 and (macd_hist or 0) >= 0:
            patterns.append("RSI Oversold Reversal Setup")
        elif rsi14 is not None and rsi14 >= 70 and (macd_hist or 0) <= 0:
            patterns.append("RSI Overbought Exhaustion Signal")

        if squeeze:
            patterns.append("Bollinger Band Contraction / Volatility Squeeze")

        if vol_surge and resistance is not None and price is not None and price >= resistance * 0.98:
            patterns.append("Volume-Backed Resistance Breakout")
        elif vol_surge and support is not None and price is not None and price <= support * 1.02:
            patterns.append("Volume-Backed Support Breakdown")

        if trend == "Bullish" and vol_ratio is not None and vol_ratio >= 1.2:
            patterns.append("Bullish Trend-Volume Confirmation")

        if price is not None and support is not None and abs(price - support) / support <= 0.02:
            patterns.append("Support Test & Hold Zone")
        if price is not None and resistance is not None and abs(price - resistance) / resistance <= 0.02:
            patterns.append("Resistance Testing Zone")

        if not patterns:
            patterns.append("Consolidation Range-Bound Pattern")

        return patterns

    def run(self, state: PortfolioState, correction: str | None = None) -> AgentResult:
        detailed = len(state.enriched_holdings) <= STOCK_LEVEL_ANALYSIS_LIMIT
        if not detailed:
            tech_res = TechnicalAnalysis(detailed_mode=False, summary="Portfolio contains >20 holdings; individual technical analysis skipped in favor of sector analysis.")
            return {"technical_analysis": tech_res}

        tech_findings: list[TechnicalFinding] = []

        for holding in state.enriched_holdings:
            t = holding.technicals
            price = holding.current_price
            bars = t.historical_bars_count or 60

            trend = self._evaluate_trend(price, t.sma50, t.sma200, t.crossover, t.bollinger_squeeze)
            momentum = self._evaluate_momentum(t.rsi14, t.macd_histogram, t.momentum_14d_pct)
            vol_eval = self._evaluate_volatility(t.annualized_volatility_pct, t.bollinger_squeeze, t.bollinger_bandwidth_pct)
            vol_act = self._evaluate_volume(t.volume_surge, t.volume_ratio)
            patterns = self._detect_patterns(
                trend, momentum, t.crossover, t.rsi14, t.macd_histogram,
                t.volume_surge, t.bollinger_squeeze, price, t.support, t.resistance, t.volume_ratio
            )

            rsi_str = f"{t.rsi14:.1f}" if t.rsi14 is not None else "unavailable"
            macd_hist_str = f"{t.macd_histogram:.2f}" if t.macd_histogram is not None else "unavailable"
            sma50_str = f"₹{t.sma50:.2f}" if t.sma50 is not None else "unavailable"
            sma200_str = f"₹{t.sma200:.2f}" if t.sma200 is not None else "unavailable"
            vol_ratio_str = f"{t.volume_ratio:.2f}x" if t.volume_ratio is not None else "normal"
            volatility_str = f"{t.annualized_volatility_pct:.1f}%" if t.annualized_volatility_pct is not None else "unavailable"
            drawdown_str = f"{t.max_drawdown_pct:.1f}%" if t.max_drawdown_pct is not None else "unavailable"
            support_str = f"₹{t.support:.2f}" if t.support is not None else "unavailable"
            resistance_str = f"₹{t.resistance:.2f}" if t.resistance is not None else "unavailable"
            pattern_str = ", ".join(patterns)

            narrative = (
                f"{holding.ticker} is evaluated across a {bars}-bar daily historical timeframe in the {holding.sector} sector. "
                f"The current stock price of {f'₹{price:.2f}' if price is not None else 'unavailable'} displays a {trend.lower()} technical trend alignment, "
                f"with the 50-day moving average standing at {sma50_str} and the 200-day moving average at {sma200_str}, yielding a {t.crossover} moving-average signal. "
                f"Momentum evaluation reveals {momentum.lower()} strength: the 14-period Relative Strength Index (RSI-14) is {rsi_str} and the MACD histogram measures {macd_hist_str}. "
                f"Volume behavior reflects {vol_act.lower()}, registering a 20-day volume ratio of {vol_ratio_str}. "
                f"Volatility dynamics indicate {vol_eval.lower()} with an annualized volatility of {volatility_str} and a peak historical drawdown of {drawdown_str}. "
                f"Key chart boundaries are identified at support of {support_str} and resistance of {resistance_str}. "
                f"Multi-indicator combination analysis highlights key technical patterns including: {pattern_str}. "
                f"These technical metrics represent historical price, volume, and volatility calculations rather than forward-looking price predictions. "
                f"Investors should evaluate these signals alongside fundamental health, sector trends, and personal risk parameters. Educational technical analysis only; not investment advice."
            )

            evidence_payload = AnalyticalEvidence(
                supporting_metrics={
                    "rsi14": t.rsi14,
                    "macd_histogram": t.macd_histogram,
                    "sma50": t.sma50,
                    "sma200": t.sma200,
                    "volume_ratio": t.volume_ratio,
                    "annualized_volatility_pct": t.annualized_volatility_pct,
                    "max_drawdown_pct": t.max_drawdown_pct,
                },
                historical_observations=patterns,
                comparisons={"sma_crossover": t.crossover},
                confidence_score=0.90 if holding.data_quality.fresh and holding.data_quality.complete else 0.70,
                data_quality_rating="High" if holding.data_quality.complete else "Medium",
                limitations=["Technical indicators reflect past price action and cannot foresee sudden corporate or news announcements."],
                missing_information=[k for k, v in {"rsi14": t.rsi14, "sma50": t.sma50, "sma200": t.sma200}.items() if v is None],
                interpretation=narrative,
            )

            tech_findings.append(
                TechnicalFinding(
                    ticker=holding.ticker,
                    trend=trend,
                    momentum=momentum,
                    volatility_assessment=vol_eval,
                    volume_assessment=vol_act,
                    support=t.support,
                    resistance=t.resistance,
                    detected_patterns=patterns,
                    narrative=narrative,
                    evidence=evidence_payload,
                )
            )

        summary_text = f"Technical analysis complete for {len(tech_findings)} asset(s). Evaluated trend, momentum, volatility, volume, and multi-indicator patterns."
        return {
            "technical_analysis": TechnicalAnalysis(detailed_mode=True, findings=tech_findings, summary=summary_text),
        }


agent = TechnicalAgent()
