"""Dedicated Report Generator agent for Phase 14.

Separates analytical reasoning from final presentation by consuming all upstream state
(including synthesis & scenarios) and generating the structured ExecutiveReport.
"""

from __future__ import annotations

from app.services.sarvam import text_completion

from .base import AgentResult
from ..data.report import build_executive_report_data
from ..schemas import PortfolioState, STOCK_LEVEL_ANALYSIS_LIMIT


class ReportGeneratorAgent:
    name = "report_generator"
    prompt = """Produce a comprehensive, highly readable educational Indian equity portfolio executive report using only supplied findings and structured evidence payloads. Summarize key insights across fundamental, technical, valuation, market context, risk, synthesis, and scenario dimensions. Never offer direct buy/sell instructions."""

    @staticmethod
    def _is_prompt_echo(text: str) -> bool:
        return any(marker in text.lower() for marker in ("the user wants", "let me parse", "constraints:", "structure:", "holdings: empty", "i need to produce", "json dumping"))

    @staticmethod
    def _safe_summary(state: PortfolioState) -> str:
        sector, risk = state.sector_analysis, state.risk_analysis
        dominant = max(sector.findings, key=lambda item: item.allocation_pct) if sector and sector.findings else None
        high_risk = sum(1 for item in (risk.findings if risk else []) if item.severity == "High")
        missing = ", ".join(sector.missing_sectors[:4]) if sector and sector.missing_sectors else "no major sectors"
        dominant_text = f"{dominant.sector} represents {dominant.allocation_pct:.1f}% of measured value, creating a concentration risk." if dominant else "Sector allocation could not be fully measured from available prices."
        return f"Sector concentration\n{dominant_text} The portfolio should be reviewed for unintended single-sector exposure and data classification gaps.\n\nRisk profile\nOverall risk is {risk.portfolio_risk_level.lower() if risk else 'elevated'}, with {high_risk} holding(s) flagged at high severity.\n\nDiversification and next steps\nExposure is limited in several areas, including {missing}. Review sector weights and document personal risk limits before making any allocation decision. This is educational analysis, not investment advice."

    @staticmethod
    def _prune(obj: Any) -> Any:
        if obj is None:
            return None
        dump = obj.model_dump() if hasattr(obj, "model_dump") else obj
        if isinstance(dump, dict):
            pruned = {}
            for k, v in dump.items():
                if k in ("evidence", "historical_prices", "raw_bars", "price_history"):
                    continue
                if isinstance(v, list):
                    pruned[k] = [ReportGeneratorAgent._prune(item) for item in v[:20]]
                elif isinstance(v, dict):
                    pruned[k] = ReportGeneratorAgent._prune(v)
                else:
                    pruned[k] = v
            return pruned
        return dump

    def run(self, state: PortfolioState, correction: str | None = None) -> AgentResult:
        detailed = len(state.enriched_holdings) <= STOCK_LEVEL_ANALYSIS_LIMIT
        holding_summaries = [
            {
                "ticker": item.ticker,
                "sector": item.sector,
                "market_value": item.market_value,
                "pnl_pct": item.pnl_pct,
                "data_quality": {
                    "fresh": item.data_quality.fresh,
                    "complete": item.data_quality.complete,
                    "source": item.data_quality.source,
                    "missing_fields": item.data_quality.missing_fields,
                },
            }
            for item in state.enriched_holdings
        ] if detailed else []

        synthesis_dump = self._prune(state.report.synthesis) if (state.report and state.report.synthesis) else None

        payload = {
            "portfolio_size": len(state.enriched_holdings),
            "holdings": holding_summaries,
            "sector_analysis": self._prune(state.sector_analysis),
            "asset_analysis": self._prune(state.asset_analysis) if detailed else None,
            "technical_analysis": self._prune(state.technical_analysis) if detailed else None,
            "risk_analysis": self._prune(state.risk_analysis),
            "stock_thesis": self._prune(state.stock_thesis),
            "sector_thesis": self._prune(state.sector_thesis),
            "fundamental_analysis": self._prune(state.fundamental_analysis),
            "valuation_analysis": self._prune(state.valuation_analysis),
            "market_context_analysis": self._prune(state.market_context_analysis),
            "scenario_analysis": self._prune(state.scenario_analysis),
            "synthesis": synthesis_dump,
            "evidence": [item.model_dump() for item in state.evidence if item.verified and item.quality_score >= 0.7][:10],
            "data_errors": [error for item in state.enriched_holdings for error in item.data_errors],
        }

        narrative = text_completion(self.prompt, payload, max_tokens=2800)
        if self._is_prompt_echo(narrative):
            narrative = self._safe_summary(state)

        report = build_executive_report_data(state, narrative)
        return {"report": report}



agent = ReportGeneratorAgent()
