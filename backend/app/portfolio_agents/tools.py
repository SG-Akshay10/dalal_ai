"""Backward-compatibility shim — all symbols now live in ``portfolio_agents.data``.

.. deprecated::
    Import directly from ``app.portfolio_agents.data`` instead.

    This file will be removed in a future cleanup once all internal callers
    have been updated.  It exists only to avoid breaking any external code or
    scripts that were written against the old ``tools`` import path.
"""

from __future__ import annotations

# Re-export the full public surface of the data package so that any existing
# import of the form ``from app.portfolio_agents.tools import X`` continues to
# work without modification.
from .data import (  # noqa: F401  (re-exports are intentional)
    MARKET_DATA_MAX_AGE_SECONDS,
    allocation,
    calculate_technicals,
    diversification_score,
    enrich_holding,
    holding_quality,
    market_data_is_fresh,
    missing_sectors,
    resolve_sector,
)

__all__ = [
    "MARKET_DATA_MAX_AGE_SECONDS",
    "allocation",
    "calculate_technicals",
    "diversification_score",
    "enrich_holding",
    "holding_quality",
    "market_data_is_fresh",
    "missing_sectors",
    "resolve_sector",
]
