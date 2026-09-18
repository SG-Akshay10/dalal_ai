"""Reusable deterministic portfolio-level calculations."""

from __future__ import annotations

from collections import defaultdict

from app.services.portfolio_risk import DEFAULT_SECTORS
from ..schemas import EnrichedHolding


def allocation(holdings: list[EnrichedHolding]) -> tuple[dict[str, float], float]:
    values: dict[str, float] = defaultdict(float)
    for holding in holdings:
        if holding.market_value is not None:
            values[holding.sector] += holding.market_value
    total = sum(values.values())
    return dict(values), total


def diversification_score(values: dict[str, float], total: float) -> float:
    if not total:
        return 0
    hhi = sum((value / total) ** 2 for value in values.values())
    return round(max(0, min(100, (1 - hhi) * 125)), 1)


def missing_sectors(values: dict[str, float], total: float) -> list[str]:
    return [sector for sector in DEFAULT_SECTORS if not total or values.get(sector, 0) / total * 100 < 5]
