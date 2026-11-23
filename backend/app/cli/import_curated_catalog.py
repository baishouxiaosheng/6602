from collections import Counter
from pathlib import Path

from app.config import get_settings
from app.persistence.migrations import initialize_database
from app.persistence.repositories import GameRepository
from app.services.curated_catalog import load_curated_catalog


DATA = Path(__file__).resolve().parents[2] / "data"


def main() -> None:
    catalog = load_curated_catalog(
        DATA / "seed_store_snapshots.json",
        DATA / "curated_gene_levels.json",
    )
    database = initialize_database(get_settings().database_url)
    try:
        imported = []
        with database.session_factory.begin() as session:
            repository = GameRepository(session)
            for game in catalog.games:
                imported.append(
                    repository.upsert(
                        game,
                        store_source=catalog.store_sources[game.appid],
                        store_fetched_at=catalog.captured_at,
                        preserve_valid_genes=False,
                    )
                )
    finally:
        database.engine.dispose()
    counts = Counter(game.catalog_status.value for game in imported)
    print(
        f"Imported {len(imported)} curated games: "
        + ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
        + "."
    )


if __name__ == "__main__":
    main()
