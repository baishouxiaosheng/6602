"""[A] Shared throttled HTTP GET used by every Steam client.

TODO(Dev A) implement ``ThrottledHttp.get_json`` (task A1):
* one shared httpx.Client, timeout 20 s, a descriptive but generic User-Agent;
* at least ``min_interval_s`` between two requests to the same host (injectable
  ``sleep``/``clock`` so tests run instantly);
* map failures onto contracts.errors: timeout / connection / 5xx -> UpstreamError,
  429 -> RateLimited, other 4xx -> NotFound (404) or InvalidInput;
* wrap the request in retry.retry_call(attempts=3) so retryable errors back off;
* body that is not JSON -> UpstreamError (Steam sometimes returns an HTML error page).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any


class ThrottledHttp:
    def __init__(
        self,
        *,
        min_interval_s: float = 1.5,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        transport: Any | None = None,  # httpx.MockTransport in tests
    ) -> None:
        self.min_interval_s = min_interval_s
        self._sleep = sleep
        self._clock = clock
        self._transport = transport

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        raise NotImplementedError("Dev A: task A1")
