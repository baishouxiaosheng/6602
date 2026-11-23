import argparse
from pathlib import Path

from app.adapters.steam.client import SteamClient
from app.config import get_settings
from app.persistence.migrations import initialize_database
from app.services.catalog import CatalogService


DEFAULT_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "fixtures"
    / "test_games_fixture.json"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import the offline five-game Batch 6A catalog fixture."
    )
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_FIXTURE)
    args = parser.parse_args()

    database = initialize_database(get_settings().database_url)
    # Fixture import is offline; this placeholder is never called.
    service = CatalogService(database, SteamClient.__new__(SteamClient), None)
    try:
        games = service.import_fixture(args.path)
    finally:
        database.engine.dispose()

    verified = sum(item.catalog_status.value == "verified" for item in games)
    print(f"Imported {len(games)} fixture games ({verified} verified).")


if __name__ == "__main__":
    main()
