from app.algorithms.profile_fusion import fuse_profile
from app.domain.catalog import Game, GameGene
from app.domain.enums import (
    CanonicalGenre,
    CatalogStatus,
    GeneId,
    LevelSupport,
    SourcePriority,
    TraceStatus,
)
from app.domain.evidence import Evidence
from app.domain.profiles import FamiliarGenre, HardFilters, PlayerProfile, QuestionnaireSubmission


def make_evidence(
    appid: int,
    gene_id: GeneId,
    *,
    priority: SourcePriority = SourcePriority.HIGH,
) -> Evidence:
    suffix = f"{appid}_{gene_id.value}"
    return Evidence(
        evidence_id=f"ev_{suffix}",
        appid=appid,
        gene_id=gene_id,
        source_type="official_description",
        source_priority=priority,
        trace_status=TraceStatus.VERIFIED,
        level_support=LevelSupport.SUPPORTED,
        quote_original=f"Verified evidence for {gene_id.value}.",
        source_locator="appdetails.about_the_game",
        source_record_id=f"store_{appid}",
        review_id=f"review_{suffix}" if priority == SourcePriority.LOW else None,
        review_author_hash=(
            f"author_{suffix}" if priority == SourcePriority.LOW else None
        ),
    )


def make_game(
    appid: int,
    *,
    levels: dict[GeneId, int] | None = None,
    genre: CanonicalGenre = CanonicalGenre.RPG,
    status: CatalogStatus = CatalogStatus.VERIFIED,
    price: int | None = 1_000,
) -> Game:
    levels = levels or {gene_id: 2 for gene_id in GeneId}
    return Game(
        appid=appid,
        name=f"Game {appid}",
        sampling_bucket=genre,
        catalog_status=status,
        genres=[genre],
        categories=["Single-player", "Full Controller Support"],
        platforms=["windows"],
        languages=["english"],
        social_modes=["single_player"],
        price_usd_cents=price,
        genes=[
            GameGene(
                gene_id=gene_id,
                level=level,
                level_support=LevelSupport.SUPPORTED,
                evidence=[make_evidence(appid, gene_id)],
            )
            for gene_id, level in levels.items()
        ],
    )


def make_submission(
    *,
    target: int = 2,
    important: list[GeneId] | None = None,
    familiar_genres: list[FamiliarGenre] | None = None,
    hard_filters: HardFilters | None = None,
) -> QuestionnaireSubmission:
    return QuestionnaireSubmission(
        display_name="Alice",
        gene_targets={gene_id: target for gene_id in GeneId},
        important_genes=important or [],
        familiar_genres=familiar_genres
        or [FamiliarGenre(genre=CanonicalGenre.RPG, rank=1, weight=3)],
        hard_filters=hard_filters or HardFilters(platforms=["windows"]),
    )


def make_profile(**kwargs) -> PlayerProfile:
    submission = make_submission(**kwargs)
    return fuse_profile(profile_id="p_test", submission=submission)
