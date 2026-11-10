import pytest

from gamegene.contracts import Confidence, EvidenceGrade, GeneId, InvalidInput, Track
from gamegene.profile.interview import load_interview, score_interview
from gamegene.recommend import scoring
from tests.conftest import PERSONAS, make_profile

HADES, DEAD_CELLS, HOLLOW, CIV6, OBSCURE, FACTORIO = 1145360, 588650, 367520, 289070, 999001, 427520


def test_interview_scoring_reference_persona():
    prefs, tags = score_interview(load_interview(), PERSONAS["roguelike"])
    assert (prefs[GeneId.CHALLENGE].target, prefs[GeneId.CHALLENGE].weight) == (4.0, 1.0)
    assert (prefs[GeneId.STRATEGY].target, prefs[GeneId.STRATEGY].weight) == (1.0, 0.7)
    assert (prefs[GeneId.EXPLORATION].target, prefs[GeneId.EXPLORATION].weight) == (2.0, 0.4)
    assert prefs[GeneId.SOCIAL].target == 0.0
    assert tags == {
        "roguelike": 1.0,
        "action roguelike": 1.0,
        "roguelite": 1.0,
        "hack and slash": 1.0,
    }


def test_interview_reports_every_problem():
    answers = dict(PERSONAS["roguelike"])
    del answers["q01_failure"]
    answers["q02_evening"] = ["zzz"]
    answers["q11_familiar"] = ["roguelike", "rpg", "sim", "story", "shooter"]
    with pytest.raises(InvalidInput) as info:
        score_interview(load_interview(), answers)
    assert len(info.value.details["problems"]) == 3


def test_gene_score_numbers(catalog):
    p = make_profile("roguelike")
    parts = scoring.gene_score(p, catalog.get_game(DEAD_CELLS))
    assert (parts.similarity, parts.coverage, parts.score) == (0.9094, 1.0, 0.9094)
    assert scoring.gene_score(p, catalog.get_game(OBSCURE)) is None  # < 5 known genes


def test_unknown_gene_lowers_coverage_not_similarity(catalog):
    parts = scoring.gene_score(make_profile("builder"), catalog.get_game(CIV6))
    assert parts.coverage < 1.0
    assert parts.score == pytest.approx(parts.similarity * (0.7 + 0.3 * parts.coverage), abs=1e-3)


def test_tracks(catalog):
    p = make_profile("roguelike")
    assert scoring.surface_overlap(p, catalog.get_game(HADES)) == 0.75
    assert scoring.assign_track(0.75) is Track.SAME
    assert scoring.surface_overlap(p, catalog.get_game(HOLLOW)) == 0.0
    assert scoring.assign_track(0.0) is Track.CROSS
    assert scoring.assign_track(0.30) is Track.SAME and scoring.assign_track(0.2999) is Track.CROSS
    assert scoring.surface_overlap(make_profile(familiar_tags={}), catalog.get_game(HADES)) == 0.0


def test_shared_genes_and_evidence_gate(catalog):
    p = make_profile("roguelike")
    game = catalog.get_game(HADES)
    shared = scoring.shared_genes(p, game)
    assert [s.gene for s in shared] == [
        GeneId.PACE,
        GeneId.CHALLENGE,
        GeneId.PROGRESSION,
        GeneId.IMMERSION,
    ]
    assert all(s.evidence_id in game.evidence_by_id() for s in shared)
    parts = scoring.gene_score(p, game)
    assert scoring.is_recommendable(parts, shared)
    only_c = [s.model_copy(update={"grade": EvidenceGrade.C}) for s in shared]
    assert not scoring.is_recommendable(parts, only_c)  # strong score, weak evidence -> no
    assert scoring.confidence_for(parts, shared) is Confidence.HIGH
    assert scoring.confidence_for(parts, only_c) is Confidence.LOW


def test_threshold_is_inclusive():
    strong = scoring.ScoreParts(similarity=0.72, coverage=1.0, score=scoring.STRONG_SCORE)
    weak = scoring.ScoreParts(similarity=0.7199, coverage=1.0, score=0.7199)
    p = make_profile("roguelike")
    from gamegene.catalog.reader import FixtureCatalog

    shared = scoring.shared_genes(p, FixtureCatalog().get_game(HADES))
    assert scoring.is_recommendable(strong, shared) and not scoring.is_recommendable(weak, shared)


def test_barriers_are_capped_and_mention_unknown_genes(catalog):
    out = scoring.barriers(make_profile("builder"), catalog.get_game(CIV6), overlap=0.0)
    assert 1 <= len(out) <= 3
    assert any("证据不足" in b for b in out) or len(out) == 3
