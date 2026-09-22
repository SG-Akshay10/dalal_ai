import json
from app.services.sarvam import sanitize_payload, ensure_context_budget, structured_completion, text_completion, SarvamStructuredOutputError
from unittest.mock import patch, MagicMock

def test_sanitize_payload_removes_historical_prices():
    raw_payload = {
        "ticker": "RELIANCE",
        "historical_prices": [{"date": "2026-01-01", "close": 2500}] * 500,
        "some_text": "A" * 5000,
        "nested": {
            "raw_bars": [1, 2, 3],
            "valid_key": "ok"
        }
    }
    sanitized = sanitize_payload(raw_payload)
    assert "historical_prices" not in sanitized
    assert "raw_bars" not in sanitized["nested"]
    assert sanitized["nested"]["valid_key"] == "ok"
    assert len(sanitized["some_text"]) <= 4020
    assert sanitized["some_text"].endswith("... [truncated]")

def test_ensure_context_budget_truncates_large_payloads():
    instructions = "You are a financial analyst."
    huge_user_content = "X" * 600000 # ~170k tokens
    result = ensure_context_budget(instructions, huge_user_content, max_tokens=2800, max_context=128000)
    assert len(result) < 600000
    assert "... [Payload truncated to fit Sarvam context window]" in result

@patch("app.services.sarvam.httpx.post")
@patch("os.getenv", return_value="fake_api_key")
def test_text_completion_applies_sanitization(mock_env, mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {"choices": [{"message": {"content": "Sample narrative response"}}]}
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    payload = {"ticker": "INFY", "historical_prices": [1, 2, 3]}
    res = text_completion("System prompt", payload)
    assert res == "Sample narrative response"
    
    # Verify historical_prices was stripped from request json sent to Sarvam API
    args, kwargs = mock_post.call_args
    sent_payload = kwargs["json"]
    sent_user_msg = sent_payload["messages"][1]["content"]
    assert "historical_prices" not in sent_user_msg
