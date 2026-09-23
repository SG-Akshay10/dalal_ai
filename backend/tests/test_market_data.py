import threading
import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services import market_data


@pytest.fixture(autouse=True)
def clear_market_data_cache():
    with market_data._cache_lock:
        market_data._cache.clear()
        market_data._cache_key_locks.clear()
    yield


def test_get_retries_a_throttled_yahoo_response():
    throttled = MagicMock(spec=httpx.Response)
    throttled.status_code = 429
    throttled.headers = {"Retry-After": "0"}
    successful = MagicMock(spec=httpx.Response)
    successful.status_code = 200
    successful.json.return_value = {"chart": {"result": []}}

    with patch("app.services.market_data.httpx.get", side_effect=[throttled, successful]) as get, \
         patch("app.services.market_data.time.sleep") as sleep:
        assert market_data._get("/v8/finance/chart/WIPRO.NS", {"range": "5d"}) == {"chart": {"result": []}}

    assert get.call_count == 2
    sleep.assert_any_call(0.0)


def test_get_raises_after_throttle_retries_are_exhausted():
    throttled = MagicMock(spec=httpx.Response)
    throttled.status_code = 429
    throttled.headers = {}
    throttled.raise_for_status.side_effect = httpx.HTTPStatusError(
        "rate limited", request=MagicMock(), response=throttled
    )

    with patch("app.services.market_data.httpx.get", return_value=throttled) as get, \
         patch("app.services.market_data.time.sleep"):
        with pytest.raises(httpx.HTTPStatusError):
            market_data._get("/v8/finance/chart/WIPRO.NS", {"range": "5d"})

    assert get.call_count == market_data.YAHOO_MAX_RETRIES + 1


def test_cached_coalesces_concurrent_cache_misses():
    barrier = threading.Barrier(2)
    calls = 0
    calls_lock = threading.Lock()

    def loader():
        nonlocal calls
        with calls_lock:
            calls += 1
        time.sleep(0.03)
        return {"price": 123}

    def read():
        barrier.wait()
        return market_data._cached("quote:WIPRO.NS", 30, loader)

    first = threading.Thread(target=read)
    second = threading.Thread(target=read)
    first.start()
    second.start()
    first.join()
    second.join()

    assert calls == 1
