from pathlib import Path

import pytest

from app.adapters.llm.fake import FakeLLMClient
from app.algorithms.retrieval import retrieve_candidates
from app.domain.enums import CanonicalGenre, CatalogStatus, GeneId, Track
from app.domain.llm import RankedCandidate, RankingResult
from app.domain.profiles import FamiliarGenre, HardFilters
from app.domain.recommendations import StartRecommendationRequest
from app.persistence.database import create_database
from app.persistence.repositories import GameRepository
from app.services.catalog import CatalogService
from app.services.evidence_text import quote_is_present
from app.services.fixture_catalog import load_fixture_catalog
from app.services.profile import ProfileService
from app.services.recommendation import RecommendationService
from tests.factories import make_submission


FIXTURE = (
    Path(__file__).parents[1]
    / "data"
    / "fixtures"
    / "test_games_fixture.json"
)


def test_fixture_conversion_is_evidence_grounded_and_demo_ready() -> None:
    fixture = load_fixture_catalog(FIXTURE)

    assert len(fixture.games) == 5
    assert all(item.game.catalog_status == CatalogStatus.VERIFIED for item in fixture.games)
    assert all(item.game.platforms == ["windows"] for item in fixture.games)
    assert all(item.game.languages == ["english"] for item in fixture.games)

    by_appid = {item.game.appid: item.game for item in fixture.games}
    assert by_appid[558990].sampling_bucket == CanonicalGenre.SIMULATION
    assert {item.descriptor_id for item in by_appid[558990].descriptors} == {
        "alchemy",
        "engineering",
    }
    assert "online_co_op" in by_appid[413150].social_modes
    assert next(
        gene for gene in by_appid[1135690].genes if gene.gene_id == GeneId.NARRATIVE
    ).level == 2

    for game in by_appid.values():
        accepted = {
            evidence.evidence_id
            for gene in game.genes
            for evidence in gene.evidence
        }
        assert all(descriptor.evidence_ids for descriptor in game.descriptors)
        assert all(
            set(descriptor.evidence_ids).issubset(accepted)
            for descriptor in game.descriptors
        )


def test_evidence_matching_normalizes_quotes_and_whitespace() -> None:
    assert quote_is_present(
        "life you're unpacking",
        ["Learning clues about the life you’re   unpacking."],
    )


def test_fixture_import_is_idempotent(tmp_path: Path) -> None:
    database = create_database(f"sqlite:///{tmp_path / 'fixture.db'}")
    database.create_schema()
    service = CatalogService(database, object(), None)  # type: ignore[arg-type]

    first = service.import_fixture(FIXTURE)
    second = service.import_fixture(FIXTURE)

    assert len(first) == len(second) == 5
    with database.session_factory() as session:
        persisted = GameRepository(session).list()
    assert len(persisted) == 5
    assert all(item.catalog_status == CatalogStatus.VERIFIED for item in persisted)
    database.engine.dispose()


@pytest.mark.asyncio
async def test_five_game_fixture_runs_through_dual_track_recommendation(
    tmp_path: Path,
) -> None:
    database = create_database(f"sqlite:///{tmp_path / 'recommendation.db'}")
    database.create_schema()
    catalog = CatalogService(database, object(), None)  # type: ignore[arg-type]
    games = catalog.import_fixture(FIXTURE)

    submission = make_submission(
        target=2,
        important=[GeneId.CHALLENGE, GeneId.PACE, GeneId.EXPLORATION],
        familiar_genres=[
            FamiliarGenre(genre=CanonicalGenre.ACTION, rank=1, weight=3)
        ],
        hard_filters=HardFilters(platforms=["windows"], required_language="english"),
    )
    profile = ProfileService(database, None).create(submission)
    retrieval = retrieve_candidates(games, profile)
    assert retrieval.same_track.candidates
    assert retrieval.cross_track.candidates
    assert retrieval.same_track.candidates[0].appid == 1145360

    def ranked(candidate, rank: int) -> RankedCandidate:
        match = candidate.matching_genes[0]
        return RankedCandidate(
            appid=candidate.appid,
            rank=rank,
            ranking_reason="Fixture-backed compatibility match.",
            matched_gene_ids=[match.gene_id],
            evidence_ids=[match.evidence_id],
        )

    llm = FakeLLMClient(
        ranking_result=RankingResult(
            same_track=[ranked(retrieval.same_track.candidates[0], 1)],
            cross_track=[ranked(retrieval.cross_track.candidates[0], 1)],
        )
    )
    service = RecommendationService(database, llm)
    request = StartRecommendationRequest(
        profile_id=profile.profile_id,
        tracks=[Track.SAME, Track.CROSS],
    )
    run = service.create_run(request)
    await service.execute(run.run_id, request, lambda *_: None)
    result = service.get(run.run_id)

    assert result.status.value == "ok"
    assert result.same_track[0].appid == 1145360
    assert result.cross_track
    assert llm.calls["rank_candidates"] == 1
    database.engine.dispose()
