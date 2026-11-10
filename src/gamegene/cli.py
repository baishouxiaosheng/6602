"""Command line entry point.

gamegene serve [--host 127.0.0.1] [--port 7860]
gamegene catalog build --appids data/seed/appids.csv [--limit N] [--force]
gamegene catalog stats
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from .config import load_settings
from .contracts.errors import GameGeneError


def _read_appids(path: Path, limit: int | None) -> list[int]:
    with path.open(encoding="utf-8", newline="") as fh:
        ids = [int(row["appid"]) for row in csv.DictReader(fh) if row.get("appid", "").strip()]
    seen: set[int] = set()
    unique = [i for i in ids if not (i in seen or seen.add(i))]
    return unique[:limit] if limit else unique


def _serve(args) -> int:
    import uvicorn

    from .app.api import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port)
    return 0


def _catalog_build(args) -> int:
    from .catalog.pipeline import run_batch
    from .llm import make_llm
    from .steam.http import ThrottledHttp
    from .steam.store import HttpSteamStoreClient
    from .storage import JsonStore

    s = load_settings()
    steam = HttpSteamStoreClient(
        ThrottledHttp(min_interval_s=s.steam_min_interval_s),
        s.raw_dir,
        cc=s.steam_cc,
        lang=s.steam_lang,
    )
    report = run_batch(
        _read_appids(Path(args.appids), args.limit),
        steam=steam,
        llm=make_llm(s),
        store=JsonStore(s.data_dir),
        force=args.force,
        report_dir=s.data_dir / "reports",
    )
    print(report.counts())
    return 0


def _catalog_stats(_args) -> int:
    from .catalog.reader import make_catalog, stats_of
    from .storage import JsonStore

    s = load_settings()
    print(stats_of(make_catalog(s, JsonStore(s.data_dir))).model_dump_json(indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gamegene")
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve", help="start the web UI and HTTP API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=7860)
    serve.set_defaults(fn=_serve)
    cat = sub.add_parser("catalog", help="catalog pipeline (Workflow 2)").add_subparsers(
        dest="sub", required=True
    )
    build = cat.add_parser("build")
    build.add_argument("--appids", required=True)
    build.add_argument("--limit", type=int)
    build.add_argument("--force", action="store_true")
    build.set_defaults(fn=_catalog_build)
    cat.add_parser("stats").set_defaults(fn=_catalog_stats)
    args = parser.parse_args(argv)
    try:
        return args.fn(args)
    except GameGeneError as err:
        print(err.to_response().model_dump_json(indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
