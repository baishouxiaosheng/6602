from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.domain.catalog import Descriptor, Game, GameGene
from app.domain.enums import (
    CanonicalGenre,
    CatalogStatus,
    GeneId,
    JobStatus,
    JobType,
    LevelSupport,
    RecommendationStatus,
    SemanticReviewStatus,
    SourcePriority,
    TraceStatus,
)
from app.domain.evidence import Evidence
from app.domain.jobs import Job, JobError
from app.domain.profiles import OwnedGameRecord, PlayerProfile, QuestionnaireSubmission
from app.domain.recommendations import RecommendationRun
from app.persistence.models import (
    EvidenceRow,
    GameGeneRow,
    GameRow,
    JobRow,
    OwnedGameRow,
    ProfileRow,
    RecommendationRunRow,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _evidence_to_row(item: Evidence, game_gene_id: int | None = None) -> EvidenceRow:
    return EvidenceRow(
        evidence_id=item.evidence_id,
        game_gene_id=game_gene_id or 0,
        source_type=item.source_type,
        source_priority=item.source_priority.value,
        trace_status=item.trace_status.value,
        level_support=item.level_support.value,
        quote_original=item.quote_original,
        source_locator=item.source_locator,
        source_record_id=item.source_record_id,
        review_id=item.review_id,
        review_author_hash=item.review_author_hash,
    )


def _row_to_evidence(row: EvidenceRow, *, appid: int, gene_id: GeneId) -> Evidence:
    return Evidence(
        evidence_id=row.evidence_id,
        appid=appid,
        gene_id=gene_id,
        source_type=row.source_type,
        source_priority=SourcePriority(row.source_priority),
        trace_status=TraceStatus(row.trace_status),
        level_support=LevelSupport(row.level_support),
        quote_original=row.quote_original,
        source_locator=row.source_locator,
        source_record_id=row.source_record_id,
        review_id=row.review_id,
        review_author_hash=row.review_author_hash,
    )


def _row_to_game(row: GameRow) -> Game:
    genes: list[GameGene] = []
    for gene_row in row.genes:
        gene_id = GeneId(gene_row.gene_id)
        evidence = [
            _row_to_evidence(item, appid=row.appid, gene_id=gene_id)
            for item in gene_row.evidence
        ]
        genes.append(
            GameGene(
                gene_id=gene_id,
                level=gene_row.level,
                suggested_level=gene_row.suggested_level,
                level_support=LevelSupport(gene_row.level_support),
                semantic_review_status=SemanticReviewStatus(
                    gene_row.semantic_review_status
                ),
                evidence=evidence,
            )
        )

    return Game(
        appid=row.appid,
        name=row.name,
        sampling_bucket=(
            CanonicalGenre(row.sampling_bucket) if row.sampling_bucket else None
        ),
        catalog_status=CatalogStatus(row.catalog_status),
        genres=[CanonicalGenre(item) for item in row.genres_json],
        categories=list(row.categories_json),
        platforms=list(row.platforms_json),
        languages=list(row.languages_json),
        social_modes=list(row.social_modes_json),
        price_usd_cents=row.price_usd_cents,
        is_free=row.is_free,
        genes=genes,
        descriptors=[Descriptor.model_validate(item) for item in row.descriptors_json],
    )


class GameRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, appid: int) -> Game | None:
        statement = (
            select(GameRow)
            .where(GameRow.appid == appid)
            .options(selectinload(GameRow.genes).selectinload(GameGeneRow.evidence))
        )
        row = self.session.scalar(statement)
        return _row_to_game(row) if row else None

    def list(self, *, status: CatalogStatus | None = None) -> list[Game]:
        statement = select(GameRow).options(
            selectinload(GameRow.genes).selectinload(GameGeneRow.evidence)
        )
        if status is not None:
            statement = statement.where(GameRow.catalog_status == status.value)
        statement = statement.order_by(GameRow.appid)
        return [_row_to_game(row) for row in self.session.scalars(statement).all()]

    def upsert(
        self,
        game: Game,
        *,
        store_source: dict[str, Any] | None = None,
        store_fetched_at: datetime | None = None,
        preserve_valid_genes: bool = True,
    ) -> Game:
        row = self.session.get(GameRow, game.appid)
        if row is None:
            row = GameRow(
                appid=game.appid,
                name=game.name,
                catalog_status=game.catalog_status.value,
            )
            self.session.add(row)

        if row.catalog_status == CatalogStatus.VERIFIED.value:
            if game.catalog_status != CatalogStatus.VERIFIED:
                next_status = row.catalog_status
            else:
                next_status = game.catalog_status.value
        else:
            next_status = game.catalog_status.value

        row.name = game.name
        row.sampling_bucket = game.sampling_bucket.value if game.sampling_bucket else None
        row.catalog_status = next_status
        row.genres_json = [item.value for item in game.genres]
        row.categories_json = list(game.categories)
        row.platforms_json = list(game.platforms)
        row.languages_json = list(game.languages)
        row.social_modes_json = list(game.social_modes)
        row.price_usd_cents = game.price_usd_cents
        row.is_free = game.is_free
        row.descriptors_json = [item.model_dump(mode="json") for item in game.descriptors]
        if store_source is not None:
            row.store_source_json = store_source
        if store_fetched_at is not None:
            row.store_fetched_at = store_fetched_at

        self.session.flush()
        existing = {item.gene_id: item for item in row.genes}
        for gene in game.genes:
            gene_row = existing.get(gene.gene_id.value)
            if (
                preserve_valid_genes
                and gene_row is not None
                and gene_row.level is not None
                and gene.level is None
            ):
                continue

            if gene_row is None:
                gene_row = GameGeneRow(
                    game_appid=game.appid,
                    gene_id=gene.gene_id.value,
                    level_support=gene.level_support.value,
                    semantic_review_status=gene.semantic_review_status.value,
                )
                self.session.add(gene_row)
                self.session.flush()
            else:
                gene_row.evidence.clear()
                self.session.flush()

            gene_row.level = gene.level
            gene_row.suggested_level = gene.suggested_level
            gene_row.level_support = gene.level_support.value
            gene_row.semantic_review_status = gene.semantic_review_status.value
            gene_row.evidence.extend(
                [_evidence_to_row(item, gene_row.id) for item in gene.evidence]
            )

        self.session.flush()
        self.session.expire(row)
        persisted = self.get(game.appid)
        if persisted is None:  # pragma: no cover - defensive invariant
            raise RuntimeError("Game upsert did not produce a readable record.")
        return persisted


class EvidenceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, evidence_id: str) -> Evidence | None:
        statement = (
            select(EvidenceRow)
            .where(EvidenceRow.evidence_id == evidence_id)
            .options(
                selectinload(EvidenceRow.game_gene).selectinload(GameGeneRow.game)
            )
        )
        row = self.session.scalar(statement)
        if row is None:
            return None
        gene_id = GeneId(row.game_gene.gene_id)
        return _row_to_evidence(row, appid=row.game_gene.game_appid, gene_id=gene_id)

    def list_for_game(self, appid: int) -> list[Evidence]:
        statement = (
            select(EvidenceRow)
            .join(GameGeneRow)
            .where(GameGeneRow.game_appid == appid)
            .options(selectinload(EvidenceRow.game_gene))
            .order_by(EvidenceRow.evidence_id)
        )
        rows = self.session.scalars(statement).all()
        return [
            _row_to_evidence(
                row,
                appid=appid,
                gene_id=GeneId(row.game_gene.gene_id),
            )
            for row in rows
        ]


class ProfileRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save(
        self,
        profile: PlayerProfile,
        *,
        questionnaire: QuestionnaireSubmission | None = None,
        questionnaire_version: str = "v1",
        steam_import_status: str = "not_imported",
    ) -> PlayerProfile:
        row = self.session.get(ProfileRow, profile.profile_id)
        if row is None:
            row = ProfileRow(
                profile_id=profile.profile_id,
                display_name=profile.display_name,
                familiar_genres_json=[],
                hard_filters_json={},
                gene_profile_json=[],
            )
            self.session.add(row)

        row.display_name = profile.display_name
        row.questionnaire_version = questionnaire_version
        if questionnaire is not None:
            row.questionnaire_json = questionnaire.model_dump(mode="json")
        row.free_text = profile.free_text
        row.familiar_genres_json = [
            item.model_dump(mode="json") for item in profile.familiar_genres
        ]
        row.hard_filters_json = profile.hard_filters.model_dump(mode="json")
        row.soft_preferences_json = list(profile.soft_descriptor_preferences)
        row.gene_profile_json = [
            item.model_dump(mode="json") for item in profile.gene_contributions
        ]
        row.owned_appids_json = sorted(profile.owned_appids)
        row.warnings_json = list(profile.warnings)
        row.steam_import_status = steam_import_status
        self.session.flush()
        return profile

    def get(self, profile_id: str) -> PlayerProfile | None:
        row = self.session.get(ProfileRow, profile_id)
        if row is None:
            return None
        return PlayerProfile.model_validate(
            {
                "profile_id": row.profile_id,
                "display_name": row.display_name,
                "gene_contributions": row.gene_profile_json,
                "familiar_genres": row.familiar_genres_json,
                "hard_filters": row.hard_filters_json,
                "soft_descriptor_preferences": row.soft_preferences_json,
                "owned_appids": set(row.owned_appids_json),
                "free_text": row.free_text,
                "warnings": row.warnings_json,
            }
        )

    def get_questionnaire(self, profile_id: str) -> QuestionnaireSubmission | None:
        row = self.session.get(ProfileRow, profile_id)
        if row is None or not row.questionnaire_json:
            return None
        return QuestionnaireSubmission.model_validate(row.questionnaire_json)

    def set_steam_import_status(self, profile_id: str, status: str) -> None:
        row = self.session.get(ProfileRow, profile_id)
        if row is None:
            raise KeyError(profile_id)
        row.steam_import_status = status
        self.session.flush()


class OwnedGameRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_for_profile(
        self, profile_id: str, games: Sequence[OwnedGameRecord]
    ) -> None:
        self.session.execute(
            delete(OwnedGameRow).where(OwnedGameRow.profile_id == profile_id)
        )
        self.session.add_all(
            [
                OwnedGameRow(
                    profile_id=profile_id,
                    appid=item.appid,
                    playtime_minutes=item.playtime_minutes,
                    is_favorite=item.is_favorite,
                    liked_aspects_json=list(item.liked_aspects),
                    participates_in_profile=item.participates_in_profile,
                )
                for item in games
            ]
        )
        self.session.flush()

    def list_for_profile(self, profile_id: str) -> list[OwnedGameRecord]:
        statement = (
            select(OwnedGameRow)
            .where(OwnedGameRow.profile_id == profile_id)
            .order_by(OwnedGameRow.appid)
        )
        return [
            OwnedGameRecord(
                appid=row.appid,
                playtime_minutes=row.playtime_minutes,
                is_favorite=row.is_favorite,
                liked_aspects=row.liked_aspects_json,
                participates_in_profile=row.participates_in_profile,
            )
            for row in self.session.scalars(statement).all()
        ]


class RecommendationRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save(
        self,
        run: RecommendationRun,
        *,
        candidate_facts: dict[str, Any] | None = None,
        llm_result: dict[str, Any] | None = None,
        error_code: str | None = None,
    ) -> RecommendationRun:
        row = self.session.get(RecommendationRunRow, run.run_id)
        if row is None:
            row = RecommendationRunRow(
                run_id=run.run_id,
                profile_id=run.profile_id,
                status=run.status.value,
            )
            self.session.add(row)
        row.status = run.status.value
        row.candidate_facts_json = candidate_facts or {}
        row.llm_result_json = llm_result
        row.validated_result_json = run.model_dump(mode="json")
        row.message = run.message
        row.error_code = error_code
        if run.status != RecommendationStatus.RUNNING:
            row.completed_at = _utc_now()
        self.session.flush()
        return run

    def get(self, run_id: str) -> RecommendationRun | None:
        row = self.session.get(RecommendationRunRow, run_id)
        if row is None or row.validated_result_json is None:
            return None
        return RecommendationRun.model_validate(row.validated_result_json)


class JobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, job: Job) -> Job:
        row = self.session.get(JobRow, job.job_id)
        if row is None:
            row = JobRow(
                job_id=job.job_id,
                job_type=job.job_type.value,
                status=job.status.value,
                current_step=job.current_step,
            )
            self.session.add(row)
        row.job_type = job.job_type.value
        row.status = job.status.value
        row.current_step = job.current_step
        row.processed_items = job.processed_items
        row.total_items = job.total_items
        row.result_ref = job.result_ref
        row.error_code = job.error.code if job.error else None
        row.error_message = job.error.message if job.error else None
        row.error_retryable = job.error.retryable if job.error else False
        row.updated_at = job.updated_at
        self.session.flush()
        return job

    def get(self, job_id: str) -> Job | None:
        row = self.session.get(JobRow, job_id)
        if row is None:
            return None
        error = None
        if row.error_code:
            error = JobError(
                code=row.error_code,
                message=row.error_message or "Unknown job error.",
                retryable=row.error_retryable,
            )
        return Job(
            job_id=row.job_id,
            job_type=JobType(row.job_type),
            status=JobStatus(row.status),
            current_step=row.current_step,
            processed_items=row.processed_items,
            total_items=row.total_items,
            result_ref=row.result_ref,
            error=error,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
