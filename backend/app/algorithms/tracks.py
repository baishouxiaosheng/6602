from app.domain.catalog import Game
from app.domain.enums import Track
from app.domain.profiles import PlayerProfile


def calculate_surface_overlap(game: Game, profile: PlayerProfile) -> float:
    total_weight = sum(item.weight for item in profile.familiar_genres)
    if total_weight <= 0 or not game.genres:
        return 0.0
    game_genres = set(game.genres)
    overlap_weight = sum(
        item.weight for item in profile.familiar_genres if item.genre in game_genres
    )
    return overlap_weight / total_weight


def assign_track(
    game: Game,
    profile: PlayerProfile,
    *,
    threshold: float = 0.50,
) -> Track | None:
    if not game.genres:
        return None
    overlap = calculate_surface_overlap(game, profile)
    return Track.SAME if overlap >= threshold else Track.CROSS
