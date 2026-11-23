import argparse
import asyncio
from collections import Counter
from pathlib import Path

from app.api.dependencies import build_services
from app.config import get_settings
from app.services.catalog import CatalogService


DEFAULT_SEED_CSV = Path(__file__).resolve().parents[2] / "data" / "seed_games.csv"


def _summary(entries) -> str:
    counts = Counter(item.sampling_bucket.value for item in entries)
    distribution = ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    replacements = sum(item.replacement_for is not None for item in entries)
    return f"Validated {len(entries)} seed games ({distribution}; replacements={replacements})."


async def _import(path: Path) -> None:
    entries = CatalogService.load_mvp_seed_csv(path)
    print(_summary(entries))
    services = build_services(get_settings())
    try:
        def progress(step: str, processed: int, total: int) -> None:
            print(f"Progress {processed}/{total}: {step}", flush=True)

        games = await services.catalog.annotate_seed_entries(
            entries,
            progress=progress,
        )
    finally:
        if services.http_client is not None:
            await services.http_client.aclose()
        services.database.engine.dispose()
    counts = Counter(item.catalog_status.value for item in games)
    print(
        "Catalog import completed: "
        + ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
        + "."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate or annotate the 30-game Batch 6B seed catalog."
    )
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT_SEED_CSV)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the CSV without calling Steam or Qwen.",
    )
    args = parser.parse_args()
    if args.validate_only:
        entries = CatalogService.load_mvp_seed_csv(args.path)
        print(_summary(entries))
        return
    asyncio.run(_import(args.path))


if __name__ == "__main__":
    main()
