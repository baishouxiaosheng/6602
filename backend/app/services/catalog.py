import csv
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from app.adapters.llm.base import LLMClient
from app.adapters.steam.client import SteamClient
from app.adapters.steam.schemas import SteamReview, SteamStoreGame
from app.domain.catalog import Game, GameGene
from app.domain.enums import (
    CanonicalGenre,
    CatalogStatus,
    GeneId,
    SourcePriority,
    TraceStatus,
)
from app.domain.llm import (
    OfficialAnnotationRequest,
    ReviewPassage,
    ReviewSupplementRequest,
)
from app.persistence.database import Database
from app.persistence.repositories import GameRepository
from app.services.errors import ConfigurationUnavailable, NotFoundError, ServiceError
from app.services.evidence_text import quote_is_present
from app.services.fixture_catalog import load_fixture_catalog


logger = logging.getLogger(__name__)


def _official_passages(store: SteamStoreGame) -> list[str]:
    passages = [store.short_description, store.detailed_description]
    passages.extend(store.raw_genres)
    passages.extend(store.categories)
    return [item for item in passages if item]


def _valid_official_gene(
    gene: GameGene, *, appid: int, passages: list[str]
) -> bool:
    if gene.level is None:
        return True
    valid = [
        item
        for item in gene.evidence
        if item.appid == appid
        and item.gene_id == gene.gene_id
        and item.source_priority in {SourcePriority.HIGH, SourcePriority.MEDIUM}
        and item.trace_status == TraceStatus.VERIFIED
        and quote_is_present(item.quote_original, passages)
    ]
    return bool(valid)


def _valid_review_gene(
    gene: GameGene,
    *,
    appid: int,
    reviews_by_id: dict[str, SteamReview],
) -> bool:
    if gene.level is None:
        return True
    valid_review_ids: set[str] = set()
    valid_authors: set[str] = set()
    for item in gene.evidence:
        review = reviews_by_id.get(item.review_id or "")
        if (
            item.appid != appid
            or item.gene_id != gene.gene_id
            or item.source_priority != SourcePriority.LOW
            or item.trace_status != TraceStatus.VERIFIED
            or review is None
            or review.author_hash != item.review_author_hash
            or not quote_is_present(item.quote_original, [review.text])
        ):
            continue
        valid_review_ids.add(review.review_id)
        valid_authors.add(review.author_hash)
    return len(valid_review_ids) >= 3 and len(valid_authors) >= 3


def _base_game(store: SteamStoreGame) -> Game:
    return Game(
        appid=store.appid,
        name=store.name,
        catalog_status=CatalogStatus.PENDING,
        genres=store.genres,
        categories=store.categories,
        platforms=store.platforms,
        languages=store.languages,
        social_modes=store.social_modes,
        price_usd_cents=store.price_usd_cents,
        is_free=store.is_free,
    )


class SeedCatalogEntry(BaseModel):
    appid: int
    sampling_bucket: CanonicalGenre
    selection_reason: str = Field(min_length=1, max_length=500)
    added_by: str = Field(min_length=1, max_length=80)
    batch: str = Field(min_length=1, max_length=80)
    replacement_for: int | None = None

    @model_validator(mode="after")
    def validate_replacement_record(self) -> "SeedCatalogEntry":
        if self.batch.casefold().startswith("replacement") and self.replacement_for is None:
            raise ValueError("Replacement batches require replacement_for.")
        if self.replacement_for == self.appid:
            raise ValueError("A seed game cannot replace itself.")
        return self


class CatalogService:
    def __init__(
        self,
        database: Database,
        steam: SteamClient,
        llm: LLMClient | None,
    ) -> None:
        self.database = database
        self.steam = steam
        self.llm = llm

    def get_game(self, appid: int) -> Game:
        with self.database.session_factory() as session:
            game = GameRepository(session).get(appid)
        if game is None:
            raise NotFoundError("Game", str(appid))
        return game

    def list_games(self) -> list[Game]:
        with self.database.session_factory() as session:
            return GameRepository(session).list()

    def stats(self) -> dict[str, int]:
        counts = Counter(game.catalog_status.value for game in self.list_games())
        return {
            "total": sum(counts.values()),
            **{status.value: counts[status.value] for status in CatalogStatus},
        }

    def import_fixture(self, path: Path) -> list[Game]:
        fixture = load_fixture_catalog(path)
        imported: list[Game] = []
        with self.database.session_factory.begin() as session:
            repository = GameRepository(session)
            for item in fixture.games:
                imported.append(
                    repository.upsert(
                        item.game,
                        store_source={
                            "fixture": fixture.fixture_name,
                            "steam": item.store_source,
                        },
                        store_fetched_at=fixture.captured_at,
                        preserve_valid_genes=False,
                    )
                )
        return imported

    @staticmethod
    def load_seed_csv(path: Path) -> list[SeedCatalogEntry]:
        required = {
            "appid",
            "sampling_bucket",
            "selection_reason",
            "added_by",
            "batch",
            "replacement_for",
        }
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ServiceError(
                    "invalid_seed_csv",
                    "Seed CSV does not contain the required columns.",
                )
            try:
                entries = [
                    SeedCatalogEntry(
                        appid=int(row["appid"]),
                        sampling_bucket=CanonicalGenre(row["sampling_bucket"].casefold()),
                        selection_reason=row["selection_reason"].strip(),
                        added_by=row["added_by"].strip(),
                        batch=row["batch"].strip(),
                        replacement_for=(
                            int(row["replacement_for"])
                            if row["replacement_for"].strip()
                            else None
                        ),
                    )
                    for row in reader
                ]
            except (KeyError, TypeError, ValueError) as exc:
                raise ServiceError(
                    "invalid_seed_csv", "Seed CSV contains invalid values."
                ) from exc
        appids = [entry.appid for entry in entries]
        if not entries or any(appid <= 0 for appid in appids):
            raise ServiceError("invalid_seed_csv", "Seed CSV contains invalid AppIDs.")
        if len(appids) != len(set(appids)):
            raise ServiceError("invalid_seed_csv", "Seed CSV contains duplicate AppIDs.")
        return entries

    @staticmethod
    def load_mvp_seed_csv(path: Path) -> list[SeedCatalogEntry]:
        entries = CatalogService.load_seed_csv(path)
        if len(entries) != 30:
            raise ServiceError(
                "invalid_seed_csv", "MVP seed CSV must contain exactly 30 games."
            )
        counts = Counter(entry.sampling_bucket for entry in entries)
        if any(counts[genre] != 5 for genre in CanonicalGenre):
            raise ServiceError(
                "invalid_seed_csv",
                "MVP seed CSV must contain exactly five games in each canonical genre.",
            )
        appids = {entry.appid for entry in entries}
        replacement_targets = [
            entry.replacement_for
            for entry in entries
            if entry.replacement_for is not None
        ]
        if any(target in appids for target in replacement_targets):
            raise ServiceError(
                "invalid_seed_csv",
                "A replaced AppID cannot remain in the active MVP seed catalog.",
            )
        if len(replacement_targets) != len(set(replacement_targets)):
            raise ServiceError(
                "invalid_seed_csv", "MVP seed CSV has duplicate replacement targets."
            )
        return entries

    async def annotate_game(
        self,
        appid: int,
        *,
        sampling_bucket: CanonicalGenre | None = None,
    ) -> Game:
        with self.database.session_factory() as session:
            cached = GameRepository(session).get(appid)
        if (
            cached is not None
            and cached.catalog_status == CatalogStatus.VERIFIED
            and (sampling_bucket is None or cached.sampling_bucket == sampling_bucket)
        ):
            return cached
        if self.llm is None:
            raise ConfigurationUnavailable("Qwen is not configured.")

        try:
            store = await self.steam.get_store_game(appid)
        except Exception:
            if cached is not None:
                return cached
            failed = Game(
                appid=appid,
                name=f"Steam App {appid}",
                catalog_status=CatalogStatus.FAILED,
            )
            with self.database.session_factory.begin() as session:
                return GameRepository(session).upsert(failed)

        game = _base_game(store)
        if sampling_bucket is not None:
            if sampling_bucket not in game.genres:
                raise ServiceError(
                    "invalid_sampling_bucket",
                    (
                        f"Sampling bucket '{sampling_bucket.value}' is not an official "
                        f"canonical genre for AppID {appid}."
                    ),
                )
            game.sampling_bucket = sampling_bucket
        passages = _official_passages(store)
        try:
            official = await self.llm.annotate_official(
                OfficialAnnotationRequest(
                    appid=appid,
                    name=store.name,
                    official_passages=passages,
                    genres=[item.value for item in store.genres],
                    categories=store.categories,
                )
            )
            if len({gene.gene_id for gene in official.genes}) != len(official.genes):
                raise ServiceError(
                    "invalid_annotation", "Official annotation contains duplicate genes."
                )
            official_by_id = {
                gene.gene_id: gene
                for gene in official.genes
                if _valid_official_gene(gene, appid=appid, passages=passages)
            }
            game.genes = [official_by_id[item] for item in GeneId if item in official_by_id]
            accepted_evidence_ids = {
                evidence.evidence_id
                for gene in game.genes
                for evidence in gene.evidence
                if evidence.trace_status == TraceStatus.VERIFIED
            }
            game.descriptors = [
                descriptor
                for descriptor in official.descriptors
                if descriptor.evidence_ids
                and set(descriptor.evidence_ids).issubset(accepted_evidence_ids)
            ]

            known = {gene.gene_id for gene in game.genes if gene.level is not None}
            missing = [gene_id for gene_id in GeneId if gene_id not in known]
            if len(known) < 5 and missing:
                review_page = await self.steam.get_reviews(appid, num_per_page=100)
                reviews_by_id = {item.review_id: item for item in review_page.reviews}
                if len({item.author_hash for item in review_page.reviews}) >= 3:
                    supplement = await self.llm.supplement_reviews(
                        ReviewSupplementRequest(
                            appid=appid,
                            missing_gene_ids=missing,
                            passages=[
                                ReviewPassage(
                                    review_id=item.review_id,
                                    author_hash=item.author_hash,
                                    text=item.text,
                                )
                                for item in review_page.reviews
                            ],
                        )
                    )
                    if len({gene.gene_id for gene in supplement.genes}) != len(
                        supplement.genes
                    ):
                        raise ServiceError(
                            "invalid_annotation",
                            "Review annotation contains duplicate genes.",
                        )
                    for gene in supplement.genes:
                        if (
                            gene.gene_id in missing
                            and _valid_review_gene(
                                gene,
                                appid=appid,
                                reviews_by_id=reviews_by_id,
                            )
                        ):
                            official_by_id[gene.gene_id] = gene
                    game.genes = [
                        official_by_id[item] for item in GeneId if item in official_by_id
                    ]

            known_count = sum(gene.level is not None for gene in game.genes)
            game.catalog_status = (
                CatalogStatus.VERIFIED if known_count >= 5 else CatalogStatus.PARTIAL
            )
        except Exception:
            logger.exception("Catalog annotation failed for AppID %s.", appid)
            game.catalog_status = CatalogStatus.FAILED

        with self.database.session_factory.begin() as session:
            return GameRepository(session).upsert(
                game,
                store_source=store.raw_payload,
                store_fetched_at=datetime.now(timezone.utc),
            )

    async def annotate_games(self, appids: list[int], progress=None) -> list[Game]:
        results: list[Game] = []
        for index, appid in enumerate(appids, start=1):
            results.append(await self.annotate_game(appid))
            if progress is not None:
                progress("annotating_catalog", index, len(appids))
        return results

    async def annotate_seed_entries(
        self, entries: list[SeedCatalogEntry], progress=None
    ) -> list[Game]:
        results: list[Game] = []
        total = len(entries)
        for index, entry in enumerate(entries, start=1):
            results.append(
                await self.annotate_game(
                    entry.appid,
                    sampling_bucket=entry.sampling_bucket,
                )
            )
            if progress is not None:
                progress("annotating_seed_catalog", index, total)
        return results
