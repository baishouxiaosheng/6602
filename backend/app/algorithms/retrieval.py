from collections import Counter
from enum import StrEnum

from pydantic import BaseModel, Field

from app.algorithms.candidate_facts import build_candidate_fact
from app.algorithms.hard_filters import DropReason, apply_hard_filters
from app.algorithms.similarity import (
    calculate_similarity,
    is_recommendation_eligible,
)
from app.algorithms.tracks import assign_track
from app.domain.catalog import Game
from app.domain.enums import RecommendationStatus, Track
from app.domain.profiles import PlayerProfile
from app.domain.recommendations import CandidateFact


class TrackResultKind(StrEnum):
    FORMAL = "formal"
    CLOSEST = "closest"
    NO_MATCH = "no_match"


class TrackRetrieval(BaseModel):
    kind: TrackResultKind
    candidates: list[CandidateFact] = Field(default_factory=list, max_length=5)


class RetrievalResult(BaseModel):
    status: RecommendationStatus
    same_track: TrackRetrieval
    cross_track: TrackRetrieval
    drop_counts: dict[str, int] = Field(default_factory=dict)


class _ScoredGame(BaseModel):
    game: Game
    track: Track
    score: float


def _select_track(
    scored: list[_ScoredGame],
    profile: PlayerProfile,
    track: Track,
    *,
    formal_threshold: float,
    closest_floor: float,
    recall_limit: int,
) -> TrackRetrieval:
    track_games = [item for item in scored if item.track == track]
    track_games.sort(key=lambda item: (-item.score, item.game.appid))

    formal = [item for item in track_games if item.score >= formal_threshold]
    selected = formal[:recall_limit]
    kind = TrackResultKind.FORMAL

    if not selected:
        closest = [item for item in track_games if item.score >= closest_floor]
        selected = closest[:recall_limit]
        kind = TrackResultKind.CLOSEST if selected else TrackResultKind.NO_MATCH

    facts: list[CandidateFact] = []
    for rank, item in enumerate(selected, start=1):
        fact = build_candidate_fact(
            item.game,
            profile,
            track=track,
            algorithm_rank=rank,
            compatibility_score=item.score,
        )
        if fact.matching_genes:
            facts.append(fact)

    if not facts:
        return TrackRetrieval(kind=TrackResultKind.NO_MATCH)
    return TrackRetrieval(kind=kind, candidates=facts)


def retrieve_candidates(
    games: list[Game],
    profile: PlayerProfile,
    *,
    formal_threshold: float = 0.72,
    closest_floor: float = 0.55,
    coverage_threshold: float = 0.70,
    track_threshold: float = 0.50,
    recall_limit: int = 5,
) -> RetrievalResult:
    drops: Counter[str] = Counter()
    scored: list[_ScoredGame] = []

    for game in games:
        filter_decision = apply_hard_filters(game, profile)
        if not filter_decision.passed:
            reason = filter_decision.reason or DropReason.NOT_VERIFIED
            drops[reason.value] += 1
            continue

        similarity = calculate_similarity(game, profile)
        if not is_recommendation_eligible(
            game,
            profile,
            similarity,
            minimum_coverage=coverage_threshold,
        ):
            drops["recommendation_ineligible"] += 1
            continue

        track = assign_track(game, profile, threshold=track_threshold)
        if track is None:
            drops[DropReason.MISSING_SURFACE_LABELS.value] += 1
            continue

        scored.append(
            _ScoredGame(
                game=game,
                track=track,
                score=similarity.compatibility_score,
            )
        )

    same = _select_track(
        scored,
        profile,
        Track.SAME,
        formal_threshold=formal_threshold,
        closest_floor=closest_floor,
        recall_limit=recall_limit,
    )
    cross = _select_track(
        scored,
        profile,
        Track.CROSS,
        formal_threshold=formal_threshold,
        closest_floor=closest_floor,
        recall_limit=recall_limit,
    )

    kinds = {same.kind, cross.kind}
    if TrackResultKind.FORMAL in kinds:
        status = RecommendationStatus.OK
    elif TrackResultKind.CLOSEST in kinds:
        status = RecommendationStatus.CLOSEST_ONLY
    else:
        status = RecommendationStatus.NO_MATCH

    return RetrievalResult(
        status=status,
        same_track=same,
        cross_track=cross,
        drop_counts=dict(drops),
    )
