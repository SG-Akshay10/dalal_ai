from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.analysis import router as analysis_router
from app.auth import get_current_user
from app.database import DatabaseManager

app = FastAPI()
app.include_router(analysis_router)

def override_get_current_user():
    return {"sub": "test_rate_limit_user", "email": "test@example.com"}

app.dependency_overrides[get_current_user] = override_get_current_user

client = TestClient(app)


def test_analysis_rate_limiting():
    user_id = "test_rate_limit_user"

    mock_state = MagicMock()
    mock_state.report = MagicMock(headline="Headline", executive_summary="Summary", model_dump=lambda mode: {})
    mock_state.sector_analysis = MagicMock(findings=[], concentration_flags=[], missing_sectors=[])
    mock_state.risk_analysis = MagicMock(portfolio_risk_level="Low", findings=[])
    mock_state.enriched_holdings = []
    mock_state.model_dump = lambda mode: {}

    with patch("app.routers.analysis.run_portfolio_pipeline", return_value=mock_state):
        with patch("app.routers.analysis._RISK_REPORT_CACHE", {}):
            # First request: should succeed
            res1 = client.post("/api/analysis/risk-profile", json={"holdings": [{"ticker": "TCS", "quantity": 10, "buy_price": 3000}]})
            assert res1.status_code == 200, res1.json()

            # Second request: should hit 429 rate limit
            res2 = client.post("/api/analysis/risk-profile", json={"holdings": [{"ticker": "INFY", "quantity": 5, "buy_price": 1400}]})
            assert res2.status_code == 429
            assert "Rate limit reached" in res2.json()["detail"]

