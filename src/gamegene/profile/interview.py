"""[FW] Interview spec loading and deterministic scoring (no model involved)."""

from __future__ import annotations

import json
from functools import lru_cache

from ..config import RESOURCES
from ..contracts.errors import InvalidInput
from ..contracts.genes import GENE_ORDER, MAX_LEVEL, MIN_LEVEL, GeneId
from ..contracts.models import GenePreference, InterviewSpec

NEUTRAL_TARGET = 2.0
BASE_WEIGHT = 0.4
WEIGHT_PER_STEP = 0.3


@lru_cache(maxsize=1)
def load_interview() -> InterviewSpec:
    return InterviewSpec.model_validate(
        json.loads((RESOURCES / "interview_v1.json").read_text(encoding="utf-8"))
    )


def validate_answers(spec: InterviewSpec, answers: dict[str, list[str]]) -> None:
    """Raise InvalidInput listing EVERY problem (missing / unknown / wrong count)."""
    problems: list[str] = []
    known = {q.id: q for q in spec.questions}
    for qid in answers:
        if qid not in known:
            problems.append(f"{qid}: unknown question")
    for q in spec.questions:
        chosen = answers.get(q.id)
        if not chosen:
            problems.append(f"{q.id}: no answer")
            continue
        valid = {o.id for o in q.options}
        bad = [c for c in chosen if c not in valid]
        if bad:
            problems.append(f"{q.id}: unknown option(s) {bad}")
        if len(set(chosen)) != len(chosen):
            problems.append(f"{q.id}: duplicate options")
        if not q.min_choices <= len(chosen) <= q.max_choices:
            problems.append(f"{q.id}: choose {q.min_choices}-{q.max_choices}, got {len(chosen)}")
    if problems:
        raise InvalidInput("interview answers are invalid", problems=problems)


def score_interview(
    spec: InterviewSpec, answers: dict[str, list[str]]
) -> tuple[dict[GeneId, GenePreference], dict[str, float]]:
    """answers -> (nine gene preferences, familiar tags).

    target = clamp(2.0 + sum of chosen deltas, 0, 4)
    weight = min(1, 0.4 + 0.3 * |target - 2|)   (strong opinions matter more)
    familiar tags: every tag of every chosen 'tags' option gets weight 1.0
    """
    validate_answers(spec, answers)
    targets = dict.fromkeys(GENE_ORDER, NEUTRAL_TARGET)
    tags: dict[str, float] = {}
    for q in spec.questions:
        options = {o.id: o for o in q.options}
        for choice in answers[q.id]:
            opt = options[choice]
            for gene, delta in opt.gene_deltas.items():
                targets[gene] += delta
            for tag in opt.tags:
                tags[tag.lower()] = 1.0
    prefs = {}
    for gene, raw in targets.items():
        target = max(MIN_LEVEL, min(MAX_LEVEL, raw))
        weight = min(1.0, BASE_WEIGHT + WEIGHT_PER_STEP * abs(target - NEUTRAL_TARGET))
        prefs[gene] = GenePreference(target=round(target, 2), weight=round(weight, 2))
    return prefs, tags
