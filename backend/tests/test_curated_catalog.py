from collections import Counter
from pathlib import Path

from app.domain.enums import CanonicalGenre, CatalogStatus
from app.persistence.database import create_database
from app.persistence.repositories import GameRepository
from app.services.curated_catalog import load_curated_catalog
from app.services.evidence_text import quote_is_present


DATA = Path(__file__).parents[1] / "data"


def _catalog():
    return load_curated_catalog(
        DATA / "seed_store_snapshots.json",
        DATA / "curated_gene_levels.json",
    )


def test_curated_catalog_is_balanced_and_evidence_grounded() -> None:
    catalog = _catalog()

    assert len(catalog.games) == 30
    assert len({game.appid for game in catalog.games}) == 30
    assert Counter(game.sampling_bucket for game in catalog.games) == {
        genre: 5 for genre in CanonicalGenre
    }
    assert Counter(game.catalog_status for game in catalog.games) == {
        CatalogStatus.VERIFIED: 29,
        CatalogStatus.PARTIAL: 1,
    }
    partial = next(
        game for game in catalog.games if game.catalog_status == CatalogStatus.PARTIAL
    )
    assert partial.appid == 501300

    for game in catalog.games:
        snapshot = catalog.store_sources[game.appid]
        description_sources = [
            snapshot.get("short_description") or "",
            snapshot.get("detailed_description") or "",
        ]
        category_sources = snapshot.get("categories") or []
        accepted_ids = set()
        for gene in game.genes:
            for evidence in gene.evidence:
                sources = (
                    category_sources
                    if evidence.source_locator == "appdetails.categories"
                    else description_sources
                )
                assert quote_is_present(evidence.quote_original, sources)
                accepted_ids.add(evidence.evidence_id)
        assert all(
            set(descriptor.evidence_ids).issubset(accepted_ids)
            for descriptor in game.descriptors
        )


def test_curated_catalog_import_is_idempotent(tmp_path: Path) -> None:
    catalog = _catalog()
    database = create_database(f"sqlite:///{tmp_path / 'curated.db'}")
    database.create_schema()

    for _ in range(2):
        with database.session_factory.begin() as session:
            repository = GameRepository(session)
            for game in catalog.games:
                repository.upsert(
                    game,
                    store_source=catalog.store_sources[game.appid],
                    store_fetched_at=catalog.captured_at,
                    preserve_valid_genes=False,
                )

    with database.session_factory() as session:
        persisted = GameRepository(session).list()
    assert len(persisted) == 30
    assert Counter(game.catalog_status for game in persisted) == {
        CatalogStatus.VERIFIED: 29,
        CatalogStatus.PARTIAL: 1,
    }
    database.engine.dispose()
