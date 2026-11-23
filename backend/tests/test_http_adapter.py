import httpx
import pytest

from app.adapters.http import JsonHttpClient, RetryPolicy, UpstreamHttpError


@pytest.mark.asyncio
async def test_json_http_client_retries_429_then_succeeds() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = JsonHttpClient(
            service="test",
            client=client,
            retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=0),
        )
        payload = await adapter.request_json("GET", "https://example.test/data")

    assert payload == {"ok": True}
    assert attempts == 2


@pytest.mark.asyncio
async def test_json_http_client_does_not_retry_non_retryable_400() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(400, json={"error": "bad input"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = JsonHttpClient(service="test", client=client)
        with pytest.raises(UpstreamHttpError) as exc_info:
            await adapter.request_json("GET", "https://example.test/data")

    assert exc_info.value.retryable is False
    assert exc_info.value.status_code == 400
    assert attempts == 1
