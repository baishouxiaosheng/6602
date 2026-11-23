from dataclasses import dataclass
from enum import StrEnum

from app.domain.catalog import Game
from app.domain.enums import CatalogStatus, SocialRequirement
from app.domain.profiles import PlayerProfile


class DropReason(StrEnum):
    NOT_VERIFIED = "not_verified"
    OWNED_OR_EXCLUDED = "owned_or_excluded"
    PLATFORM_UNKNOWN = "platform_unknown"
    PLATFORM = "platform"
    CONTROLLER_UNKNOWN = "controller_unknown"
    CONTROLLER = "controller"
    SOCIAL_MODE_UNKNOWN = "social_mode_unknown"
    SOCIAL_MODE = "social_mode"
    LANGUAGE_UNKNOWN = "language_unknown"
    LANGUAGE = "language"
    PRICE_UNVERIFIABLE = "price_unverifiable"
    PRICE = "price"
    INSUFFICIENT_GENES = "insufficient_genes"
    MISSING_SURFACE_LABELS = "missing_surface_labels"


@dataclass(frozen=True)
class FilterDecision:
    passed: bool
    reason: DropReason | None = None


def _normalized(values: list[str]) -> set[str]:
    return {value.strip().casefold().replace("-", "_").replace(" ", "_") for value in values}


def apply_hard_filters(game: Game, profile: PlayerProfile) -> FilterDecision:
    if game.catalog_status != CatalogStatus.VERIFIED:
        return FilterDecision(False, DropReason.NOT_VERIFIED)

    if game.appid in profile.owned_appids:
        return FilterDecision(False, DropReason.OWNED_OR_EXCLUDED)

    filters = profile.hard_filters
    game_platforms = _normalized(game.platforms)
    requested_platforms = _normalized(filters.platforms)
    if requested_platforms:
        if not game_platforms:
            return FilterDecision(False, DropReason.PLATFORM_UNKNOWN)
        if game_platforms.isdisjoint(requested_platforms):
            return FilterDecision(False, DropReason.PLATFORM)

    if filters.controller_required:
        categories = _normalized(game.categories)
        controller_markers = {
            "controller_support",
            "full_controller_support",
            "partial_controller_support",
        }
        if not categories:
            return FilterDecision(False, DropReason.CONTROLLER_UNKNOWN)
        if categories.isdisjoint(controller_markers):
            return FilterDecision(False, DropReason.CONTROLLER)

    social_modes = _normalized(game.social_modes)
    if filters.social_requirement != SocialRequirement.ANY:
        if not social_modes:
            return FilterDecision(False, DropReason.SOCIAL_MODE_UNKNOWN)
        if filters.social_requirement == SocialRequirement.NO_MANDATORY_MULTIPLAYER:
            if "single_player" not in social_modes:
                return FilterDecision(False, DropReason.SOCIAL_MODE)
        elif filters.social_requirement == SocialRequirement.MULTIPLAYER_REQUIRED:
            multiplayer_markers = {
                "multiplayer",
                "co_op",
                "online_co_op",
                "pvp",
                "online_pvp",
            }
            if social_modes.isdisjoint(multiplayer_markers):
                return FilterDecision(False, DropReason.SOCIAL_MODE)

    if filters.required_language:
        languages = _normalized(game.languages)
        required_language = filters.required_language.casefold().replace(" ", "_")
        if not languages:
            return FilterDecision(False, DropReason.LANGUAGE_UNKNOWN)
        if required_language not in languages:
            return FilterDecision(False, DropReason.LANGUAGE)

    if filters.max_price_usd_cents is not None:
        if game.price_usd_cents is None:
            return FilterDecision(False, DropReason.PRICE_UNVERIFIABLE)
        if game.price_usd_cents > filters.max_price_usd_cents:
            return FilterDecision(False, DropReason.PRICE)

    known_genes = sum(gene.level is not None for gene in game.genes)
    if known_genes < 5:
        return FilterDecision(False, DropReason.INSUFFICIENT_GENES)

    if not game.genres:
        return FilterDecision(False, DropReason.MISSING_SURFACE_LABELS)

    return FilterDecision(True)
