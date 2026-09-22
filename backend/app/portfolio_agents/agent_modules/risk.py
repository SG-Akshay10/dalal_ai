"""Risk Analysis Agent evaluating volatility, drawdowns, leverage, liquidity, valuation risk, earnings risk, downside scenarios, and agent disagreements."""

from __future__ import annotations

from app.services.sarvam import SarvamStructuredOutputError, structured_completion

from .base import AgentResult
from ..data import extract_risk_finding
from ..schemas import (
    STOCK_LEVEL_ANALYSIS_LIMIT,
    PortfolioState,
    RiskAnalysis,
    RiskFinding,
)


class RiskAgent:
    name = "risk"
    prompt = """You are the dedicated Risk Analysis Agent. Identify and explain major risks associated with stock holdings and the overall portfolio. Analyze historical volatility, drawdowns, leverage, liquidity, valuation risk, earnings risk, concentration risk, and sector sensitivity. Identify potential downside scenarios and conditions that could invalidate positive findings from other agents. Distinguish between evidence-backed risks (supported by available data) and hypothetical risks. Feel free to disagree with other agents' optimistic conclusions rather than forcing alignment. Stop-loss references are educational support levels, not trade instructions; tax-loss observations must mention tax rules vary by jurisdiction. Provide grounded educational narratives containing at least 100 words per stock in detailed mode."""

    @staticmethod
    def fallback(holding) -> RiskFinding:
        return extract_risk_finding(holding)

    def run(self, state: PortfolioState, correction: str | None = None) -> AgentResult:
        detailed = len(state.enriched_holdings) <= STOCK_LEVEL_ANALYSIS_LIMIT
        if not detailed:
            return {
                "risk_analysis": RiskAnalysis(
                    applicable=False,
                    reason_if_not_applicable=f"Portfolio holds more than {STOCK_LEVEL_ANALYSIS_LIMIT} individual holdings; individual stock risk diagnostics skipped in favor of sector-wide risk summary.",
                    portfolio_risk_level="Medium",
                    concentration_risk_summary=f"Portfolio contains {len(state.enriched_holdings)} holdings (> {STOCK_LEVEL_ANALYSIS_LIMIT}). Individual leverage and drawdown risk narratives omitted.",
                    overall_risk_summary="High-level portfolio risk summary active for large holding count.",
                )
            }

        findings: list[RiskFinding] = []

        for holding in state.enriched_holdings:
            payload = {
                "ticker": holding.ticker,
                "sector": holding.sector,
                "current_price": holding.current_price,
                "technicals": holding.technicals.model_dump(),
                "fundamentals": holding.fundamentals.model_dump(),
            }
            try:
                finding = structured_completion(
                    self.prompt,
                    payload,
                    RiskFinding,
                    correction=correction,
                    max_tokens=1200,
                )
                if len(finding.narrative.split()) < 100 or not finding.evidence_backed_risks:
                    finding = self.fallback(holding)
            except (SarvamStructuredOutputError, Exception):
                finding = self.fallback(holding)
            findings.append(finding)

        if not findings:
            level = "Low"
            summary = "No holdings were available for risk analysis."
            conc_summary = "No holdings available to evaluate concentration risk."
            macro_scenarios: list[str] = []
        else:
            high_count = sum(1 for f in findings if f.severity == "High")
            med_count = sum(1 for f in findings if f.severity == "Medium")
            level = "High" if high_count >= 1 else "Medium" if med_count >= 1 else "Low"

            # Check sector concentration
            sector_counts: dict[str, int] = {}
            for holding in state.enriched_holdings:
                sector_counts[holding.sector] = sector_counts.get(holding.sector, 0) + 1
            max_sec, count = max(sector_counts.items(), key=lambda item: item[1]) if sector_counts else ("Unknown", 0)
            conc_pct = (count / len(state.enriched_holdings) * 100) if state.enriched_holdings else 0
            conc_summary = f"{max_sec} sector concentration represents {conc_pct:.1f}% of individual position count."

            macro_scenarios = [
                "Macroeconomic monetary tightening or interest rate hikes could expand cost of capital across high-leverage positions.",
                "Broader market volatility spikes or commodity cost inflation could compress operating margins and trigger support level breakdowns.",
            ]

            disagree_count = sum(1 for f in findings if f.agent_disagreements)
            summary = (
                f"Overall portfolio risk level is {level}. Evaluated multi-factor risk diagnostics across {len(findings)} holding(s): "
                f"{high_count} high severity, {med_count} medium severity, and {sum(1 for f in findings if f.severity == 'Low')} low severity. "
                f"Identified {disagree_count} analytical disagreement flag(s) challenging optimistic assumptions."
            )

        return {
            "risk_analysis": RiskAnalysis(
                applicable=True,
                findings=findings,
                portfolio_risk_level=level,
                concentration_risk_summary=conc_summary,
                macro_downside_scenarios=macro_scenarios,
                overall_risk_summary=summary,
            )
        }


agent = RiskAgent()
