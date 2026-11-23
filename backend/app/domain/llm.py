from pydantic import BaseModel, ConfigDict, Field

from app.domain.catalog import Descriptor, GameGene
from app.domain.enums import GeneId, Track
from app.domain.recommendations import CandidateFact


class OfficialAnnotationRequest(BaseModel):
    appid: int = Field(gt=0)
    name: str
    official_passages: list[str]
    genres: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)


class OfficialAnnotationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    genes: list[GameGene]
    descriptors: list[Descriptor] = Field(default_factory=list)


class ReviewPassage(BaseModel):
    review_id: str
    author_hash: str
    text: str


class ReviewSupplementRequest(BaseModel):
    appid: int = Field(gt=0)
    missing_gene_ids: list[GeneId]
    passages: list[ReviewPassage]


class ReviewSupplementResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    genes: list[GameGene]


class PreferenceParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2_000)


class RankingRequest(BaseModel):
    profile_summary: str = Field(min_length=1, max_length=8_000)
    same_track_candidates: list[CandidateFact] = Field(default_factory=list, max_length=5)
    cross_track_candidates: list[CandidateFact] = Field(default_factory=list, max_length=5)
    repair_feedback: str | None = Field(default=None, max_length=12_000)


class RankedCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    appid: int = Field(gt=0)
    rank: int = Field(ge=1, le=3)
    ranking_reason: str
    matched_gene_ids: list[GeneId]
    evidence_ids: list[str]
    caution: str | None = None


class RankingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    same_track: list[RankedCandidate] = Field(default_factory=list, max_length=3)
    cross_track: list[RankedCandidate] = Field(default_factory=list, max_length=3)
