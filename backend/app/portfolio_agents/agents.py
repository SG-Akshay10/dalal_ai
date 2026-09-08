from __future__ import annotations

from .schemas import AssetAnalysis, AssetFinding, CriticResult, ExecutiveReport, PortfolioState, RiskAnalysis, RiskFinding, SectorAnalysis, SectorFinding
from .tools import allocation, diversification_score, enrich_holding, missing_sectors
from app.services.sarvam import text_completion

SECTOR_PROMPT = """You are the Sector Allocation Subagent for an Indian equity portfolio. Analyze only supplied figures. Identify concentration, diversification and macro sensitivities. Use educational language; never issue direct trade instructions."""
ASSET_PROMPT = """You are the Asset Technical and Fundamental Subagent. Interpret supplied technical data without inventing fundamentals. For detailed mode, every asset narrative must contain at least 100 words, describe trend, RSI/MACD, support/resistance and data limitations. Use educational language only."""
RISK_PROMPT = """You are the Risk and Laggard Diagnostic Subagent. Analyze supplied drawdown and technical data. Stop-loss levels are educational reference levels, not instructions; tax-loss observations must mention tax rules vary by jurisdiction."""
CRITIC_PROMPT = """You are a strict portfolio-report critic. Reject missing sections, unsupported claims, direct buy/sell instructions, or asset narratives below 100 words when detailed_mode is true."""
SYNTHESIS_PROMPT = """You are the Executive Report Synthesizer. Produce a concise, readable educational Indian equity portfolio report using only supplied findings. Write 4-6 short paragraphs with headings, never dump JSON, never repeat a holding list, and do not include raw input values unless they support a conclusion. Include sector, asset (only when supplied), risk discussion and multi-step non-personalized recommendations. Never give direct buy/sell instructions."""


def _is_prompt_echo(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in ("the user wants", "let me parse", "constraints:", "structure:", "holdings: empty", "i need to produce", "json dumping"))


def _safe_executive_summary(state: PortfolioState) -> str:
    sector = state.sector_analysis
    risk = state.risk_analysis
    dominant = max(sector.findings, key=lambda item: item.allocation_pct) if sector and sector.findings else None
    high_risk = sum(1 for item in (risk.findings if risk else []) if item.severity == "High")
    missing = ", ".join(sector.missing_sectors[:4]) if sector and sector.missing_sectors else "no major sectors"
    dominant_text = f"{dominant.sector} represents {dominant.allocation_pct:.1f}% of measured value, creating a concentration risk." if dominant else "Sector allocation could not be fully measured from available prices."
    return (f"Sector concentration\n{dominant_text} The portfolio should be reviewed for unintended single-sector exposure and data classification gaps.\n\n"
            f"Risk profile\nOverall risk is {risk.portfolio_risk_level.lower() if risk else 'elevated'}, with {high_risk} holding(s) flagged at high severity. Drawdown, volatility, and support levels should be monitored as educational risk indicators.\n\n"
            f"Diversification and next steps\nExposure is limited in several areas, including {missing}. Review sector weights, verify missing classifications, and document personal risk limits before making any allocation decision. This is educational analysis, not investment advice.")


def ingestion_agent(state: PortfolioState) -> dict:
    return {"enriched_holdings": [enrich_holding(item) for item in state.raw_holdings]}


def sector_agent(state: PortfolioState, correction: str | None = None) -> dict:
    values, total = allocation(state.enriched_holdings)
    findings = []
    flags = []
    for sector, value in sorted(values.items(), key=lambda item: item[1], reverse=True):
        pct = round(value / total * 100, 2) if total else 0
        level = "High" if pct >= 35 else "Medium" if pct >= 15 else "Low"
        if pct >= 35:
            flags.append(f"{sector} is {pct}% of measured portfolio value")
        findings.append(SectorFinding(sector=sector, allocation_pct=pct, market_value=round(value, 2), risk_level=level, commentary=f"{sector} represents {pct}% of measured portfolio value. Concentration and sector-specific macro sensitivity should be assessed against the investor's objectives."))
    return {"sector_analysis": SectorAnalysis(findings=findings, concentration_flags=flags, missing_sectors=missing_sectors(values, total), diversification_score=diversification_score(values, total), macro_commentary="Sector exposure is calculated from current measured market values; macro sensitivity varies with rates, commodity prices, currency, regulation, and economic growth.")}


def asset_agent(state: PortfolioState, correction: str | None = None) -> dict:
    detailed = len(state.enriched_holdings) <= 10
    if not detailed:
        return {"asset_analysis": AssetAnalysis(detailed_mode=False)}
    findings = []
    for holding in state.enriched_holdings:
        technicals = holding.technicals
        trend = technicals.crossover.title() if technicals.crossover != "unavailable" else "Unavailable"
        momentum = "Positive" if (technicals.macd_histogram or 0) > 0 else "Negative" if (technicals.macd_histogram or 0) < 0 else "Neutral"
        # This agent operates on calculated facts. Keeping it deterministic
        # prevents an LLM schema echo from blocking the entire report.
        narrative = (
            f"{holding.ticker} is classified in {holding.sector}. Its current market value is {holding.market_value if holding.market_value is not None else 'unavailable'}, with a position return of {holding.pnl_pct if holding.pnl_pct is not None else 'unavailable'}%. "
            f"The moving-average signal is {trend.lower()}, based on the 50-day and 200-day averages where history is available. RSI-14 is {technicals.rsi14 if technicals.rsi14 is not None else 'unavailable'}, while the MACD histogram is {technicals.macd_histogram if technicals.macd_histogram is not None else 'unavailable'}, indicating {momentum.lower()} momentum under this technical framework. "
            f"Recent support is {technicals.support if technicals.support is not None else 'unavailable'} and resistance is {technicals.resistance if technicals.resistance is not None else 'unavailable'}; these are observed price zones, not predictions or trading instructions. Annualized volatility is {technicals.annualized_volatility_pct if technicals.annualized_volatility_pct is not None else 'unavailable'}%, and maximum observed drawdown is {technicals.max_drawdown_pct if technicals.max_drawdown_pct is not None else 'unavailable'}%. "
            "Technical indicators can change quickly and do not capture earnings, valuation, liquidity, corporate actions, or personal financial circumstances. Review this holding alongside its portfolio weight, sector exposure, time horizon, and risk tolerance. This is educational analysis only and is not a recommendation to buy, sell, hold, or alter any position."
        )
        findings.append(AssetFinding(ticker=holding.ticker, trend=trend, momentum=momentum, support=technicals.support, resistance=technicals.resistance, narrative=narrative))
    return {"asset_analysis": AssetAnalysis(detailed_mode=True, findings=findings)}


def risk_agent(state: PortfolioState, correction: str | None = None) -> dict:
    findings = []
    for holding in state.enriched_holdings:
        drawdown = holding.technicals.max_drawdown_pct
        severity = "High" if (drawdown is not None and drawdown <= -25) or (holding.technicals.annualized_volatility_pct or 0) >= 40 else "Medium" if (drawdown is not None and drawdown <= -12) else "Low"
        findings.append(RiskFinding(ticker=holding.ticker, severity=severity, drawdown_pct=drawdown, stop_loss_reference=holding.technicals.support, tax_loss_observation="A loss may warrant recordkeeping review; tax treatment depends on jurisdiction, holding period, and investor circumstances.", commentary="This diagnostic uses observed drawdown, volatility, and support as educational risk references rather than trade instructions."))
    level = "High" if any(item.severity == "High" for item in findings) else "Medium" if any(item.severity == "Medium" for item in findings) else "Low"
    return {"risk_analysis": RiskAnalysis(findings=findings, portfolio_risk_level=level)}


def critic_agent(state: PortfolioState) -> dict:
    issues = []
    if not state.sector_analysis or not state.risk_analysis:
        issues.append("Required sector or risk analysis is missing")
    if len(state.enriched_holdings) <= 10 and any(len(item.narrative.split()) < 100 for item in (state.asset_analysis.findings if state.asset_analysis else [])):
        issues.append("An individual asset narrative is shorter than 100 words")
    return {"critic": CriticResult(passed=not issues, issues=issues)}


def synthesizer_agent(state: PortfolioState) -> dict:
    detailed = len(state.enriched_holdings) <= 10
    payload = {"portfolio_size": len(state.enriched_holdings), "holdings": [item.model_dump() for item in state.enriched_holdings] if detailed else [], "sector_analysis": state.sector_analysis.model_dump() if state.sector_analysis else None, "asset_analysis": state.asset_analysis.model_dump() if detailed and state.asset_analysis else None, "risk_analysis": state.risk_analysis.model_dump() if state.risk_analysis else None, "data_errors": [error for item in state.enriched_holdings for error in item.data_errors]}
    narrative = text_completion(SYNTHESIS_PROMPT, payload, max_tokens=2600)
    if _is_prompt_echo(narrative):
        narrative = _safe_executive_summary(state)
    sector_text = state.sector_analysis.macro_commentary if state.sector_analysis else "Sector analysis was unavailable."
    asset_text = "\n\n".join(item.narrative for item in (state.asset_analysis.findings if detailed and state.asset_analysis else []))
    risk_text = " ".join(item.commentary for item in (state.risk_analysis.findings if state.risk_analysis else []))
    return {"report": ExecutiveReport(headline="Portfolio executive analysis", executive_summary=narrative, sector_commentary=sector_text, asset_commentary=asset_text, risk_commentary=risk_text, recommendations=["Review concentration and position-size limits against personal goals.", "Monitor material changes in sector exposure, volatility, and drawdown."], disclaimer="Educational analysis only; not investment advice.")}
