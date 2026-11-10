import pytest
from pydantic import BaseModel

from gamegene.contracts import InvalidInput, LLMClient, LLMOutputInvalid, UpstreamError
from gamegene.llm import FakeLLM, extract_json_text, validate_json_text
from gamegene.retry import retry_call


class Out(BaseModel):
    label: str
    score: int


def test_fences_and_prose_are_stripped():
    assert extract_json_text('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert extract_json_text('Sure! Here it is: {"a": 1} Hope it helps.') == '{"a": 1}'
    assert validate_json_text('```\n{"label":"x","score":2}\n```', Out) == Out(label="x", score=2)


@pytest.mark.parametrize(
    "raw", ["", "Sure! Here is my assessment", '{"label": "x"}', '{"label":"x","score":"hi"}']
)
def test_bad_answers_give_a_readable_reason(raw):
    with pytest.raises(ValueError):
        validate_json_text(raw, Out)


def test_fake_llm_is_an_llm_client_and_records_calls():
    llm = FakeLLM(script=[{"label": "x", "score": 1}])
    assert isinstance(llm, LLMClient)
    assert llm.complete_json(system="s", user="u", schema=Out).score == 1
    assert llm.calls == 1


def test_fake_llm_bad_answer_and_forced_error():
    llm = FakeLLM(script=["not json at all", UpstreamError("down")])
    with pytest.raises(LLMOutputInvalid) as info:
        llm.complete_json(system="s", user="u", schema=Out)
    assert info.value.details["raw_head"] == "not json at all"
    with pytest.raises(UpstreamError):
        llm.complete_json(system="s", user="u", schema=Out)
    with pytest.raises(LLMOutputInvalid):  # script exhausted, no responder
        llm.complete_json(system="s", user="u", schema=Out)


def test_retry_only_retries_retryable_errors():
    calls, sleeps = [], []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise UpstreamError("503")
        return "ok"

    assert retry_call(flaky, attempts=3, sleep=sleeps.append) == "ok"
    assert len(calls) == 3 and sleeps == [1.0, 2.0]

    calls.clear()

    def bad_input():
        calls.append(1)
        raise InvalidInput("400")

    with pytest.raises(InvalidInput):
        retry_call(bad_input, attempts=3, sleep=sleeps.append)
    assert len(calls) == 1


def test_retry_gives_up_after_bounded_attempts():
    calls = []

    def always_down():
        calls.append(1)
        raise UpstreamError("down")

    with pytest.raises(UpstreamError):
        retry_call(always_down, attempts=3, sleep=lambda s: None)
    assert len(calls) == 3
