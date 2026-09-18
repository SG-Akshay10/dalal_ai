"""Executive-report synthesis agent consuming only typed analysis outputs."""

from __future__ import annotations

from app.services.sarvam import text_completion

from .base import AgentResult
from ..schemas import ExecutiveReport, PortfolioState, STOCK_LEVEL_ANALYSIS_LIMIT


class SynthesisAgent:
    name = "synthesize"
    prompt = """Produce a concise, readable educational Indian equity portfolio report using only supplied findings. Include sector, asset when supplied, risk, stock thesis when supplied, sector thesis, and non-personalized recommendations. Never give direct buy/sell instructions."""

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

    def run(self, state: PortfolioState, correction: str | None = None) -> AgentResult:
        detailed = len(state.enriched_holdings) <= STOCK_LEVEL_ANALYSIS_LIMIT
        # Build a scoped holding summary: the LLM only needs identifiers,
        # position-level performance, and data-quality status to write the
        # executive narrative.  Raw technical arrays are already processed by
        # the deterministic agents (sector, asset, risk) so re-sending them
        # would only invite redundant re-interpretation.
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
        payload = {
            "portfolio_size": len(state.enriched_holdings),
            "holdings": holding_summaries,
            "sector_analysis": state.sector_analysis.model_dump() if state.sector_analysis else None,
            "asset_analysis": state.asset_analysis.model_dump() if detailed and state.asset_analysis else None,
            "technical_analysis": state.technical_analysis.model_dump() if detailed and state.technical_analysis else None,
            "risk_analysis": state.risk_analysis.model_dump() if state.risk_analysis else None,
            "stock_thesis": state.stock_thesis.model_dump() if state.stock_thesis else None,
            "sector_thesis": state.sector_thesis.model_dump() if state.sector_thesis else None,
            "fundamental_analysis": state.fundamental_analysis.model_dump() if state.fundamental_analysis else None,
            "valuation_analysis": state.valuation_analysis.model_dump() if state.valuation_analysis else None,
            "market_context_analysis": state.market_context_analysis.model_dump() if state.market_context_analysis else None,
            "evidence": [item.model_dump() for item in state.evidence if item.verified and item.quality_score >= 0.7],
            "data_errors": [error for item in state.enriched_holdings for error in item.data_errors],
        }
        narrative = text_completion(self.prompt, payload, max_tokens=2600)
        if self._is_prompt_echo(narrative): narrative = self._safe_summary(state)
        sector_text = "; ".join(f"{item.sector}: {item.allocation_pct:.1f}% ({item.risk_level.lower()} risk)" for item in state.sector_analysis.findings) + f". {state.sector_analysis.macro_commentary}" if state.sector_analysis else "Sector analysis was unavailable."
        asset_text = "\n\n".join(item.narrative for item in (state.asset_analysis.findings if detailed and state.asset_analysis else []))
        if state.risk_analysis:
            high, medium = sum(item.severity == "High" for item in state.risk_analysis.findings), sum(item.severity == "Medium" for item in state.risk_analysis.findings)
            draws = [item.drawdown_pct for item in state.risk_analysis.findings if item.drawdown_pct is not None]
            risk_text = f"{high} holding(s) are flagged high severity and {medium} medium severity, with an overall portfolio risk level of {state.risk_analysis.portfolio_risk_level.lower()}." + (f" The largest observed drawdown reference is {min(draws):.1f}%." if draws else "") + " These diagnostics use observed drawdown, volatility, and support as educational risk references rather than trade instructions."
        else: risk_text = "Risk diagnostics were unavailable."
        stock_text = "\n".join(f"{item.ticker} ({item.sector}) — Pros: {'; '.join(item.pros) or 'none identified'}. Cons: {'; '.join(item.cons) or 'none identified'}." for item in state.stock_thesis.findings) if state.stock_thesis and state.stock_thesis.applicable and state.stock_thesis.findings else (state.stock_thesis.reason_if_not_applicable if state.stock_thesis and not state.stock_thesis.applicable else "Individual stock thesis analysis was unavailable.")
        sector_thesis_text = "\n\n".join(f"{item.sector} — Growth drivers: {'; '.join(item.growth_drivers) or 'none identified'}. Headwinds: {'; '.join(item.headwinds) or 'none identified'}. Policy/geopolitical factors: {'; '.join(item.policy_geopolitical_factors) or 'none identified'}. Pros: {'; '.join(item.pros) or 'none identified'}. Cons: {'; '.join(item.cons) or 'none identified'}. {item.narrative}" for item in state.sector_thesis.findings) if state.sector_thesis and state.sector_thesis.findings else "Sector thesis analysis was unavailable."
        fundamental_text = state.fundamental_analysis.overall_summary + "\n" + "\n".join(f"{item.ticker}: {item.narrative}" for item in state.fundamental_analysis.findings) if state.fundamental_analysis and state.fundamental_analysis.applicable and state.fundamental_analysis.findings else (state.fundamental_analysis.reason_if_not_applicable if state.fundamental_analysis and not state.fundamental_analysis.applicable else "Fundamental analysis was unavailable.")
        valuation_text = state.valuation_analysis.portfolio_valuation_summary + "\n" + "\n".join(f"{item.ticker}: {item.narrative}" for item in state.valuation_analysis.findings) if state.valuation_analysis and state.valuation_analysis.applicable and state.valuation_analysis.findings else (state.valuation_analysis.reason_if_not_applicable if state.valuation_analysis and not state.valuation_analysis.applicable else "Valuation analysis was unavailable.")
        market_context_text = state.market_context_analysis.overall_market_context_summary + "\n" + "\n".join(f"{item.ticker}: {item.narrative}" for item in state.market_context_analysis.findings) if state.market_context_analysis and state.market_context_analysis.applicable and state.market_context_analysis.findings else (state.market_context_analysis.reason_if_not_applicable if state.market_context_analysis and not state.market_context_analysis.applicable else "Market context analysis was unavailable.")
        return {"report": ExecutiveReport(headline="Portfolio executive analysis", executive_summary=narrative, sector_commentary=sector_text, asset_commentary=asset_text, risk_commentary=risk_text, stock_thesis_commentary=stock_text, sector_thesis_commentary=sector_thesis_text, fundamental_commentary=fundamental_text, valuation_commentary=valuation_text, market_context_commentary=market_context_text, recommendations=["Review concentration and position-size limits against personal goals.", "Monitor material changes in sector exposure, volatility, and drawdown."], disclaimer="Educational analysis only; not investment advice.")}


agent = SynthesisAgent()
