from uuid import uuid4

from app.adapters.llm.base import LLMClient
from app.algorithms.retrieval import retrieve_candidates
from app.domain.enums import RecommendationStatus, Track
from app.domain.llm import RankedCandidate, RankingRequest
from app.domain.profiles import PlayerProfile
from app.domain.recommendations import (
    CandidateFact,
    RecommendationItem,
    RecommendationRun,
    StartRecommendationRequest,
)
from app.persistence.database import Database
from app.persistence.repositories import (
    GameRepository,
    ProfileRepository,
    RecommendationRunRepository,
)
from app.services.errors import ConfigurationUnavailable, NotFoundError, ServiceError
from app.services.jobs import ProgressCallback


class RecommendationService:
    def __init__(self, database: Database, llm: LLMClient | None) -> None:
        self.database = database
        self.llm = llm

    def get(self, run_id: str) -> RecommendationRun:
        with self.database.session_factory() as session:
            run = RecommendationRunRepository(session).get(run_id)
        if run is None:
            raise NotFoundError("Recommendation run", run_id)
        return run

    def create_run(self, request: StartRecommendationRequest) -> RecommendationRun:
        with self.database.session_factory() as session:
            if ProfileRepository(session).get(request.profile_id) is None:
                raise NotFoundError("Profile", request.profile_id)
        run = RecommendationRun(
            run_id=f"r_{uuid4().hex}",
            profile_id=request.profile_id,
            status=RecommendationStatus.RUNNING,
        )
        with self.database.session_factory.begin() as session:
            RecommendationRunRepository(session).save(run)
        return run

    @staticmethod
    def _profile_summary(profile: PlayerProfile) -> str:
        return profile.model_dump_json(
            include={
                "gene_contributions",
                "familiar_genres",
                "hard_filters",
                "soft_descriptor_preferences",
            }
        )

    @staticmethod
    def _validate_track_ranking(
        ranked: list[RankedCandidate],
        candidates: list[CandidateFact],
        expected_track: Track,
    ) -> list[RecommendationItem]:
        by_appid = {item.appid: item for item in candidates}
        if candidates and not ranked:
            raise ServiceError(
                "invalid_llm_ranking",
                f"Qwen returned no {expected_track.value} ranking.",
            )
        if len({item.appid for item in ranked}) != len(ranked):
            raise ServiceError(
                "invalid_llm_ranking", "Qwen returned duplicate candidate AppIDs."
            )
        if len({item.rank for item in ranked}) != len(ranked):
            raise ServiceError(
                "invalid_llm_ranking", "Qwen returned duplicate ranks."
            )

        items: list[RecommendationItem] = []
        for item in ranked:
            candidate = by_appid.get(item.appid)
            if candidate is None or candidate.track != expected_track:
                raise ServiceError(
                    "invalid_llm_ranking",
                    "Qwen selected an AppID outside the supplied track whitelist.",
                )
            allowed_genes = {fact.gene_id for fact in candidate.matching_genes}
            allowed_evidence = {
                fact.evidence_id for fact in candidate.matching_genes
            }
            if (
                not item.matched_gene_ids
                or not set(item.matched_gene_ids).issubset(allowed_genes)
                or not item.evidence_ids
                or not set(item.evidence_ids).issubset(allowed_evidence)
            ):
                raise ServiceError(
                    "invalid_llm_ranking",
                    "Qwen referenced unsupported genes or evidence.",
                )
            items.append(
                RecommendationItem(
                    appid=candidate.appid,
                    name=candidate.name,
                    track=expected_track,
                    ai_rank=item.rank,
                    compatibility_score=candidate.compatibility_score,
                    ranking_reason=item.ranking_reason,
                    matched_gene_ids=item.matched_gene_ids,
                    evidence_ids=item.evidence_ids,
                    caution=item.caution,
                )
            )
        return sorted(items, key=lambda value: value.ai_rank)

    async def execute(
        self,
        run_id: str,
        request: StartRecommendationRequest,
        progress: ProgressCallback,
    ) -> str:
        try:
            return await self._execute(run_id, request, progress)
        except Exception as exc:
            error_code = exc.code if isinstance(exc, ServiceError) else "recommendation_failed"
            failed = RecommendationRun(
                run_id=run_id,
                profile_id=request.profile_id,
                status=RecommendationStatus.FAILED,
                message="Recommendation could not be completed.",
            )
            with self.database.session_factory.begin() as session:
                RecommendationRunRepository(session).save(
                    failed, error_code=error_code
                )
            raise

    async def _execute(
        self,
        run_id: str,
        request: StartRecommendationRequest,
        progress: ProgressCallback,
    ) -> str:
        with self.database.session_factory() as session:
            profile = ProfileRepository(session).get(request.profile_id)
            games = GameRepository(session).list()
        if profile is None:
            raise NotFoundError("Profile", request.profile_id)

        progress("retrieving_candidates", 1, 2)
        retrieval = retrieve_candidates(games, profile)
        same_candidates = (
            retrieval.same_track.candidates if Track.SAME in request.tracks else []
        )
        cross_candidates = (
            retrieval.cross_track.candidates if Track.CROSS in request.tracks else []
        )
        facts_json = {
            "status": retrieval.status.value,
            "same_track": [item.model_dump(mode="json") for item in same_candidates],
            "cross_track": [item.model_dump(mode="json") for item in cross_candidates],
            "drop_counts": retrieval.drop_counts,
        }

        if not same_candidates and not cross_candidates:
            run = RecommendationRun(
                run_id=run_id,
                profile_id=request.profile_id,
                status=RecommendationStatus.NO_MATCH,
                message="No eligible catalog games matched the current profile.",
            )
            with self.database.session_factory.begin() as session:
                RecommendationRunRepository(session).save(
                    run, candidate_facts=facts_json
                )
            progress("completed_no_match", 2, 2)
            return run_id

        if self.llm is None:
            raise ConfigurationUnavailable("Qwen is not configured.")
        progress("ranking_candidates", 1, 2)
        ranking_request = RankingRequest(
            profile_summary=self._profile_summary(profile),
            same_track_candidates=same_candidates,
            cross_track_candidates=cross_candidates,
        )
        ranking = await self.llm.rank_candidates(ranking_request)
        try:
            same_items = self._validate_track_ranking(
                ranking.same_track, same_candidates, Track.SAME
            )
            cross_items = self._validate_track_ranking(
                ranking.cross_track, cross_candidates, Track.CROSS
            )
        except ServiceError as exc:
            if exc.code != "invalid_llm_ranking":
                raise
            ranking_request = ranking_request.model_copy(
                update={
                    "repair_feedback": (
                        "The previous ranking was rejected by deterministic validation. "
                        f"Error: {exc}. Previous JSON: "
                        f"{ranking.model_dump_json()}"
                    )
                }
            )
            ranking = await self.llm.rank_candidates(ranking_request)
            same_items = self._validate_track_ranking(
                ranking.same_track, same_candidates, Track.SAME
            )
            cross_items = self._validate_track_ranking(
                ranking.cross_track, cross_candidates, Track.CROSS
            )
        status = (
            RecommendationStatus.CLOSEST_ONLY
            if retrieval.status == RecommendationStatus.CLOSEST_ONLY
            else RecommendationStatus.OK
        )
        run = RecommendationRun(
            run_id=run_id,
            profile_id=request.profile_id,
            status=status,
            same_track=same_items,
            cross_track=cross_items,
            message=(
                "Closest available matches; formal threshold was not reached."
                if status == RecommendationStatus.CLOSEST_ONLY
                else None
            ),
        )
        with self.database.session_factory.begin() as session:
            RecommendationRunRepository(session).save(
                run,
                candidate_facts=facts_json,
                llm_result=ranking.model_dump(mode="json"),
            )
        progress("completed", 2, 2)
        return run_id
