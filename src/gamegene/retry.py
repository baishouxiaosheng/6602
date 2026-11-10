"""Bounded retry with exponential backoff. The only retry helper in the project."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from .contracts.errors import GameGeneError

T = TypeVar("T")


def retry_call(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay_s: float = 1.0,
    max_delay_s: float = 20.0,
    sleep: Callable[[float], None] = time.sleep,
    on_retry: Callable[[int, GameGeneError], None] | None = None,
) -> T:
    """Call ``fn`` up to ``attempts`` times.

    Only errors with ``retryable=True`` (UpstreamError, RateLimited) are retried;
    everything else propagates immediately (retry 5xx, never 4xx: Lec 4).
    The last error is re-raised unchanged when attempts run out.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except GameGeneError as err:
            if not err.retryable or attempt == attempts:
                raise
            if on_retry:
                on_retry(attempt, err)
            sleep(min(max_delay_s, base_delay_s * 2 ** (attempt - 1)))
    raise AssertionError("unreachable")
