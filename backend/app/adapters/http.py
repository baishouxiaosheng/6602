import asyncio
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    backoff_seconds: float = 0.25
    timeout_seconds: float = 20.0


class UpstreamHttpError(Exception):
    def __init__(
        self,
        *,
        service: str,
        message: str,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.service = service
        self.status_code = status_code
        self.retryable = retryable


class InvalidUpstreamPayload(UpstreamHttpError):
    pass


class JsonHttpClient:
    def __init__(
        self,
        *,
        service: str,
        client: httpx.AsyncClient,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self.service = service
        self.client = client
        self.retry_policy = retry_policy or RetryPolicy()

    async def request_json(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self.retry_policy.max_attempts + 1):
            try:
                response = await self.client.request(
                    method,
                    url,
                    timeout=self.retry_policy.timeout_seconds,
                    **kwargs,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    raise UpstreamHttpError(
                        service=self.service,
                        message=f"{self.service} returned HTTP {response.status_code}.",
                        status_code=response.status_code,
                        retryable=True,
                    )
                if response.status_code >= 400:
                    raise UpstreamHttpError(
                        service=self.service,
                        message=f"{self.service} returned HTTP {response.status_code}.",
                        status_code=response.status_code,
                        retryable=False,
                    )
                payload = response.json()
                if not isinstance(payload, dict):
                    raise InvalidUpstreamPayload(
                        service=self.service,
                        message=f"{self.service} returned a non-object JSON payload.",
                    )
                return payload
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                retryable = True
            except UpstreamHttpError as exc:
                if not exc.retryable:
                    raise
                last_error = exc
                retryable = True
            except ValueError as exc:
                raise InvalidUpstreamPayload(
                    service=self.service,
                    message=f"{self.service} returned invalid JSON.",
                ) from exc

            if attempt < self.retry_policy.max_attempts and retryable:
                await asyncio.sleep(self.retry_policy.backoff_seconds * attempt)

        if isinstance(last_error, UpstreamHttpError):
            raise last_error
        raise UpstreamHttpError(
            service=self.service,
            message=f"{self.service} request failed after retries.",
            retryable=True,
        ) from last_error
