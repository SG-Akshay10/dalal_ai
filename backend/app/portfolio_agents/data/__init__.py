"""Normalized market-data, quality, and deterministic portfolio calculations.

All agents should import from this package rather than from ``tools`` or
individual sub-modules.  This is the single stable surface for:

- Market-data enrichment and technical-indicator computation (``market``)
- Fundamental metrics processing and evaluation (``fundamental``)
- Portfolio-level deterministic calculations (``portfolio``)
- Data-freshness and completeness metadata (``quality``)
"""

from .fundamental import (
    SECTOR_BENCHMARKS,
    calculate_fundamental_health,
    extract_fundamental_finding,
    get_sector_benchmark,
)
from .market import (
    calculate_technicals,
    enrich_holding,
    resolve_sector,
)
from .portfolio import (
    allocation,
    diversification_score,
    missing_sectors,
)
from .quality import (
    MARKET_DATA_MAX_AGE_SECONDS,
    holding_quality,
    market_data_is_fresh,
)
from .valuation import (
    SECTOR_VALUATION_BENCHMARKS,
    calculate_growth_adjusted_valuation,
    calculate_historical_valuation_range,
    extract_valuation_finding,
    get_sector_valuation_benchmark,
)

__all__ = [
    # fundamental calculations
    "SECTOR_BENCHMARKS",
    "calculate_fundamental_health",
    "extract_fundamental_finding",
    "get_sector_benchmark",
    # valuation calculations
    "SECTOR_VALUATION_BENCHMARKS",
    "calculate_growth_adjusted_valuation",
    "calculate_historical_valuation_range",
    "extract_valuation_finding",
    "get_sector_valuation_benchmark",
    # market enrichment
    "calculate_technicals",
    "enrich_holding",
    "resolve_sector",
    # portfolio calculations
    "allocation",
    "diversification_score",
    "missing_sectors",
    # data quality
    "MARKET_DATA_MAX_AGE_SECONDS",
    "holding_quality",
    "market_data_is_fresh",
]
