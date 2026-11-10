"""[FW] Read side of the catalog (contracts.CatalogReader)."""

from __future__ import annotations

import json

from ..config import RESOURCES, Settings
from ..contracts.errors import ConfigError, NotFound
from ..contracts.models import CatalogStats, GameRecord
from ..storage import JsonStore, Kind


class FixtureCatalog:
    """Bundled SYNTHETIC sample catalog (resources/fixture_catalog.json).

    Gene levels, evidence quotes and prices in it are hand-written placeholders so
    Dev B and the UI can work before the real pipeline exists. It is never real
    evidence and must not be shown in the final demo.
    """

    source = "fixture"

    def __init__(self) -> None:
        raw = json.loads((RESOURCES / "fixture_catalog.json").read_text(encoding="utf-8"))
        self._games = {g["appid"]: GameRecord.model_validate(g) for g in raw["games"]}

    def list_games(self) -> list[GameRecord]:
        return list(self._games.values())

    def get_game(self, appid: int) -> GameRecord:
        try:
            return self._games[appid]
        except KeyError as err:
            raise NotFound(f"appid {appid} is not in the catalog", appid=appid) from err


class StoreCatalog:
    """Real catalog written by Workflow 2 into the JSON store."""

    source = "store"

    def __init__(self, store: JsonStore) -> None:
        self._store = store

    def list_games(self) -> list[GameRecord]:
        return [self._store.get(Kind.GAME, i) for i in self._store.list_ids(Kind.GAME)]  # type: ignore[misc]

    def get_game(self, appid: int) -> GameRecord:
        return self._store.get(Kind.GAME, str(appid))  # type: ignore[return-value]


def make_catalog(settings: Settings, store: JsonStore):
    if settings.catalog_source == "fixture":
        return FixtureCatalog()
    if settings.catalog_source == "store":
        return StoreCatalog(store)
    raise ConfigError(
        f"GAMEGENE_CATALOG must be 'fixture' or 'store', got {settings.catalog_source!r}"
    )


def stats_of(catalog) -> CatalogStats:
    games = catalog.list_games()
    by_status: dict[str, int] = {}
    for g in games:
        by_status[g.status.value] = by_status.get(g.status.value, 0) + 1
    return CatalogStats(total=len(games), by_status=by_status, source=catalog.source)
