from __future__ import annotations

from .schemas import (
    AssetAnalysis, AssetFinding, CriticResult, ExecutiveReport, PortfolioState,
    RiskAnalysis, RiskFinding, SectorAnalysis, SectorFinding,
    SectorThesis, SectorThesisFinding, StockThesis, StockThesisFinding,
    STOCK_LEVEL_ANALYSIS_LIMIT,
)
from .tools import allocation, diversification_score, enrich_holding, missing_sectors
from app.services.ingestion import fetch_rss_news, fetch_sector_news
from app.services.sarvam import SarvamStructuredOutputError, structured_completion, text_completion

SECTOR_PROMPT = """You are the Sector Allocation Subagent for an Indian equity portfolio. Analyze only supplied figures. Identify concentration, diversification and macro sensitivities. Use educational language; never issue direct trade instructions."""
ASSET_PROMPT = """You are the Asset Technical and Fundamental Subagent. Interpret supplied technical data without inventing fundamentals. For detailed mode, every asset narrative must contain at least 100 words, describe trend, RSI/MACD, support/resistance and data limitations. Use educational language only."""
RISK_PROMPT = """You are the Risk and Laggard Diagnostic Subagent. Analyze supplied drawdown and technical data. Stop-loss levels are educational reference levels, not instructions; tax-loss observations must mention tax rules vary by jurisdiction."""
STOCK_THESIS_PROMPT = """You are the Stock Thesis Subagent for an Indian equity portfolio. Using only the supplied technicals, fundamentals (PE/D-E if present), and recent news headlines, identify concrete pros and cons for the stock: pros are reasons it could grow (momentum/trend signals, positive headline themes such as strong earnings, contract wins, favorable guidance), cons are reasons it could decline (negative momentum, guidance cuts, regulatory action, management changes, macro exposure). Populate growth_drivers, decline_risks, pros, and cons as short, specific bullet phrases (each under 15 words) grounded only in the supplied data. Keep narrative brief: one or two sentences (under 40 words) summarizing the overall picture, since pros/cons are the primary output. Do not fabricate news not supplied. Use educational language only; never issue direct buy/sell instructions."""
SECTOR_THESIS_PROMPT = """You are the Sector Thesis Subagent for Indian equities. Using only the supplied sector holdings summary and recent sector-level news headlines, write a detailed explanation of why the sector is showing (or not showing) growth, citing concrete drivers referenced in the headlines such as government policy, geopolitics, global demand, input costs, regulation, or company profit/loss trends. Populate growth_drivers, headwinds, and policy_geopolitical_factors with specific, well-reasoned bullet phrases citing the headline themes. Then list pros and cons of the industry generally. Write a thorough narrative of at least 120 words synthesizing the drivers, headwinds, and policy/geopolitical context in detail. Use educational language only; never issue direct buy/sell instructions."""
CRITIC_PROMPT = """You are a strict portfolio-report critic. Reject missing sections, unsupported claims, direct buy/sell instructions, or asset narratives below 100 words when detailed_mode is true."""
SYNTHESIS_PROMPT = """You are the Executive Report Synthesizer. Produce a concise, readable educational Indian equity portfolio report using only supplied findings. Write short paragraphs with headings, never dump JSON, never repeat a holding list, and do not include raw input values unless they support a conclusion. Include sector, asset (only when supplied), risk, stock thesis (only when supplied), sector thesis, and multi-step non-personalized recommendations. Never give direct buy/sell instructions."""


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
    detailed = len(state.enriched_holdings) <= STOCK_LEVEL_ANALYSIS_LIMIT
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


def _deterministic_stock_finding(holding) -> StockThesisFinding:
    technicals = holding.technicals
    growth: list[str] = []
    decline: list[str] = []
    if technicals.crossover == "bullish":
        growth.append("50-day moving average is above the 200-day average, a historically bullish trend signal.")
    elif technicals.crossover == "bearish":
        decline.append("50-day moving average is below the 200-day average, a historically bearish trend signal.")
    if (technicals.macd_histogram or 0) > 0:
        growth.append("MACD histogram is positive, indicating strengthening momentum.")
    elif (technicals.macd_histogram or 0) < 0:
        decline.append("MACD histogram is negative, indicating weakening momentum.")
    if holding.pnl_pct is not None and holding.pnl_pct >= 0:
        growth.append(f"Position is up {holding.pnl_pct}% from the recorded buy price.")
    elif holding.pnl_pct is not None:
        decline.append(f"Position is down {abs(holding.pnl_pct)}% from the recorded buy price.")
    narrative = (
        f"{holding.ticker} ({holding.sector}): " + ("; ".join((growth + decline)[:2]) or "Limited signal available.") +
        " (Deterministic fallback; language model unavailable.)"
    )
    return StockThesisFinding(
        ticker=holding.ticker, sector=holding.sector,
        growth_drivers=growth or ["No strong growth signal detected in available data."],
        decline_risks=decline or ["No strong decline signal detected in available data."],
        pros=growth[:2] or ["Insufficient data to determine pros."],
        cons=decline[:2] or ["Insufficient data to determine cons."],
        narrative=narrative,
    )


def stock_thesis_agent(state: PortfolioState, correction: str | None = None) -> dict:
    # Independent of sector/asset/risk agents: only depends on ingestion output.
    if len(state.enriched_holdings) > STOCK_LEVEL_ANALYSIS_LIMIT:
        return {"stock_thesis": StockThesis(applicable=False, reason_if_not_applicable=f"Portfolio holds more than {STOCK_LEVEL_ANALYSIS_LIMIT} individual stocks; individual stock thesis is skipped in favor of sector-wide analysis.")}
    findings = []
    for holding in state.enriched_holdings:
        try:
            headlines = [item["title"] for item in fetch_rss_news(holding.ticker)][:8]
        except Exception:
            headlines = []
        payload = {"ticker": holding.ticker, "sector": holding.sector, "market_value": holding.market_value, "pnl_pct": holding.pnl_pct, "technicals": holding.technicals.model_dump(), "recent_headlines": headlines}
        try:
            finding = structured_completion(STOCK_THESIS_PROMPT, payload, StockThesisFinding, correction=correction, max_tokens=900)
        except SarvamStructuredOutputError:
            finding = _deterministic_stock_finding(holding)
        findings.append(finding)
    return {"stock_thesis": StockThesis(applicable=True, findings=findings)}


def _deterministic_sector_finding(sector: str, holdings: list) -> SectorThesisFinding:
    returns = [item.pnl_pct for item in holdings if item.pnl_pct is not None]
    average = sum(returns) / len(returns) if returns else None
    growth = [f"Average unrealized return across measured {sector} holdings is {average:.1f}%."] if average is not None and average >= 0 else []
    headwinds = [f"Average unrealized return across measured {sector} holdings is {average:.1f}%."] if average is not None and average < 0 else []
    narrative = (
        f"{sector} sector summary across {len(holdings)} tracked holding(s): " +
        (growth[0] if growth else headwinds[0] if headwinds else "Insufficient price data to characterize recent sector performance.") +
        " This deterministic fallback summary was generated without live news context because the language model was unavailable; treat it as educational only, not investment advice."
    )
    return SectorThesisFinding(
        sector=sector,
        growth_drivers=growth or ["No clear growth driver detected in available data."],
        headwinds=headwinds or ["No clear headwind detected in available data."],
        policy_geopolitical_factors=["No sector news was available to assess policy or geopolitical context."],
        pros=["Provides diversification exposure to a distinct industry."],
        cons=["Sector-specific downturns can affect all holdings in this group simultaneously."],
        narrative=narrative,
    )


def sector_thesis_agent(state: PortfolioState, correction: str | None = None) -> dict:
    # Independent of sector/asset/risk agents: only depends on ingestion output. Always runs, regardless of holding count.
    grouped: dict[str, list] = {}
    for holding in state.enriched_holdings:
        grouped.setdefault(holding.sector, []).append(holding)
    findings = []
    for sector, holdings in grouped.items():
        try:
            headlines = [item["title"] for item in fetch_sector_news(sector)][:10]
        except Exception:
            headlines = []
        payload = {"sector": sector, "holdings": [{"ticker": item.ticker, "pnl_pct": item.pnl_pct, "market_value": item.market_value} for item in holdings], "recent_sector_headlines": headlines}
        try:
            finding = structured_completion(SECTOR_THESIS_PROMPT, payload, SectorThesisFinding, correction=correction, max_tokens=900)
        except SarvamStructuredOutputError:
            finding = _deterministic_sector_finding(sector, holdings)
        findings.append(finding)
    return {"sector_thesis": SectorThesis(findings=findings)}


def critic_agent(state: PortfolioState) -> dict:
    issues = []
    if not state.sector_analysis or not state.risk_analysis:
        issues.append("Required sector or risk analysis is missing")
    if len(state.enriched_holdings) <= STOCK_LEVEL_ANALYSIS_LIMIT and any(len(item.narrative.split()) < 100 for item in (state.asset_analysis.findings if state.asset_analysis else [])):
        issues.append("An individual asset narrative is shorter than 100 words")
    if not state.sector_thesis or not state.sector_thesis.findings:
        issues.append("Sector thesis analysis is missing")
    if state.stock_thesis and state.stock_thesis.applicable and not state.stock_thesis.findings:
        issues.append("Stock thesis analysis is missing despite being applicable")
    return {"critic": CriticResult(passed=not issues, issues=issues)}


def synthesizer_agent(state: PortfolioState) -> dict:
    detailed = len(state.enriched_holdings) <= STOCK_LEVEL_ANALYSIS_LIMIT
    payload = {"portfolio_size": len(state.enriched_holdings), "holdings": [item.model_dump() for item in state.enriched_holdings] if detailed else [], "sector_analysis": state.sector_analysis.model_dump() if state.sector_analysis else None, "asset_analysis": state.asset_analysis.model_dump() if detailed and state.asset_analysis else None, "risk_analysis": state.risk_analysis.model_dump() if state.risk_analysis else None, "stock_thesis": state.stock_thesis.model_dump() if state.stock_thesis else None, "sector_thesis": state.sector_thesis.model_dump() if state.sector_thesis else None, "data_errors": [error for item in state.enriched_holdings for error in item.data_errors]}
    narrative = text_completion(SYNTHESIS_PROMPT, payload, max_tokens=2600)
    if _is_prompt_echo(narrative):
        narrative = _safe_executive_summary(state)
    if state.sector_analysis:
        allocation_text = "; ".join(f"{item.sector}: {item.allocation_pct:.1f}% ({item.risk_level.lower()} risk)" for item in state.sector_analysis.findings)
        sector_text = f"{allocation_text}. {state.sector_analysis.macro_commentary}"
    else:
        sector_text = "Sector analysis was unavailable."
    asset_text = "\n\n".join(item.narrative for item in (state.asset_analysis.findings if detailed and state.asset_analysis else []))
    if state.risk_analysis:
        high = sum(1 for item in state.risk_analysis.findings if item.severity == "High")
        medium = sum(1 for item in state.risk_analysis.findings if item.severity == "Medium")
        drawdowns = [item.drawdown_pct for item in state.risk_analysis.findings if item.drawdown_pct is not None]
        drawdown_text = f" The largest observed drawdown reference is {min(drawdowns):.1f}%." if drawdowns else ""
        risk_text = f"{high} holding(s) are flagged high severity and {medium} medium severity, with an overall portfolio risk level of {state.risk_analysis.portfolio_risk_level.lower()}.{drawdown_text} These diagnostics use observed drawdown, volatility, and support as educational risk references rather than trade instructions."
    else:
        risk_text = "Risk diagnostics were unavailable."
    if state.stock_thesis and state.stock_thesis.applicable and state.stock_thesis.findings:
        stock_thesis_text = "\n".join(
            f"{item.ticker} ({item.sector}) — Pros: {'; '.join(item.pros) or 'none identified'}. Cons: {'; '.join(item.cons) or 'none identified'}."
            for item in state.stock_thesis.findings
        )
    elif state.stock_thesis and not state.stock_thesis.applicable:
        stock_thesis_text = state.stock_thesis.reason_if_not_applicable
    else:
        stock_thesis_text = "Individual stock thesis analysis was unavailable."
    if state.sector_thesis and state.sector_thesis.findings:
        sector_thesis_text = "\n\n".join(
            f"{item.sector} — Growth drivers: {'; '.join(item.growth_drivers) or 'none identified'}. "
            f"Headwinds: {'; '.join(item.headwinds) or 'none identified'}. "
            f"Policy/geopolitical factors: {'; '.join(item.policy_geopolitical_factors) or 'none identified'}. "
            f"Pros: {'; '.join(item.pros) or 'none identified'}. Cons: {'; '.join(item.cons) or 'none identified'}. {item.narrative}"
            for item in state.sector_thesis.findings
        )
    else:
        sector_thesis_text = "Sector thesis analysis was unavailable."
    return {"report": ExecutiveReport(headline="Portfolio executive analysis", executive_summary=narrative, sector_commentary=sector_text, asset_commentary=asset_text, risk_commentary=risk_text, stock_thesis_commentary=stock_thesis_text, sector_thesis_commentary=sector_thesis_text, recommendations=["Review concentration and position-size limits against personal goals.", "Monitor material changes in sector exposure, volatility, and drawdown."], disclaimer="Educational analysis only; not investment advice.")}
