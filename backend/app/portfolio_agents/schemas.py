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


class Technicals(BaseModel):
    rsi14: float | None = None
    sma50: float | None = None
    sma200: float | None = None
    macd_histogram: float | None = None
    crossover: Literal["bullish", "bearish", "neutral", "unavailable"] = "unavailable"
    annualized_volatility_pct: float | None = None
    support: float | None = None
    resistance: float | None = None
    max_drawdown_pct: float | None = None


class EnrichedHolding(BaseModel):
    ticker: str
    sector: str = "Unknown"
    quantity: float
    buy_price: float | None = None
    current_price: float | None = None
    market_value: float | None = None
    pnl_pct: float | None = None
    technicals: Technicals = Field(default_factory=Technicals)
    data_errors: list[str] = Field(default_factory=list)


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


class RiskFinding(BaseModel):
    ticker: str
    severity: Literal["Low", "Medium", "High"]
    drawdown_pct: float | None = None
    stop_loss_reference: float | None = None
    tax_loss_observation: str
    commentary: str


class RiskAnalysis(BaseModel):
    findings: list[RiskFinding] = Field(default_factory=list)
    portfolio_risk_level: Literal["Low", "Medium", "High"]


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


class CriticResult(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)


class ExecutiveReport(BaseModel):
    headline: str
    executive_summary: str
    sector_commentary: str
    asset_commentary: str = ""
    risk_commentary: str
    stock_thesis_commentary: str = ""
    sector_thesis_commentary: str = ""
    recommendations: list[str] = Field(min_length=1)
    disclaimer: str


class PortfolioState(BaseModel):
    raw_holdings: list[HoldingInput]
    enriched_holdings: list[EnrichedHolding] = Field(default_factory=list)
    sector_analysis: SectorAnalysis | None = None
    asset_analysis: AssetAnalysis | None = None
    risk_analysis: RiskAnalysis | None = None
    stock_thesis: StockThesis | None = None
    sector_thesis: SectorThesis | None = None
    critic: CriticResult | None = None
    report: ExecutiveReport | None = None
    retry_count: int = 0
    errors: list[str] = Field(default_factory=list)
