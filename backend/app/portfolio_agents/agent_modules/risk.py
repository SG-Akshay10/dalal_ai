"""Deterministic drawdown and volatility diagnostic agent."""

from __future__ import annotations

from .base import AgentResult
from ..schemas import PortfolioState, RiskAnalysis, RiskFinding


class RiskAgent:
    name = "risk"
    prompt = """You are the Risk and Laggard Diagnostic Subagent. Analyze supplied drawdown and technical data. Stop-loss levels are educational reference levels, not instructions; tax-loss observations must mention tax rules vary by jurisdiction."""

    def run(self, state: PortfolioState, correction: str | None = None) -> AgentResult:
        findings = []
        for holding in state.enriched_holdings:
            drawdown = holding.technicals.max_drawdown_pct
            severity = "High" if (drawdown is not None and drawdown <= -25) or (holding.technicals.annualized_volatility_pct or 0) >= 40 else "Medium" if (drawdown is not None and drawdown <= -12) else "Low"
            findings.append(RiskFinding(ticker=holding.ticker, severity=severity, drawdown_pct=drawdown, stop_loss_reference=holding.technicals.support, tax_loss_observation="A loss may warrant recordkeeping review; tax treatment depends on jurisdiction, holding period, and investor circumstances.", commentary="This diagnostic uses observed drawdown, volatility, and support as educational risk references rather than trade instructions."))
        level = "High" if any(item.severity == "High" for item in findings) else "Medium" if any(item.severity == "Medium" for item in findings) else "Low"
        return {"risk_analysis": RiskAnalysis(findings=findings, portfolio_risk_level=level)}


agent = RiskAgent()
