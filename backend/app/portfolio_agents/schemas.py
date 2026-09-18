from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

# Shared threshold: portfolios with more than this many individual holdings
# skip per-stock thesis/technical analysis and rely on sector-wide analysis only.
STOCK_LEVEL_ANALYSIS_LIMIT = 20


class HoldingInput(BaseModel):
    ticker: str | None = None
    symbol: str | None = None
    quantity: float = Field(gt=0)
    buy_price: float | None = Field(default=None, ge=0)
    current_price: float | None = Field(default=None, ge=0)
    sector: str | None = None
    exchange: str = "NSE"
    # Chart rows may be supplied by the dashboard so the portfolio analysis can
    # use the exact series already displayed to the user instead of fetching it
    # a second time.
    historical_prices: list[dict[str, float | str | None]] = Field(default_factory=list)
    # Timestamp for the dashboard quote/history snapshot. The backend refreshes
    # market data when this is absent or older than ten minutes.
    market_data_as_of: str | None = None


class Technicals(BaseModel):
    rsi14: float | None = None
    sma20: float | None = None
    sma50: float | None = None
    sma200: float | None = None
    ema12: float | None = None
    ema26: float | None = None
    macd_line: float | None = None
    macd_signal: float | None = None
    macd_histogram: float | None = None
    crossover: Literal["bullish", "bearish", "neutral", "unavailable"] = "unavailable"
    bollinger_upper: float | None = None
    bollinger_lower: float | None = None
    bollinger_bandwidth_pct: float | None = None
    bollinger_squeeze: bool = False
    annualized_volatility_pct: float | None = None
    momentum_14d_pct: float | None = None
    avg_volume_20d: float | None = None
    latest_volume: float | None = None
    volume_ratio: float | None = None
    volume_surge: bool = False
    support: float | None = None
    resistance: float | None = None
    max_drawdown_pct: float | None = None
    historical_bars_count: int = 0


class DataQuality(BaseModel):
    """Freshness, completeness, and provenance metadata for a single enriched holding.

    Every enriched holding carries one of these records so agents and the
    executive report can surface data quality without performing any additional
    computation.
    """
    source: str = "unknown"
    as_of: str | None = None          # ISO-8601 UTC timestamp of the snapshot
    fresh: bool = False               # True when data is ≤ MARKET_DATA_MAX_AGE_SECONDS old
    complete: bool = False            # True when no errors and no missing_fields
    missing_fields: list[str] = Field(default_factory=list)   # e.g. ["current_price", "historical_prices"]
    errors: list[str] = Field(default_factory=list)           # human-readable retrieval errors


class FinancialPeriod(BaseModel):
    period: str  # e.g., "FY2023", "FY2024", "TTM"
    revenue: float | None = None
    net_income: float | None = None
    operating_margin_pct: float | None = None
    net_margin_pct: float | None = None
    eps: float | None = None


class FundamentalMetrics(BaseModel):
    pe_ratio: float | None = None
    forward_pe: float | None = None
    pb_ratio: float | None = None
    ev_ebitda: float | None = None
    peg_ratio: float | None = None
    price_to_sales: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    de_ratio: float | None = None
    roe_pct: float | None = None
    roce_pct: float | None = None
    gross_margin_pct: float | None = None
    operating_margin_pct: float | None = None
    net_margin_pct: float | None = None
    revenue_growth_pct: float | None = None
    earnings_growth_pct: float | None = None
    free_cash_flow: float | None = None
    operating_cash_flow: float | None = None
    interest_coverage: float | None = None
    historical_periods: list[FinancialPeriod] = Field(default_factory=list)
    benchmark_pe: float | None = None
    benchmark_roe_pct: float | None = None


class EnrichedHolding(BaseModel):
    ticker: str
    sector: str = "Unknown"
    quantity: float
    buy_price: float | None = None
    current_price: float | None = None
    market_value: float | None = None
    pnl_pct: float | None = None
    technicals: Technicals = Field(default_factory=Technicals)
    fundamentals: FundamentalMetrics = Field(default_factory=FundamentalMetrics)
    data_errors: list[str] = Field(default_factory=list)
    data_quality: DataQuality = Field(default_factory=DataQuality)


class SectorFinding(BaseModel):
    sector: str
    allocation_pct: float
    market_value: float
    risk_level: Literal["Low", "Medium", "High"]
    commentary: str


class SectorAnalysis(BaseModel):
    findings: list[SectorFinding]
    concentration_flags: list[str] = Field(default_factory=list)
    missing_sectors: list[str] = Field(default_factory=list)
    diversification_score: float = Field(ge=0, le=100)
    macro_commentary: str


class AssetFinding(BaseModel):
    ticker: str
    trend: str
    momentum: str
    support: float | None = None
    resistance: float | None = None
    narrative: str = ""


class AssetAnalysis(BaseModel):
    detailed_mode: bool
    findings: list[AssetFinding] = Field(default_factory=list)


class TechnicalFinding(BaseModel):
    ticker: str
    trend: Literal["Bullish", "Bearish", "Neutral", "Consolidating"]
    momentum: Literal["Strong Positive", "Weak Positive", "Neutral", "Weak Negative", "Strong Negative"]
    volatility_assessment: str
    volume_assessment: str
    support: float | None = None
    resistance: float | None = None
    detected_patterns: list[str] = Field(default_factory=list)
    narrative: str = ""


class TechnicalAnalysis(BaseModel):
    detailed_mode: bool
    findings: list[TechnicalFinding] = Field(default_factory=list)
    summary: str = ""


class RiskFinding(BaseModel):
    ticker: str
    severity: Literal["Low", "Medium", "High"]
    drawdown_pct: float | None = None
    volatility_pct: float | None = None
    stop_loss_reference: float | None = None
    tax_loss_observation: str = "A loss may warrant recordkeeping review; tax treatment depends on jurisdiction, holding period, and investor circumstances."
    leverage_risk: str = ""
    liquidity_risk: str = ""
    valuation_risk: str = ""
    earnings_risk: str = ""
    sector_sensitivity: str = ""
    downside_scenarios: list[str] = Field(default_factory=list)
    evidence_backed_risks: list[str] = Field(default_factory=list)
    hypothetical_risks: list[str] = Field(default_factory=list)
    agent_disagreements: list[str] = Field(default_factory=list)
    commentary: str = ""
    narrative: str = ""


class RiskAnalysis(BaseModel):
    applicable: bool = True
    reason_if_not_applicable: str = ""
    findings: list[RiskFinding] = Field(default_factory=list)
    portfolio_risk_level: Literal["Low", "Medium", "High"] = "Medium"
    concentration_risk_summary: str = ""
    macro_downside_scenarios: list[str] = Field(default_factory=list)
    overall_risk_summary: str = ""


class StockThesisFinding(BaseModel):
    ticker: str
    sector: str
    growth_drivers: list[str] = Field(default_factory=list)
    decline_risks: list[str] = Field(default_factory=list)
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    narrative: str = ""


class StockThesis(BaseModel):
    applicable: bool
    reason_if_not_applicable: str = ""
    findings: list[StockThesisFinding] = Field(default_factory=list)


class SectorThesisFinding(BaseModel):
    sector: str
    growth_drivers: list[str] = Field(default_factory=list)
    headwinds: list[str] = Field(default_factory=list)
    policy_geopolitical_factors: list[str] = Field(default_factory=list)
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    narrative: str = ""


class SectorThesis(BaseModel):
    findings: list[SectorThesisFinding] = Field(default_factory=list)


class FundamentalFinding(BaseModel):
    ticker: str
    sector: str
    health_score: float = Field(ge=0, le=100)
    key_metrics: dict[str, float | str | None] = Field(default_factory=dict)
    positive_developments: list[str] = Field(default_factory=list)
    deteriorating_metrics: list[str] = Field(default_factory=list)
    financial_weaknesses: list[str] = Field(default_factory=list)
    insufficient_data_areas: list[str] = Field(default_factory=list)
    historical_trend_analysis: str = ""
    benchmark_comparison: str = ""
    narrative: str = ""


class FundamentalAnalysis(BaseModel):
    applicable: bool
    reason_if_not_applicable: str = ""
    findings: list[FundamentalFinding] = Field(default_factory=list)
    portfolio_fundamental_health: Literal["Strong", "Moderate", "Weak", "Mixed"] = "Moderate"
    overall_summary: str = ""


class ValuationFinding(BaseModel):
    ticker: str
    sector: str
    current_price: float | None = None
    valuation_assessment: Literal["Undervalued", "Fairly Valued", "Overvalued", "Speculative / High Growth", "Unavailable"] = "Unavailable"
    observed_metrics: dict[str, float | str | None] = Field(default_factory=dict)
    valuation_assumptions: dict[str, float | str | None] = Field(default_factory=dict)
    historical_valuation_range: str = ""
    comparative_benchmark_analysis: str = ""
    growth_adjusted_analysis: str = ""
    data_vs_assumptions_breakdown: str = ""
    narrative: str = ""


class ValuationAnalysis(BaseModel):
    applicable: bool
    reason_if_not_applicable: str = ""
    findings: list[ValuationFinding] = Field(default_factory=list)
    portfolio_valuation_summary: str = ""
    overall_valuation_stance: Literal["Attractive", "Fair", "Elevated", "Mixed", "Unavailable"] = "Fair"


class MarketContextFinding(BaseModel):
    ticker: str
    sector: str
    relative_strength_vs_market: float | None = None
    relative_strength_vs_sector: float | None = None
    movement_alignment: Literal[
        "Aligned with Market & Sector",
        "Outperforming Broad Market",
        "Outperforming Sector",
        "Underperforming Broad Market",
        "Underperforming Sector",
        "Diverging Positively",
        "Diverging Negatively",
        "Synchronized Movement",
    ] = "Synchronized Movement"
    market_trend_environment: Literal["Bullish", "Bearish", "Neutral", "High Volatility"] = "Neutral"
    sector_trend_environment: Literal["Bullish", "Bearish", "Neutral", "High Volatility"] = "Neutral"
    observed_context_metrics: dict[str, float | str | None] = Field(default_factory=dict)
    analytical_assumptions: dict[str, float | str | None] = Field(default_factory=dict)
    narrative: str = ""


class MarketContextAnalysis(BaseModel):
    applicable: bool
    reason_if_not_applicable: str = ""
    broad_market_benchmark: str = "NIFTY 50"
    market_regime_summary: str = ""
    findings: list[MarketContextFinding] = Field(default_factory=list)
    overall_market_context_summary: str = ""


class CriticResult(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)


class EvidenceRecord(BaseModel):
    """Evidence produced by an optional external-information agent.

    The active pipeline has no external news evidence. Future source agents must
    emit records through this model so the critic can reject unverified or
    low-quality material before it reaches a report.
    """
    source: str
    subject: str
    claim: str
    retrieved_at: str
    quality_score: float = Field(ge=0, le=1)
    verified: bool = False


class ExecutiveReport(BaseModel):
    headline: str
    executive_summary: str
    sector_commentary: str
    asset_commentary: str = ""
    risk_commentary: str
    stock_thesis_commentary: str = ""
    sector_thesis_commentary: str = ""
    fundamental_commentary: str = ""
    valuation_commentary: str = ""
    market_context_commentary: str = ""
    recommendations: list[str] = Field(min_length=1)
    disclaimer: str


class PortfolioState(BaseModel):
    raw_holdings: list[HoldingInput]
    enriched_holdings: list[EnrichedHolding] = Field(default_factory=list)
    sector_analysis: SectorAnalysis | None = None
    asset_analysis: AssetAnalysis | None = None
    technical_analysis: TechnicalAnalysis | None = None
    risk_analysis: RiskAnalysis | None = None
    stock_thesis: StockThesis | None = None
    sector_thesis: SectorThesis | None = None
    fundamental_analysis: FundamentalAnalysis | None = None
    valuation_analysis: ValuationAnalysis | None = None
    market_context_analysis: MarketContextAnalysis | None = None
    critic: CriticResult | None = None
    report: ExecutiveReport | None = None
    retry_count: int = 0
    errors: list[str] = Field(default_factory=list)
    evidence: list[EvidenceRecord] = Field(default_factory=list)

