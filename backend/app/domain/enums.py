from enum import StrEnum


class GeneId(StrEnum):
    CHALLENGE = "challenge"
    STRATEGY = "strategy"
    PACE = "pace"
    PROGRESSION = "progression"
    EXPLORATION = "exploration"
    CREATION = "creation"
    NARRATIVE = "narrative"
    IMMERSION = "immersion"
    SOCIAL = "social"


class SourcePriority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TraceStatus(StrEnum):
    VERIFIED = "verified"
    REJECTED = "rejected"


class LevelSupport(StrEnum):
    SUPPORTED = "supported"
    UNCERTAIN = "uncertain"


class SemanticReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class CatalogStatus(StrEnum):
    PENDING = "pending"
    PARTIAL = "partial"
    VERIFIED = "verified"
    FAILED = "failed"


class Track(StrEnum):
    SAME = "same_track"
    CROSS = "cross_track"


class RecommendationStatus(StrEnum):
    RUNNING = "running"
    OK = "ok"
    CLOSEST_ONLY = "closest_only"
    NO_MATCH = "no_match"
    FAILED = "failed"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobType(StrEnum):
    STEAM_IMPORT = "steam_import"
    CATALOG_BATCH = "catalog_batch"
    RECOMMENDATION = "recommendation"


class CanonicalGenre(StrEnum):
    ACTION = "action"
    ADVENTURE = "adventure"
    RPG = "rpg"
    STRATEGY = "strategy"
    SIMULATION = "simulation"
    CASUAL = "casual"


class SocialRequirement(StrEnum):
    ANY = "any"
    NO_MANDATORY_MULTIPLAYER = "no_mandatory_multiplayer"
    MULTIPLAYER_REQUIRED = "multiplayer_required"
