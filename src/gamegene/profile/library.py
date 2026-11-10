"""[B] Blend a Steam library into an interview profile (task B1). Pure function."""

from __future__ import annotations

from ..contracts.genes import GeneId
from ..contracts.models import GameRecord, GenePreference, OwnedGame

MIN_PLAYTIME_MINUTES = 60
MAX_BLEND = 0.5
BLEND_PER_GAME = 0.1


def blend_library(
    prefs: dict[GeneId, GenePreference],
    familiar_tags: dict[str, float],
    owned: list[OwnedGame],
    catalog_games: dict[int, GameRecord],
) -> tuple[dict[GeneId, GenePreference], dict[str, float], list[int]]:
    """Return (new prefs, new familiar tags, matched appids).

    matched = owned games that are in the catalog with status VERIFIED and
              playtime >= 60 minutes;  w_game = ln(1 + hours played)
    per gene: lib = weighted mean of the matched games' KNOWN levels (skip unknown);
              beta = min(0.5, 0.1 * number of matched games that know this gene);
              target' = (1 - beta) * target + beta * lib;  recompute weight with the
              interview formula (min(1, 0.4 + 0.3*|target' - 2|)); round both to 2 dp.
    tags:     tag_w = sum of w_game over matched games carrying the tag (genres + tags),
              divided by the largest tag_w -> 0..1; merged with the interview tags by max().
    No matched games -> inputs returned unchanged with [].
    """
    raise NotImplementedError("Dev B: task B1")
