"""[B] Hard filters (task B3). Pure, deterministic, runs BEFORE scoring and the model."""

from __future__ import annotations

from ..contracts.models import GameRecord, UserProfile

# Drop reasons, checked in THIS order; a game is counted under the first that applies.
DROP_REASONS = (
    "not_verified",  # status != VERIFIED
    "excluded",  # appid in profile.exclusion_set()  (owned or explicitly excluded)
    "excluded_tag",  # any excluded tag in genres or tags (case-insensitive)
    "platform",  # filters.platforms non-empty and no common platform
    "social_mode",  # filters.social_modes non-empty and no common mode
    "language",  # required_language set and not in store.languages
    "price",  # max_price_cents set, game not free, price known and final_cents > max
    "insufficient_genes",  # scoring.gene_score(...) is None
)


def apply_hard_filters(
    profile: UserProfile, games: list[GameRecord]
) -> tuple[list[GameRecord], dict[str, int]]:
    """Return (surviving games in input order, {reason: count} for reasons with count > 0).
    Unknown price passes the price filter; a free game always passes it."""
    raise NotImplementedError("Dev B: task B3")
