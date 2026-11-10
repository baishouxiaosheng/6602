"""Frozen data contracts. Every JSON file and every cross-module call uses these.

Do NOT edit without an ADR + SCHEMA_VERSION bump: Dev A writes these records,
Dev B reads them, the UI renders them. docs/03-data-contracts.md explains each field.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .genes import GENE_ORDER, GENE_SCHEMA_VERSION, MAX_LEVEL, MIN_LEVEL, GeneId

SCHEMA_VERSION = "1.0"

# Minimum number of known (non-null) genes for a game to be recommendable.
MIN_KNOWN_GENES = 5


def utcnow() -> datetime:
    return datetime.now(UTC)


class Model(BaseModel):
    """Base: reject unknown fields so contract drift fails loudly."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- enums


class Platform(StrEnum):
    WINDOWS = "windows"
    MAC = "mac"
    LINUX = "linux"


class SocialMode(StrEnum):
    SINGLE = "single"  # Steam category "Single-player"
    COOP = "coop"  # any Co-op category
    PVP = "pvp"  # any PvP category
    MMO = "mmo"  # category "MMO"


class SourceType(StrEnum):
    STORE_DESCRIPTION = "store_description"  # official Steam store text
    OFFICIAL_DOCS = "official_docs"  # developer site / manual
    WIKI = "wiki"
    STORE_REVIEW = "store_review"  # a user review (source_ref = recommendationid)
    STORE_TAGS = "store_tags"  # derived from tag votes, no sentence


class EvidenceGrade(StrEnum):
    """A > B > C. See docs/02-gene-schema.md section 4 for the exact rule."""

    A = "A"  # verbatim in official text (store description / official docs)
    B = "B"  # verbatim in a wiki, or in >= 2 independent user reviews
    C = "C"  # single review, fuzzy match only, or tag-derived


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CatalogStatus(StrEnum):
    PENDING = "pending"  # metadata fetched, not annotated yet
    VERIFIED = "verified"  # >= MIN_KNOWN_GENES genes with verified evidence
    PARTIAL = "partial"  # annotated, but too few supported genes: not recommendable
    FAILED = "failed"  # pipeline error; see review_note (Lec 9 CHECK_FAILED)


class Track(StrEnum):
    SAME = "same_track"
    CROSS = "cross_track"


class RunStatus(StrEnum):
    OK = "ok"  # at least one track has a recommendation
    CLOSEST_ONLY = "closest_only"  # nothing strong enough; closest candidate + mismatch
    NO_MATCH = "no_match"  # nothing to show (filters removed all / unsupported mode)
    ERROR = "error"  # failed; ``error`` is filled, saved state is intact


# --------------------------------------------------------------------------- catalog

GeneLevel = Annotated[int, Field(ge=MIN_LEVEL, le=MAX_LEVEL)]


class Evidence(Model):
    evidence_id: str  # unique inside one GameRecord, e.g. "ev-challenge-1"
    gene: GeneId
    quote: str = Field(min_length=8, max_length=400)  # one sentence, copied from the source
    source_type: SourceType
    source_ref: str  # URL, or Steam recommendationid for reviews, or "fixture://..."
    grade: EvidenceGrade
    match_score: float = Field(ge=0.0, le=1.0)  # 1.0 = exact substring of the cached source
    verified_at: datetime


class GeneValue(Model):
    """One gene of one game. ``level is None`` means UNKNOWN, never a guess."""

    level: GeneLevel | None = None
    confidence: Confidence | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    unknown_reason: str | None = None  # e.g. "no_evidence", "evidence_unverified", "low_confidence"

    @model_validator(mode="after")
    def _known_needs_evidence(self) -> GeneValue:
        if self.level is None:
            if self.evidence_ids or self.confidence is not None:
                raise ValueError("unknown gene must not carry evidence or confidence")
        else:
            if not self.evidence_ids:
                raise ValueError("a known gene level requires at least one evidence id")
            if self.confidence is None:
                raise ValueError("a known gene level requires a confidence")
        return self


class PriceInfo(Model):
    currency: str = "USD"
    final_cents: int = Field(ge=0)
    initial_cents: int = Field(ge=0)
    discount_percent: int = Field(ge=0, le=100, default=0)
    fetched_at: datetime


class StoreInfo(Model):
    """Normalised subset of Steam ``appdetails`` (+ tags). Raw JSON stays in data/raw/."""

    short_description: str = ""
    header_image: str | None = None
    store_url: str
    release_date: str | None = None  # as shown by Steam, not parsed
    developers: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)  # Steam genres, lower-case
    tags: list[str] = Field(default_factory=list)  # top <= 20 user tags, lower-case, by votes desc
    platforms: list[Platform] = Field(default_factory=list)
    social_modes: list[SocialMode] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)  # lower-case English names
    is_free: bool = False
    price: PriceInfo | None = None  # None = unknown or free
    review_score_desc: str | None = None  # e.g. "Very Positive"
    total_reviews: int | None = None
    cc: str = "us"
    lang: str = "english"
    fetched_at: datetime


class AnnotationMeta(Model):
    provider: str
    model: str
    prompt_version: str
    gene_schema_version: str = GENE_SCHEMA_VERSION
    annotated_at: datetime


class GameRecord(Model):
    """One catalog entry. Key = appid. Written by Workflow 2, read by Workflow 3."""

    appid: int = Field(gt=0)
    name: str
    status: CatalogStatus
    store: StoreInfo
    genes: dict[GeneId, GeneValue]
    evidence: list[Evidence] = Field(default_factory=list)
    annotation: AnnotationMeta | None = None
    review_note: str | None = None  # why PARTIAL / FAILED, for a human reviewer

    @model_validator(mode="after")
    def _consistent(self) -> GameRecord:
        if set(self.genes) != set(GENE_ORDER):
            raise ValueError("genes must contain exactly the nine gene ids")
        by_id = {e.evidence_id: e for e in self.evidence}
        if len(by_id) != len(self.evidence):
            raise ValueError("duplicate evidence_id")
        for gene, value in self.genes.items():
            for eid in value.evidence_ids:
                if eid not in by_id:
                    raise ValueError(f"{gene}: evidence id {eid!r} not in evidence list")
                if by_id[eid].gene != gene:
                    raise ValueError(f"{gene}: evidence {eid!r} belongs to {by_id[eid].gene}")
        if self.status == CatalogStatus.VERIFIED:
            if self.known_gene_count < MIN_KNOWN_GENES:
                raise ValueError(f"VERIFIED needs >= {MIN_KNOWN_GENES} known genes")
            if self.annotation is None:
                raise ValueError("VERIFIED needs annotation metadata")
        return self

    @property
    def known_gene_count(self) -> int:
        return sum(1 for v in self.genes.values() if v.level is not None)

    def evidence_by_id(self) -> dict[str, Evidence]:
        return {e.evidence_id: e for e in self.evidence}


# --------------------------------------------------------------------------- profile


class GenePreference(Model):
    target: float = Field(ge=MIN_LEVEL, le=MAX_LEVEL)  # desired level on the 0-4 scale
    weight: float = Field(ge=0.0, le=1.0)  # how much this gene matters to the user


class HardFilters(Model):
    """Deterministic exclusions. Empty list / None = no constraint."""

    platforms: list[Platform] = Field(default_factory=list)  # game must support ANY of these
    social_modes: list[SocialMode] = Field(default_factory=list)  # game must offer ANY of these
    max_price_cents: int | None = Field(default=None, ge=0)  # unknown price passes; free passes
    required_language: str | None = None  # lower-case English name, e.g. "simplified chinese"
    exclude_owned: bool = True
    excluded_tags: list[str] = Field(default_factory=list)  # lower-case; matches genres or tags
    excluded_appids: list[int] = Field(default_factory=list)


class OwnedGame(Model):
    appid: int
    name: str = ""
    playtime_minutes: int = Field(ge=0, default=0)


class ProfileSources(Model):
    interview_version: str
    answers: dict[str, list[str]]  # question id -> chosen option ids (single choice = 1 item)
    steam_id: str | None = None  # 64-bit id as string
    library_imported_at: datetime | None = None
    library_matched_appids: list[int] = Field(default_factory=list)  # owned AND in catalog


class UserProfile(Model):
    """Written by Workflow 1. Key = profile_id. Revisions are kept by the store."""

    profile_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{2,39}$")
    display_name: str = Field(min_length=1, max_length=40)
    genes: dict[GeneId, GenePreference]
    familiar_tags: dict[str, float] = Field(default_factory=dict)  # lower-case tag -> 0..1
    filters: HardFilters = Field(default_factory=HardFilters)
    owned_appids: list[int] = Field(default_factory=list)
    sources: ProfileSources
    gene_schema_version: str = GENE_SCHEMA_VERSION

    @model_validator(mode="after")
    def _nine_genes(self) -> UserProfile:
        if set(self.genes) != set(GENE_ORDER):
            raise ValueError("genes must contain exactly the nine gene ids")
        for tag, w in self.familiar_tags.items():
            if tag != tag.lower() or not 0.0 <= w <= 1.0:
                raise ValueError(f"familiar tag {tag!r} must be lower-case with weight in [0,1]")
        return self

    def exclusion_set(self) -> set[int]:
        """AppIDs that may never be recommended to this user."""
        ids = set(self.filters.excluded_appids)
        if self.filters.exclude_owned:
            ids |= set(self.owned_appids)
        return ids


class ProfileRequest(Model):
    """Input of Workflow 1 (the 'webhook body' of the profile form)."""

    profile_id: str | None = None  # None = create; existing id = revise (new revision)
    display_name: str
    answers: dict[str, list[str]]
    filters: HardFilters = Field(default_factory=HardFilters)
    steam_id_or_url: str | None = None  # optional public library import


# --------------------------------------------------------------------------- interview


class InterviewOption(Model):
    id: str
    label_zh: str
    label_en: str
    gene_deltas: dict[GeneId, float] = Field(default_factory=dict)  # for kind="gene"
    tags: list[str] = Field(default_factory=list)  # for kind="tags" (lower-case)


class InterviewQuestion(Model):
    id: str
    kind: Literal["gene", "tags"]
    prompt_zh: str
    prompt_en: str
    min_choices: int = 1
    max_choices: int = 1
    options: list[InterviewOption]


class InterviewSpec(Model):
    version: str
    questions: list[InterviewQuestion]


# --------------------------------------------------------------------------- recommendation

SUPPORTED_MODES: tuple[str, ...] = ("both", "same_track", "cross_track")


class RecommendRequest(Model):
    """Input of Workflow 3. ``mode`` is a plain string on purpose: the ROUTER decides
    what an unknown mode means (test 3), not the parser."""

    profile_id: str
    mode: str = "both"
    top_k: int = Field(default=3, ge=1, le=10)
    request_id: str | None = None  # optional idempotency key; a repeat returns the saved run


class SharedGene(Model):
    gene: GeneId
    user_target: float
    game_level: int
    evidence_id: str
    quote: str
    grade: EvidenceGrade
    source_type: SourceType
    source_ref: str


class Reason(Model):
    gene: GeneId
    text: str = Field(max_length=300)
    evidence_id: str


class Explanation(Model):
    headline: str = Field(max_length=120)
    reasons: list[Reason]
    mismatch: str | None = Field(default=None, max_length=300)  # filled for the closest candidate
    generated_by: Literal["llm", "template"]


class Recommendation(Model):
    appid: int
    name: str
    track: Track
    score: float = Field(ge=0.0, le=1.0)
    similarity: float = Field(ge=0.0, le=1.0)
    coverage: float = Field(ge=0.0, le=1.0)
    surface_overlap: float = Field(ge=0.0, le=1.0)
    confidence: Confidence
    shared_genes: list[SharedGene]
    explanation: Explanation
    barriers: list[str] = Field(default_factory=list)  # surface-level turn-offs, plain sentences
    price: PriceInfo | None = None
    is_free: bool = False
    store_url: str
    header_image: str | None = None


class TraceStep(Model):
    """One entry of the execution trace = the evidence chain the course asks for
    (request -> selected route -> intermediate data -> stored result)."""

    step: str  # e.g. "validate", "route", "hard_filters", "score", "llm_explain", "save"
    branch: str  # which branch was taken, e.g. "mode=both", "fallback=template"
    detail: dict = Field(default_factory=dict)
    at: datetime = Field(default_factory=utcnow)


class LLMUsage(Model):
    provider: str
    model: str
    calls: int = 0
    retries: int = 0
    fallbacks: int = 0  # explanations that fell back to the template


class RecommendationRun(Model):
    """Written by Workflow 3. Key = run_id. Immutable once saved."""

    run_id: str
    request: RecommendRequest
    profile_id: str
    profile_revision: int
    status: RunStatus
    message: str  # one human-readable sentence explaining the status
    same_track: list[Recommendation] = Field(default_factory=list)
    cross_track: list[Recommendation] = Field(default_factory=list)
    closest: Recommendation | None = None  # only for CLOSEST_ONLY
    candidates_total: int = 0
    candidates_after_filters: int = 0
    filter_drops: dict[str, int] = Field(default_factory=dict)  # reason -> count
    llm: LLMUsage | None = None
    error: dict | None = None  # ErrorResponse.model_dump() when status == ERROR
    trace: list[TraceStep] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def _status_matches_payload(self) -> RecommendationRun:
        has_recs = bool(self.same_track or self.cross_track)
        if self.status == RunStatus.OK and not has_recs:
            raise ValueError("status ok requires at least one recommendation")
        if self.status != RunStatus.OK and has_recs:
            raise ValueError("only status ok may carry track recommendations")
        if (self.status == RunStatus.CLOSEST_ONLY) != (self.closest is not None):
            raise ValueError("closest is set if and only if status is closest_only")
        if (self.status == RunStatus.ERROR) != (self.error is not None):
            raise ValueError("error is set if and only if status is error")
        return self


class RunSummary(Model):
    run_id: str
    profile_id: str
    status: RunStatus
    created_at: datetime
    titles: list[str] = Field(default_factory=list)


class CatalogStats(Model):
    total: int
    by_status: dict[str, int]
    source: str  # "fixture" or "store"
