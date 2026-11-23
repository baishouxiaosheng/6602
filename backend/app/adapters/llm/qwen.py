import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.adapters.http import JsonHttpClient
from app.adapters.llm.prompts import PromptRepository
from app.domain.llm import (
    OfficialAnnotationRequest,
    OfficialAnnotationResult,
    PreferenceParseRequest,
    RankingRequest,
    RankingResult,
    ReviewSupplementRequest,
    ReviewSupplementResult,
)
from app.domain.profiles import PreferenceParseResult

ResultModel = TypeVar("ResultModel", bound=BaseModel)


def _qwen_compatible_schema(value):
    """Remove JSON Schema keywords rejected by Model Studio strict mode.

    Pydantic still validates the returned keys and values after the response, so
    removing these provider-incompatible key constraints does not weaken the
    application's domain validation.
    """
    if isinstance(value, dict):
        return {
            key: _qwen_compatible_schema(item)
            for key, item in value.items()
            if key not in {"patternProperties", "propertyNames"}
        }
    if isinstance(value, list):
        return [_qwen_compatible_schema(item) for item in value]
    return value


class LLMConfigurationError(Exception):
    pass


class LLMOutputValidationError(Exception):
    def __init__(self, message: str, *, attempts: int) -> None:
        super().__init__(message)
        self.attempts = attempts


class QwenLLMClient:
    def __init__(
        self,
        *,
        http: JsonHttpClient,
        api_key: str | None,
        base_url: str | None,
        model: str | None,
        prompts: PromptRepository | None = None,
    ) -> None:
        if not api_key or not base_url or not model:
            raise LLMConfigurationError(
                "Qwen API key, base URL, and model must all be configured."
            )
        self.http = http
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.prompts = prompts or PromptRepository()

    async def annotate_official(
        self, request: OfficialAnnotationRequest
    ) -> OfficialAnnotationResult:
        return await self._complete_structured(
            prompt_name="annotation_official_v1",
            request=request,
            result_type=OfficialAnnotationResult,
        )

    async def supplement_reviews(
        self, request: ReviewSupplementRequest
    ) -> ReviewSupplementResult:
        return await self._complete_structured(
            prompt_name="annotation_reviews_v1",
            request=request,
            result_type=ReviewSupplementResult,
        )

    async def parse_preferences(
        self, request: PreferenceParseRequest
    ) -> PreferenceParseResult:
        return await self._complete_structured(
            prompt_name="preference_parse_v1",
            request=request,
            result_type=PreferenceParseResult,
        )

    async def rank_candidates(self, request: RankingRequest) -> RankingResult:
        return await self._complete_structured(
            prompt_name="candidate_ranking_v1",
            request=request,
            result_type=RankingResult,
        )

    async def _complete_structured(
        self,
        *,
        prompt_name: str,
        request: BaseModel,
        result_type: type[ResultModel],
    ) -> ResultModel:
        system_prompt = self.prompts.load(prompt_name)
        request_json = request.model_dump_json()
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": request_json},
        ]
        last_error = "unknown validation error"

        for attempt in (1, 2):
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": result_type.__name__,
                        "strict": True,
                        "schema": _qwen_compatible_schema(
                            result_type.model_json_schema()
                        ),
                    },
                },
            }
            response = await self.http.request_json(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            content = ""
            try:
                content = self._extract_content(response)
                parsed = json.loads(content)
                return result_type.model_validate(parsed)
            except (
                json.JSONDecodeError,
                ValidationError,
                TypeError,
                LLMOutputValidationError,
            ) as exc:
                last_error = str(exc)
                if attempt == 1:
                    if content:
                        messages.append({"role": "assistant", "content": content})
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "The previous JSON failed validation. Correct only the "
                                f"structure and unsupported values. Error: {last_error}"
                            ),
                        }
                    )

        raise LLMOutputValidationError(
            f"Qwen output remained invalid after one repair: {last_error}",
            attempts=2,
        )

    @staticmethod
    def _extract_content(response: dict) -> str:
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMOutputValidationError(
                "Qwen response does not contain choices[0].message.content.",
                attempts=1,
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMOutputValidationError(
                "Qwen response content is empty or not text.", attempts=1
            )
        return content
