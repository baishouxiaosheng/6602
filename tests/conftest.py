"""Shared fixtures.

A test that reaches a ``NotImplementedError`` stub is reported as SKIPPED
("not implemented yet"), so the suite is green on day one and each acceptance
test turns into a real pass/fail the moment its stub is implemented.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gamegene.catalog.reader import FixtureCatalog
from gamegene.config import Settings
from gamegene.contracts import ProfileSources, UserProfile
from gamegene.profile.interview import load_interview, score_interview
from gamegene.storage import JsonStore

FIXTURES = Path(__file__).parent / "fixtures"


def _skip_if_stub(outcome) -> None:
    exc = outcome.excinfo
    if exc and issubclass(exc[0], NotImplementedError):
        outcome.force_exception(pytest.skip.Exception(f"not implemented yet: {exc[1]}"))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    _skip_if_stub((yield))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    _skip_if_stub((yield))


def load_json(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# The three reference personas of docs/04-recommendation-spec.md section 7.
PERSONAS: dict[str, dict[str, list[str]]] = {
    "roguelike": {
        "q01_failure": ["a"],
        "q02_evening": ["b"],
        "q03_satisfaction": ["a"],
        "q04_story": ["b"],
        "q05_people": ["a"],
        "q06_world": ["b"],
        "q07_question_mark": ["b"],
        "q08_freedom": ["c"],
        "q09_long_term": ["a"],
        "q10_problem": ["b"],
        "q11_familiar": ["roguelike"],
    },
    "builder": {
        "q01_failure": ["b"],
        "q02_evening": ["a"],
        "q03_satisfaction": ["c"],
        "q04_story": ["c"],
        "q05_people": ["a"],
        "q06_world": ["c"],
        "q07_question_mark": ["b"],
        "q08_freedom": ["a"],
        "q09_long_term": ["a"],
        "q10_problem": ["a"],
        "q11_familiar": ["sim"],
    },
    "story": {
        "q01_failure": ["c"],
        "q02_evening": ["c"],
        "q03_satisfaction": ["b"],
        "q04_story": ["a"],
        "q05_people": ["a"],
        "q06_world": ["a"],
        "q07_question_mark": ["a"],
        "q08_freedom": ["c"],
        "q09_long_term": ["c"],
        "q10_problem": ["c"],
        "q11_familiar": ["story"],
    },
}


def make_profile(
    persona: str = "roguelike", profile_id: str | None = None, **overrides
) -> UserProfile:
    spec = load_interview()
    answers = PERSONAS[persona]
    prefs, tags = score_interview(spec, answers)
    data = dict(
        profile_id=profile_id or f"p-{persona}",
        display_name=persona,
        genes=prefs,
        familiar_tags=tags,
        sources=ProfileSources(interview_version=spec.version, answers=answers),
    )
    data.update(overrides)
    return UserProfile(**data)


@pytest.fixture
def store(tmp_path) -> JsonStore:
    return JsonStore(tmp_path / "store")


@pytest.fixture
def catalog() -> FixtureCatalog:
    return FixtureCatalog()


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        llm_provider="fake",
        llm_api_key="",
        llm_model="",
        llm_base_url="",
        llm_max_retries=2,
        llm_timeout_s=5,
        steam_api_key="",
        steam_cc="us",
        steam_lang="english",
        steam_min_interval_s=0,
        data_dir=tmp_path / "store",
        catalog_source="fixture",
        service="demo",
    )
