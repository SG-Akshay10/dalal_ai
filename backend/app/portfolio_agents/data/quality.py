"""Consistent freshness and completeness metadata for normalized holdings."""

from __future__ import annotations

from datetime import datetime, timezone

from ..schemas import DataQuality

MARKET_DATA_MAX_AGE_SECONDS = 10 * 60


def market_data_is_fresh(as_of: str | None) -> bool:
    if not as_of:
        return False
    try:
        timestamp = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            return False
        age = (datetime.now(timezone.utc) - timestamp.astimezone(timezone.utc)).total_seconds()
        return 0 <= age <= MARKET_DATA_MAX_AGE_SECONDS
    except (TypeError, ValueError):
        return False


def holding_quality(*, source: str, as_of: str | None, errors: list[str], missing_fields: list[str]) -> DataQuality:
    fresh = market_data_is_fresh(as_of)
    return DataQuality(source=source, as_of=as_of, fresh=fresh, complete=not errors and not missing_fields, missing_fields=missing_fields, errors=errors)
