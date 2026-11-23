import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.domain.catalog import Descriptor, Game, GameGene
from app.domain.enums import (
    CanonicalGenre,
    CatalogStatus,
    GeneId,
    LevelSupport,
    SemanticReviewStatus,
    SourcePriority,
    TraceStatus,
)
from app.domain.evidence import Evidence
from app.services.errors import ServiceError
from app.services.evidence_text import normalize_evidence_text


GENE_PATTERNS: dict[GeneId, tuple[str, ...]] = {
    GeneId.CHALLENGE: (
        "challenging", "challenge", "tough", "difficulty", "difficult",
        "instant-death", "permadeath", "survive", "survival", "danger",
        "highscore",
    ),
    GeneId.STRATEGY: (
        "strategically", "strategic", "strategy", "tactical", "tactics",
        "plan", "manage", "management", "decisions", "choices", "choose",
        "resources", "optimize", "carefully", "logical deduction", "builds",
    ),
    GeneId.PROGRESSION: (
        "progression", "upgrades", "upgrade", "unlock", "level up",
        "abilities", "grow", "stronger", "research", "technology",
        "advance", "rewards", "career", "improve",
    ),
    GeneId.EXPLORATION: (
        "exploration", "explore", "discover", "open world", "secrets",
        "hidden", "venture", "journey", "locations", "paths",
        "mysteries", "investigator",
    ),
    GeneId.CREATION: (
        "create", "creation", "build", "building", "craft", "customize",
        "customisation", "design", "editor", "construct", "assemble",
        "deckbuilder", "character builds", "sandbox",
    ),
    GeneId.NARRATIVE: (
        "storytelling", "narrative", "story", "stories", "dialogue", "mystery",
        "relationships", "choices and consequences",
    ),
    GeneId.IMMERSION: (
        "atmosphere", "atmospheric", "immersive", "first-person", "horror",
        "environment", "wilderness", "hand-drawn", "vr",
    ),
}

PACE_SLOW = (
    "no timers", "without timed input", "turn-based", "relaxing", "peaceful",
    "calming", "meditative", "take a break", "stop time", "pause",
)
PACE_FAST = (
    "fast-paced", "fast paced", "breakneck", "fast, fluid", "intense",
    "real-time", "simultaneous", "adrenaline", "rapid",
)
PACE_NEUTRAL = PACE_SLOW + PACE_FAST + ("pace",)
SOCIAL_PATTERNS = ("multiplayer", "co-op", "cooperative", "competitive", "players", "friends")

# Hand-reviewed anchors take precedence over the generic vocabulary.  They are
# short fragments of the stored official description, not model-generated text.
EVIDENCE_HINTS: dict[tuple[int, GeneId], tuple[str, ...]] = {
    (460950, GeneId.STRATEGY): ("countless methods of completion",),
    (460950, GeneId.IMMERSION): ("stylish neo-noir",),
    (753640, GeneId.CHALLENGE): ("dangerous reaches of space",),
    (753640, GeneId.STRATEGY): ("change with the passage of time",),
    (753640, GeneId.IMMERSION): ("constantly evolving solar system",),
    (632470, GeneId.STRATEGY): ("unprecedented freedom of choice",),
    (632470, GeneId.IMMERSION): ("brought to life with full english voiceover",),
    (391540, GeneId.PACE): ("time your attacks",),
    (391540, GeneId.EXPLORATION): ("find your way out",),
    (391540, GeneId.IMMERSION): ("art and soundtrack brimming with personality",),
    (646570, GeneId.CHALLENGE): ("choose a risky or safe path",),
    (646570, GeneId.PROGRESSION): ("enhance your deck",),
    (427520, GeneId.CHALLENGE): ("range of interesting challenges",),
    (427520, GeneId.PROGRESSION): ("researching technologies",),
    (255710, GeneId.STRATEGY): ("balancing essential requirements",),
    (255710, GeneId.PROGRESSION): ("level up and become more efficient",),
    (255710, GeneId.IMMERSION): ("air of authenticity",),
    (292030, GeneId.IMMERSION): ("dark fantasy open world",),
    (1003590, GeneId.CHALLENGE): ("puzzle games of all time",),
    (1003590, GeneId.STRATEGY): ("get out of a sticky situation",),
    (1003590, GeneId.IMMERSION): ("pulse, dance, shimmer, and explode in perfect sync",),
    (431240, GeneId.CHALLENGE): ("against 11 other golfers",),
    (431240, GeneId.STRATEGY): ("courses with unique mechanics",),
}

# These tempting keyword matches describe packaging, authorship, or workshop
# browsing rather than the player's experience, so they are deliberately gated.
FORCED_UNSUPPORTED: set[tuple[int, GeneId]] = {
    (379720, GeneId.NARRATIVE),
    (292030, GeneId.PROGRESSION),
    (1158310, GeneId.CREATION),
    (294100, GeneId.EXPLORATION),
    (1794680, GeneId.EXPLORATION),
}

DESCRIPTOR_PATTERNS = {
    "horror": ("horror",),
    "open_world": ("open world",),
    "puzzle": ("puzzle",),
    "turn_based": ("turn-based",),
    "roguelite": ("roguelite", "rogue-like"),
    "building": ("building", "build", "create"),
    "story_rich": ("story", "narrative"),
    "multiplayer": ("multiplayer", "co-op"),
    "relaxing": ("relaxing", "peaceful", "meditative", "zen"),
}


@dataclass(frozen=True)
class CuratedCatalog:
    games: list[Game]
    store_sources: dict[int, dict]
    captured_at: datetime


def _passages(snapshot: dict) -> list[str]:
    text = "\n".join(
        [snapshot.get("short_description") or "", snapshot.get("detailed_description") or ""]
    )
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [part.strip() for part in parts if part.strip()]


def _find_quote(passages: list[str], patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        wanted = normalize_evidence_text(pattern)
        for passage in passages:
            normalized = normalize_evidence_text(passage)
            if re.search(rf"(?<!\w){re.escape(wanted)}(?!\w)", normalized):
                return passage[:8000]
    return None


def _pace_patterns(level: int) -> tuple[str, ...]:
    if level <= 1:
        return PACE_SLOW
    if level >= 3:
        return PACE_FAST
    return PACE_NEUTRAL


def _social_evidence(snapshot: dict, level: int) -> tuple[str, SourcePriority, str] | None:
    passages = _passages(snapshot)
    if level > 0:
        quote = _find_quote(passages, SOCIAL_PATTERNS)
        if quote:
            return quote, SourcePriority.HIGH, "appdetails.about_the_game"
        for category in snapshot.get("categories") or []:
            normalized = normalize_evidence_text(category)
            if any(item in normalized for item in ("multi-player", "co-op", "pvp")):
                return category, SourcePriority.MEDIUM, "appdetails.categories"
    if level == 0 and "Single-player" in (snapshot.get("categories") or []):
        return "Single-player", SourcePriority.MEDIUM, "appdetails.categories"
    return None


def _evidence_for_gene(snapshot: dict, gene_id: GeneId, level: int):
    key = (int(snapshot["appid"]), gene_id)
    if key in FORCED_UNSUPPORTED:
        return None
    if gene_id == GeneId.SOCIAL:
        return _social_evidence(snapshot, level)
    passages = _passages(snapshot)
    patterns = EVIDENCE_HINTS.get(key)
    if patterns is None:
        patterns = _pace_patterns(level) if gene_id == GeneId.PACE else GENE_PATTERNS[gene_id]
    quote = _find_quote(passages, patterns)
    if quote is None:
        return None
    return quote, SourcePriority.HIGH, "appdetails.about_the_game"


def _build_game(snapshot: dict, levels: dict[str, int | None]) -> Game:
    appid = int(snapshot["appid"])
    genes: list[GameGene] = []
    evidence_by_id: dict[str, Evidence] = {}
    for gene_id in GeneId:
        suggested = levels.get(gene_id.value)
        evidence: list[Evidence] = []
        if suggested is not None:
            source = _evidence_for_gene(snapshot, gene_id, suggested)
            if source is not None:
                quote, priority, locator = source
                item = Evidence(
                    evidence_id=f"curated_{appid}_{gene_id.value}",
                    appid=appid,
                    gene_id=gene_id,
                    source_type=(
                        "official_description"
                        if priority == SourcePriority.HIGH
                        else "genre_mapping"
                    ),
                    source_priority=priority,
                    trace_status=TraceStatus.VERIFIED,
                    level_support=LevelSupport.SUPPORTED,
                    quote_original=quote,
                    source_locator=locator,
                    source_record_id=f"steam_{appid}_2026_11_22",
                )
                evidence.append(item)
                evidence_by_id[item.evidence_id] = item
        supported = suggested is not None and bool(evidence)
        genes.append(
            GameGene(
                gene_id=gene_id,
                level=suggested if supported else None,
                suggested_level=suggested,
                level_support=(
                    LevelSupport.SUPPORTED if supported else LevelSupport.UNCERTAIN
                ),
                semantic_review_status=SemanticReviewStatus.APPROVED,
                evidence=evidence,
            )
        )

    descriptors: list[Descriptor] = []
    for descriptor_id, patterns in DESCRIPTOR_PATTERNS.items():
        matching = [
            item.evidence_id
            for item in evidence_by_id.values()
            if any(
                normalize_evidence_text(pattern) in normalize_evidence_text(item.quote_original)
                for pattern in patterns
            )
        ]
        if matching:
            descriptors.append(
                Descriptor(
                    descriptor_id=descriptor_id,
                    value=True,
                    evidence_ids=matching[:2],
                )
            )

    known = sum(item.level is not None for item in genes)
    strong = sum(
        item.level is not None
        and any(e.source_priority in {SourcePriority.HIGH, SourcePriority.MEDIUM} for e in item.evidence)
        for item in genes
    )
    status = CatalogStatus.VERIFIED if known >= 5 and strong >= 3 else CatalogStatus.PARTIAL
    return Game(
        appid=appid,
        name=snapshot["name"],
        sampling_bucket=CanonicalGenre(snapshot["sampling_bucket"]),
        catalog_status=status,
        genres=[CanonicalGenre(item) for item in snapshot["genres"]],
        categories=list(snapshot.get("categories") or []),
        platforms=list(snapshot.get("platforms") or []),
        languages=list(snapshot.get("languages") or []),
        social_modes=list(snapshot.get("social_modes") or []),
        price_usd_cents=snapshot.get("price_usd_cents"),
        is_free=bool(snapshot.get("is_free", False)),
        genes=genes,
        descriptors=descriptors,
    )


def load_curated_catalog(snapshot_path: Path, levels_path: Path) -> CuratedCatalog:
    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        levels = json.loads(levels_path.read_text(encoding="utf-8"))
        captured_at = datetime.fromisoformat(payload["captured_at"]).replace(tzinfo=timezone.utc)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise ServiceError("invalid_curated_catalog", "Curated catalog inputs are invalid.") from exc
    snapshots = payload.get("games") or []
    if len(snapshots) != 30 or len(levels) != 30:
        raise ServiceError("invalid_curated_catalog", "Curated MVP catalog requires 30 games.")
    games = [_build_game(item, levels[str(item["appid"])]) for item in snapshots]
    if len({game.appid for game in games}) != 30:
        raise ServiceError("invalid_curated_catalog", "Curated catalog AppIDs are not unique.")
    return CuratedCatalog(
        games=games,
        store_sources={int(item["appid"]): item for item in snapshots},
        captured_at=captured_at,
    )
