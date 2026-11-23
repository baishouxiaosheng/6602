from datetime import datetime, timezone

from pydantic import BaseModel, Field, model_validator

from app.domain.enums import GeneId, RecommendationStatus, SourcePriority, Track


class CandidateGeneFact(BaseModel):
    gene_id: GeneId
    user_target: int = Field(ge=0, le=4)
    game_level: int = Field(ge=0, le=4)
    user_weight: int = Field(ge=1, le=2)
    evidence_id: str
    evidence_quote: str
    source_priority: SourcePriority


class CandidateFact(BaseModel):
    appid: int = Field(gt=0, le=4_294_967_295)
    name: str = Field(min_length=1, max_length=256)
    track: Track
    algorithm_rank: int = Field(ge=1, le=5)
    compatibility_score: float = Field(ge=0.0, le=1.0)
    matching_genes: list[CandidateGeneFact] = Field(default_factory=list, max_length=3)
    difference_genes: list[CandidateGeneFact] = Field(default_factory=list, max_length=2)
    descriptors: list[str] = Field(default_factory=list, max_length=20)


class RecommendationItem(BaseModel):
    appid: int = Field(gt=0, le=4_294_967_295)
    name: str = Field(min_length=1, max_length=256)
    track: Track
    ai_rank: int = Field(ge=1, le=3)
    compatibility_score: float = Field(ge=0.0, le=1.0)
    ranking_reason: str = Field(min_length=1, max_length=2_000)
    matched_gene_ids: list[GeneId] = Field(min_length=1, max_length=3)
    evidence_ids: list[str] = Field(min_length=1, max_length=3)
    caution: str | None = Field(default=None, max_length=1_000)


class RecommendationRun(BaseModel):
    run_id: str = Field(min_length=1, max_length=128)
    profile_id: str = Field(min_length=1, max_length=128)
    status: RecommendationStatus
    same_track: list[RecommendationItem] = Field(default_factory=list, max_length=3)
    cross_track: list[RecommendationItem] = Field(default_factory=list, max_length=3)
    message: str | None = Field(default=None, max_length=2_000)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_track_membership_and_ranks(self) -> "RecommendationRun":
        for expected_track, items in (
            (Track.SAME, self.same_track),
            (Track.CROSS, self.cross_track),
        ):
            if any(item.track != expected_track for item in items):
                raise ValueError("Recommendation item is in the wrong track.")
            ranks = [item.ai_rank for item in items]
            if len(ranks) != len(set(ranks)):
                raise ValueError("Ranks must be unique within each track.")
        return self


class StartRecommendationRequest(BaseModel):
    profile_id: str = Field(min_length=1, max_length=128)
    tracks: list[Track] = Field(default_factory=lambda: [Track.SAME, Track.CROSS])

    @model_validator(mode="after")
    def validate_unique_tracks(self) -> "StartRecommendationRequest":
        if not self.tracks or len(self.tracks) != len(set(self.tracks)):
            raise ValueError("At least one unique track is required.")
        return self
