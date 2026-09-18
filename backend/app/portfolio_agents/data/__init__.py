"""Normalized market-data, quality, and deterministic portfolio calculations.

All agents should import from this package rather than from ``tools`` or
individual sub-modules.  This is the single stable surface for:

- Market-data enrichment and technical-indicator computation (``market``)
- Portfolio-level deterministic calculations (``portfolio``)
- Data-freshness and completeness metadata (``quality``)
"""

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

__all__ = [
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
