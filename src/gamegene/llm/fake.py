"""Offline LLM for tests, CI and the demo service. Never touches the network."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel

from ..contracts.errors import LLMOutputInvalid
from .base import validate_json_text

T = TypeVar("T", bound=BaseModel)

Responder = Callable[[str, str, type[BaseModel]], Any]


class FakeLLM:
    """Implements contracts.LLMClient.

    ``script`` is a list consumed one item per call; when it is exhausted the
    ``responder`` (if any) is used. An item may be:
    * a dict / BaseModel / JSON string -> validated against the requested schema
      (an invalid one raises LLMOutputInvalid, exactly like a real bad answer);
    * an Exception instance            -> raised (use it to force errors, test 4).
    Every call is recorded in ``calls_log`` so tests can assert "no model call happened".
    """

    provider = "fake"

    def __init__(
        self,
        script: list[Any] | None = None,
        responder: Responder | None = None,
        model: str = "fake-1",
    ) -> None:
        self.model = model
        self._script = list(script or [])
        self._responder = responder
        self.calls_log: list[dict[str, Any]] = []
        self.retries = 0

    @property
    def calls(self) -> int:
        return len(self.calls_log)

    def complete_json(
        self, *, system: str, user: str, schema: type[T], temperature: float = 0.2
    ) -> T:
        self.calls_log.append({"system": system, "user": user, "schema": schema.__name__})
        if self._script:
            item = self._script.pop(0)
        elif self._responder is not None:
            item = self._responder(system, user, schema)
        else:
            raise LLMOutputInvalid(
                "FakeLLM has no scripted answer",
                provider=self.provider,
                model=self.model,
                raw_head="",
            )
        if isinstance(item, Exception):
            raise item
        if isinstance(item, schema):
            return item
        if isinstance(item, BaseModel):
            item = item.model_dump(mode="json")
        raw = item if isinstance(item, str) else __import__("json").dumps(item)
        try:
            return validate_json_text(raw, schema)
        except ValueError as err:
            raise LLMOutputInvalid(
                f"model output never matched the schema: {err}",
                provider=self.provider,
                model=self.model,
                raw_head=raw[:200],
            ) from err
