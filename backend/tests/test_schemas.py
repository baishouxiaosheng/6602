import pytest
from pydantic import ValidationError

from app.domain.catalog import Game, GameGene
from app.domain.enums import (
    CanonicalGenre,
    GeneId,
    LevelSupport,
    SourcePriority,
    TraceStatus,
)
from app.domain.evidence import Evidence
from app.domain.jobs import Job, JobError
from app.domain.enums import JobStatus, JobType
from app.domain.profiles import FamiliarGenre, QuestionnaireSubmission
from app.domain.recommendations import RecommendationItem, RecommendationRun
from app.domain.enums import RecommendationStatus, Track


def all_gene_targets() -> dict[GeneId, int]:
    return {gene_id: 2 for gene_id in GeneId}


def test_questionnaire_requires_all_nine_genes() -> None:
    targets = all_gene_targets()
    targets.pop(GeneId.SOCIAL)

    with pytest.raises(ValidationError, match="All nine gene targets"):
        QuestionnaireSubmission(
            display_name="Alice",
            gene_targets=targets,
            familiar_genres=[
                FamiliarGenre(genre=CanonicalGenre.RPG, rank=1, weight=3)
            ],
        )


def test_questionnaire_limits_important_genes() -> None:
    with pytest.raises(ValidationError):
        QuestionnaireSubmission(
            display_name="Alice",
            gene_targets=all_gene_targets(),
            important_genes=[
                GeneId.CHALLENGE,
                GeneId.STRATEGY,
                GeneId.PACE,
                GeneId.NARRATIVE,
            ],
            familiar_genres=[
                FamiliarGenre(genre=CanonicalGenre.RPG, rank=1, weight=3)
            ],
        )


def test_non_null_game_gene_requires_verified_evidence() -> None:
    with pytest.raises(ValidationError, match="verified evidence"):
        GameGene(
            gene_id=GeneId.STRATEGY,
            level=3,
            level_support=LevelSupport.SUPPORTED,
            evidence=[],
        )


def test_low_priority_evidence_requires_review_identity() -> None:
    with pytest.raises(ValidationError, match="review_id"):
        Evidence(
            evidence_id="ev_1",
            appid=10,
            gene_id=GeneId.CHALLENGE,
            source_type="user_review",
            source_priority=SourcePriority.LOW,
            trace_status=TraceStatus.VERIFIED,
            level_support=LevelSupport.SUPPORTED,
            quote_original="This game requires precise timing.",
            source_locator="reviews[0]",
            source_record_id="reviews_10",
        )


def test_sampling_bucket_must_be_official_genre() -> None:
    with pytest.raises(ValidationError, match="sampling_bucket"):
        Game(
            appid=10,
            name="Example",
            sampling_bucket=CanonicalGenre.ACTION,
            genres=[CanonicalGenre.RPG],
        )


def test_failed_job_requires_error() -> None:
    with pytest.raises(ValidationError, match="requires an error"):
        Job(
            job_id="j_1",
            job_type=JobType.CATALOG_BATCH,
            status=JobStatus.FAILED,
        )

    valid = Job(
        job_id="j_2",
        job_type=JobType.CATALOG_BATCH,
        status=JobStatus.FAILED,
        error=JobError(code="upstream_error", message="Steam failed"),
    )
    assert valid.error is not None


def test_recommendation_ranks_are_unique_per_track() -> None:
    item = RecommendationItem(
        appid=10,
        name="Example",
        track=Track.SAME,
        ai_rank=1,
        compatibility_score=0.8,
        ranking_reason="Matches the user's preferred strategy depth.",
        matched_gene_ids=[GeneId.STRATEGY],
        evidence_ids=["ev_1"],
    )

    with pytest.raises(ValidationError, match="Ranks must be unique"):
        RecommendationRun(
            run_id="r_1",
            profile_id="p_1",
            status=RecommendationStatus.OK,
            same_track=[item, item.model_copy(update={"appid": 11})],
        )
