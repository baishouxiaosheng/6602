import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
from app.services.evidence_text import normalize_evidence_text, quote_is_present


@dataclass(frozen=True)
class FixtureGame:
    game: Game
    store_source: dict[str, Any]


@dataclass(frozen=True)
class FixtureCatalog:
    games: list[FixtureGame]
    captured_at: datetime
    fixture_name: str


def _canonical_genres(values: list[str]) -> list[CanonicalGenre]:
    allowed = CanonicalGenre._value2member_map_
    result: list[CanonicalGenre] = []
    for value in values:
        genre = allowed.get(value.strip().casefold())
        if genre is not None and genre not in result:
            result.append(genre)
    return result


def _sampling_bucket(role: str, genres: list[CanonicalGenre]) -> CanonicalGenre:
    requested = role.split("桶", 1)[0].strip().casefold()
    requested_genre = CanonicalGenre._value2member_map_.get(requested)
    if requested_genre in genres:
        return requested_genre
    if not genres:
        raise ServiceError(
            "invalid_fixture", "A fixture game has no canonical Steam genre."
        )
    return genres[0]


def _social_modes(categories: list[str]) -> list[str]:
    normalized = {normalize_evidence_text(item) for item in categories}
    result: list[str] = []
    markers = (
        ("single-player", "single_player"),
        ("multi-player", "multiplayer"),
        ("co-op", "co_op"),
        ("online co-op", "online_co_op"),
        ("online pvp", "online_pvp"),
        ("pvp", "pvp"),
    )
    for source, value in markers:
        if any(source in item for item in normalized) and value not in result:
            result.append(value)
    return result


def _descriptor_terms(value: str) -> set[str]:
    aliases = {"life": "liv", "live": "liv"}
    related = {
        "alchemy": {"alche", "potio"},
        "engineering": {"engin", "machi", "desig", "build"},
        "farming": {"farm", "land", "field"},
    }
    terms: set[str] = set()
    for token in re.findall(r"[a-z0-9]+", normalize_evidence_text(value)):
        if len(token) < 3:
            continue
        terms.add(aliases.get(token, token[:5]))
        terms.update(related.get(token, set()))
    return terms


def _descriptor_evidence_ids(
    descriptor: str, evidence: list[Evidence]
) -> list[str]:
    wanted = _descriptor_terms(descriptor)
    scored: list[tuple[int, str]] = []
    for item in evidence:
        overlap = len(wanted & _descriptor_terms(item.quote_original))
        if overlap:
            scored.append((overlap, item.evidence_id))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [item[1] for item in scored[:2]]


def _load_game(raw: dict[str, Any]) -> FixtureGame:
    try:
        appid = int(raw["appid"])
        name = str(raw["name"]).strip()
        role = str(raw["role"])
        data = raw["data"]
        steam = data["steam"]
        annotation = data["gene_annotation"]
        levels = annotation["genes"]["suggested_levels"]
        raw_evidence = annotation["evidence"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ServiceError(
            "invalid_fixture", "Fixture game structure is invalid."
        ) from exc

    genres = _canonical_genres(list(steam.get("genres") or []))
    categories = [str(item) for item in steam.get("categories") or []]
    passages = [str(steam.get("description") or ""), *steam.get("genres", []), *categories]
    evidence_by_gene: dict[GeneId, list[Evidence]] = {item: [] for item in GeneId}
    seen_evidence: set[str] = set()

    for item in raw_evidence:
        try:
            gene_id = GeneId(item["gene_id"])
            evidence_id = str(item["evidence_id"])
            if evidence_id in seen_evidence:
                raise ValueError("duplicate evidence ID")
            seen_evidence.add(evidence_id)
            evidence = Evidence(
                evidence_id=evidence_id,
                appid=appid,
                gene_id=gene_id,
                source_type=item["source_type"],
                source_priority=SourcePriority(item["source_priority"]),
                trace_status=TraceStatus(item["trace_status"]),
                level_support=LevelSupport(item["level_support"]),
                quote_original=item["quote_original"],
                source_locator=item["source_locator"],
                source_record_id=item["source_record_id"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ServiceError(
                "invalid_fixture", f"Invalid evidence in fixture AppID {appid}."
            ) from exc
        if (
            evidence.trace_status == TraceStatus.VERIFIED
            and evidence.source_priority in {SourcePriority.HIGH, SourcePriority.MEDIUM}
            and quote_is_present(evidence.quote_original, passages)
        ):
            evidence_by_gene[gene_id].append(evidence)

    genes: list[GameGene] = []
    accepted_evidence: list[Evidence] = []
    for gene_id in GeneId:
        suggested = levels.get(gene_id.value)
        evidence = evidence_by_gene[gene_id]
        supported = suggested is not None and bool(evidence)
        accepted_evidence.extend(evidence)
        genes.append(
            GameGene(
                gene_id=gene_id,
                level=suggested if supported else None,
                suggested_level=suggested,
                level_support=(
                    LevelSupport.SUPPORTED if supported else LevelSupport.UNCERTAIN
                ),
                semantic_review_status=SemanticReviewStatus.PENDING,
                evidence=evidence,
            )
        )

    descriptors: list[Descriptor] = []
    for value in annotation.get("descriptors") or []:
        evidence_ids = _descriptor_evidence_ids(str(value), accepted_evidence)
        if not evidence_ids:
            continue
        descriptor_id = re.sub(
            r"[^a-z0-9]+", "_", normalize_evidence_text(str(value))
        ).strip("_")
        if descriptor_id:
            descriptors.append(
                Descriptor(
                    descriptor_id=descriptor_id,
                    value=True,
                    evidence_ids=evidence_ids,
                )
            )

    known_count = sum(item.level is not None for item in genes)
    strong_count = sum(
        item.level is not None
        and any(
            evidence.source_priority in {SourcePriority.HIGH, SourcePriority.MEDIUM}
            for evidence in item.evidence
        )
        for item in genes
    )
    status = (
        CatalogStatus.VERIFIED
        if known_count >= 5 and strong_count >= 3
        else CatalogStatus.PARTIAL
    )
    game = Game(
        appid=appid,
        name=name,
        sampling_bucket=_sampling_bucket(role, genres),
        catalog_status=status,
        genres=genres,
        categories=categories,
        platforms=["windows"],
        languages=["english"],
        social_modes=_social_modes(categories),
        price_usd_cents=steam.get("price_usd_cents"),
        is_free=bool(steam.get("is_free", False)),
        genes=genes,
        descriptors=descriptors,
    )
    return FixtureGame(game=game, store_source=dict(steam))


def load_fixture_catalog(path: Path) -> FixtureCatalog:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        meta = payload["meta"]
        raw_games = payload["games"]
        fixture_name = str(meta["fixture"])
        captured_at = datetime.fromisoformat(str(meta["date"])).replace(
            tzinfo=timezone.utc
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ServiceError("invalid_fixture", "Fixture catalog is not valid JSON.") from exc
    if not isinstance(raw_games, list) or not raw_games:
        raise ServiceError("invalid_fixture", "Fixture catalog contains no games.")
    games = [_load_game(item) for item in raw_games]
    appids = [item.game.appid for item in games]
    if len(appids) != len(set(appids)):
        raise ServiceError("invalid_fixture", "Fixture catalog has duplicate AppIDs.")
    evidence_ids = [
        evidence.evidence_id
        for item in games
        for gene in item.game.genes
        for evidence in gene.evidence
    ]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ServiceError(
            "invalid_fixture", "Fixture catalog has duplicate evidence IDs."
        )
    return FixtureCatalog(
        games=games,
        captured_at=captured_at,
        fixture_name=fixture_name,
    )
