import pytest
from pydantic import ValidationError

from gamegene.contracts import (
    GENE_ORDER,
    GENES,
    CatalogStatus,
    GameRecord,
    GeneValue,
    RecommendationRun,
    RecommendRequest,
    RunStatus,
    UserProfile,
)
from tests.conftest import make_profile


def test_nine_genes_all_specified():
    assert len(GENE_ORDER) == 9 and set(GENES) == set(GENE_ORDER)


def test_unknown_gene_carries_no_evidence():
    GeneValue(level=None, unknown_reason="no_evidence")
    with pytest.raises(ValidationError):
        GeneValue(level=None, evidence_ids=["ev-1"])
    with pytest.raises(ValidationError):
        GeneValue(level=3, confidence="high")  # known level without evidence


def test_fixture_catalog_is_valid_and_has_partial(catalog):
    games = catalog.list_games()
    assert len(games) >= 16
    assert any(g.status == CatalogStatus.PARTIAL for g in games)
    for g in games:
        GameRecord.model_validate(g.model_dump(mode="json"))  # round trip


def test_verified_needs_five_known_genes(catalog):
    raw = catalog.get_game(999001).model_dump(mode="json")
    raw["status"] = "verified"
    with pytest.raises(ValidationError):
        GameRecord.model_validate(raw)


def test_evidence_must_belong_to_its_gene(catalog):
    raw = catalog.get_game(1145360).model_dump(mode="json")
    raw["genes"]["challenge"]["evidence_ids"] = ["ev-pace-1"]
    with pytest.raises(ValidationError):
        GameRecord.model_validate(raw)


def test_unknown_fields_are_rejected():
    raw = make_profile().model_dump(mode="json")
    raw["surprise"] = 1
    with pytest.raises(ValidationError):
        UserProfile.model_validate(raw)


def test_exclusion_set_combines_owned_and_explicit():
    p = make_profile(owned_appids=[10, 20])
    p.filters.excluded_appids = [30]
    assert p.exclusion_set() == {10, 20, 30}
    p.filters.exclude_owned = False
    assert p.exclusion_set() == {30}


def test_run_status_must_match_payload():
    base = dict(
        run_id="r-1",
        request=RecommendRequest(profile_id="p-x"),
        profile_id="p-x",
        profile_revision=1,
        message="m",
    )
    RecommendationRun(**base, status=RunStatus.NO_MATCH)
    with pytest.raises(ValidationError):
        RecommendationRun(**base, status=RunStatus.OK)  # ok without recommendations
    with pytest.raises(ValidationError):
        RecommendationRun(**base, status=RunStatus.ERROR)  # error without error body
