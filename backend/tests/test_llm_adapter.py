import json

import httpx
import pytest

from app.adapters.http import JsonHttpClient, RetryPolicy
from app.adapters.llm.fake import FakeLLMClient
from app.adapters.llm.prompts import PromptRepository
from app.adapters.llm.qwen import (
    LLMConfigurationError,
    LLMOutputValidationError,
    QwenLLMClient,
)
from app.domain.enums import GeneId
from app.domain.llm import (
    OfficialAnnotationRequest,
    PreferenceParseRequest,
    RankingRequest,
    ReviewSupplementRequest,
)
from app.domain.profiles import PreferenceParseResult


def qwen_response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "response-1",
            "choices": [{"message": {"role": "assistant", "content": content}}],
        },
    )


def build_qwen(handler) -> tuple[httpx.AsyncClient, QwenLLMClient]:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    http = JsonHttpClient(
        service="qwen",
        client=client,
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=0),
    )
    return client, QwenLLMClient(
        http=http,
        api_key="test-qwen-key",
        base_url="https://qwen.example/v1",
        model="qwen-test",
    )


@pytest.mark.asyncio
async def test_qwen_uses_strict_schema_and_repairs_once() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        assert request.headers["Authorization"] == "Bearer test-qwen-key"
        body = json.loads(request.content)
        assert body["temperature"] == 0
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["strict"] is True
        schema = body["response_format"]["json_schema"]["schema"]
        assert schema["additionalProperties"] is False
        assert "propertyNames" not in json.dumps(schema)
        assert "patternProperties" not in json.dumps(schema)
        if attempts == 1:
            return qwen_response('{"gene_adjustments":{"challenge":2}}')
        assert len(body["messages"]) == 4
        assert "failed validation" in body["messages"][-1]["content"]
        return qwen_response(
            json.dumps(
                {
                    "gene_adjustments": {"challenge": -1},
                    "soft_descriptor_preferences": ["pixel_graphics"],
                    "potential_hard_constraints": [],
                    "unsupported_requests": [],
                }
            )
        )

    client, qwen = build_qwen(handler)
    async with client:
        result = await qwen.parse_preferences(
            PreferenceParseRequest(text="I want something easier with pixel art.")
        )

    assert attempts == 2
    assert result.gene_adjustments == {GeneId.CHALLENGE: -1}
    assert result.soft_descriptor_preferences == ["pixel_graphics"]


@pytest.mark.asyncio
async def test_qwen_fails_after_one_invalid_repair() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return qwen_response("not-json")

    client, qwen = build_qwen(handler)
    async with client:
        with pytest.raises(LLMOutputValidationError) as exc_info:
            await qwen.parse_preferences(PreferenceParseRequest(text="A valid request"))

    assert attempts == 2
    assert exc_info.value.attempts == 2


@pytest.mark.asyncio
async def test_qwen_exposes_all_four_structured_operations() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        system_prompt = body["messages"][0]["content"]
        if "annotate Steam games" in system_prompt:
            return qwen_response('{"genes":[],"descriptors":[]}')
        if "supplement missing Steam game genes" in system_prompt:
            return qwen_response('{"genes":[]}')
        if "Rank only the supplied candidate games" in system_prompt:
            return qwen_response('{"same_track":[],"cross_track":[]}')
        raise AssertionError(f"Unexpected prompt: {system_prompt}")

    client, qwen = build_qwen(handler)
    async with client:
        official = await qwen.annotate_official(
            OfficialAnnotationRequest(
                appid=10,
                name="Example",
                official_passages=["Build and explore."],
            )
        )
        reviews = await qwen.supplement_reviews(
            ReviewSupplementRequest(
                appid=10,
                missing_gene_ids=[GeneId.CHALLENGE],
                passages=[],
            )
        )
        ranking = await qwen.rank_candidates(
            RankingRequest(profile_summary="A valid profile summary.")
        )

    assert official.genes == []
    assert reviews.genes == []
    assert ranking.same_track == []


def test_qwen_requires_complete_configuration() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: None))
    http = JsonHttpClient(service="qwen", client=client)
    with pytest.raises(LLMConfigurationError):
        QwenLLMClient(http=http, api_key=None, base_url=None, model=None)


@pytest.mark.asyncio
async def test_fake_llm_is_explicitly_configured_and_counts_calls() -> None:
    expected = PreferenceParseResult(
        gene_adjustments={GeneId.PACE: -1},
        soft_descriptor_preferences=["cozy_atmosphere"],
    )
    fake = FakeLLMClient(preference_result=expected)

    result = await fake.parse_preferences(PreferenceParseRequest(text="Something cozy"))

    assert result == expected
    assert fake.calls["parse_preferences"] == 1


def test_all_prompts_treat_external_text_as_data_not_instructions() -> None:
    prompts = PromptRepository()
    for name in (
        "annotation_official_v1",
        "annotation_reviews_v1",
        "candidate_ranking_v1",
    ):
        prompt = prompts.load(name).casefold()
        assert "untrusted data" in prompt
        assert "never instructions" in prompt
