from pathlib import Path

import pytest
from sqlalchemy import inspect

from app.algorithms.profile_fusion import fuse_profile
from app.domain.catalog import GameGene
from app.domain.enums import (
    CatalogStatus,
    GeneId,
    JobStatus,
    JobType,
    LevelSupport,
    RecommendationStatus,
)
from app.domain.jobs import Job, JobError
from app.domain.profiles import OwnedGameRecord
from app.domain.recommendations import RecommendationRun
from app.persistence.database import create_database
from app.persistence.repositories import (
    EvidenceRepository,
    GameRepository,
    JobRepository,
    OwnedGameRepository,
    ProfileRepository,
    RecommendationRunRepository,
)
from tests.factories import make_game, make_submission


@pytest.fixture
def database(tmp_path: Path):
    db = create_database(f"sqlite:///{tmp_path / 'test.db'}")
    db.create_schema()
    yield db
    db.engine.dispose()


def test_schema_creates_all_seven_core_tables(database) -> None:
    tables = set(inspect(database.engine).get_table_names())

    assert tables == {
        "evidence",
        "game_genes",
        "games",
        "jobs",
        "owned_games",
        "profiles",
        "recommendation_runs",
    }


def test_game_round_trip_and_evidence_lookup(database) -> None:
    with database.session_factory.begin() as session:
        stored = GameRepository(session).upsert(make_game(10))
        assert stored.catalog_status == CatalogStatus.VERIFIED

    with database.session_factory() as session:
        loaded = GameRepository(session).get(10)
        evidence = EvidenceRepository(session).get("ev_10_strategy")

    assert loaded is not None
    assert len(loaded.genes) == 9
    assert evidence is not None
    assert evidence.appid == 10
    assert evidence.gene_id == GeneId.STRATEGY


def test_same_game_can_be_reannotated_without_evidence_id_conflicts(database) -> None:
    with database.session_factory.begin() as session:
        repository = GameRepository(session)
        repository.upsert(make_game(10))
        repository.upsert(make_game(10))

    with database.session_factory() as session:
        loaded = GameRepository(session).get(10)
        evidence = EvidenceRepository(session).list_for_game(10)

    assert loaded is not None
    assert len(loaded.genes) == 9
    assert len(evidence) == 9


def test_worse_reannotation_does_not_erase_valid_gene(database) -> None:
    original = make_game(10)
    with database.session_factory.begin() as session:
        GameRepository(session).upsert(original)

    worse = make_game(10)
    worse.catalog_status = CatalogStatus.PARTIAL
    worse.genes = [
        GameGene(
            gene_id=GeneId.STRATEGY,
            level=None,
            suggested_level=4,
            level_support=LevelSupport.UNCERTAIN,
            evidence=[],
        )
    ]
    with database.session_factory.begin() as session:
        GameRepository(session).upsert(worse)

    with database.session_factory() as session:
        loaded = GameRepository(session).get(10)

    assert loaded is not None
    assert loaded.catalog_status == CatalogStatus.VERIFIED
    strategy = next(gene for gene in loaded.genes if gene.gene_id == GeneId.STRATEGY)
    assert strategy.level == 2
    assert strategy.evidence


def test_profile_owned_games_job_and_run_round_trip(database) -> None:
    submission = make_submission()
    profile = fuse_profile(profile_id="p_1", submission=submission, owned_appids={10})

    with database.session_factory.begin() as session:
        ProfileRepository(session).save(profile, questionnaire=submission)
        OwnedGameRepository(session).replace_for_profile(
            "p_1",
            [
                OwnedGameRecord(
                    appid=10,
                    playtime_minutes=120,
                    is_favorite=True,
                    liked_aspects=["exploration"],
                )
            ],
        )
        JobRepository(session).save(
            Job(
                job_id="j_1",
                job_type=JobType.RECOMMENDATION,
                status=JobStatus.FAILED,
                current_step="ranking",
                error=JobError(code="llm_failed", message="Invalid output"),
            )
        )
        RecommendationRunRepository(session).save(
            RecommendationRun(
                run_id="r_1",
                profile_id="p_1",
                status=RecommendationStatus.NO_MATCH,
                message="No eligible candidates.",
            )
        )

    with database.session_factory() as session:
        loaded_profile = ProfileRepository(session).get("p_1")
        owned = OwnedGameRepository(session).list_for_profile("p_1")
        job = JobRepository(session).get("j_1")
        run = RecommendationRunRepository(session).get("r_1")

    assert loaded_profile == profile
    assert owned[0].playtime_minutes == 120
    assert owned[0].is_favorite
    assert job is not None and job.error is not None
    assert job.error.code == "llm_failed"
    assert run is not None and run.status == RecommendationStatus.NO_MATCH
