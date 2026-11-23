import html
import re
import unicodedata
from html.parser import HTMLParser
from typing import Any

from app.adapters.steam.schemas import SteamStoreGame
from app.domain.enums import CanonicalGenre


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self._ignored_depth += 1
        elif tag in {"br", "p", "div", "li", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._ignored_depth:
            self._ignored_depth -= 1
        elif tag in {"p", "div", "li", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


_URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_CODE_BLOCK_PATTERN = re.compile(r"```.*?```", re.DOTALL)
_WHITESPACE_PATTERN = re.compile(r"[ \t]+")
_GENRE_MAP = {
    "action": CanonicalGenre.ACTION,
    "adventure": CanonicalGenre.ADVENTURE,
    "rpg": CanonicalGenre.RPG,
    "role-playing": CanonicalGenre.RPG,
    "role playing": CanonicalGenre.RPG,
    "strategy": CanonicalGenre.STRATEGY,
    "simulation": CanonicalGenre.SIMULATION,
    "casual": CanonicalGenre.CASUAL,
}


def sanitize_untrusted_text(text: str, *, max_chars: int) -> str:
    extractor = _TextExtractor()
    extractor.feed(html.unescape(text or ""))
    value = "".join(extractor.parts)
    value = _CODE_BLOCK_PATTERN.sub(" ", value)
    value = _URL_PATTERN.sub("[link removed]", value)
    value = "".join(
        character
        for character in value
        if character in "\n\t" or not unicodedata.category(character).startswith("C")
    )

    lines: list[str] = []
    seen: set[str] = set()
    for raw_line in value.splitlines():
        line = _WHITESPACE_PATTERN.sub(" ", raw_line).strip()
        if not line:
            continue
        normalized = line.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        lines.append(line)
    return "\n".join(lines)[:max_chars]


def normalize_genres(raw_genres: list[dict[str, Any]]) -> tuple[list[CanonicalGenre], list[str]]:
    canonical: list[CanonicalGenre] = []
    raw_names: list[str] = []
    for item in raw_genres:
        name = str(item.get("description", "")).strip()
        if not name:
            continue
        raw_names.append(name)
        mapped = _GENRE_MAP.get(name.casefold())
        if mapped and mapped not in canonical:
            canonical.append(mapped)
    return canonical, raw_names


def normalize_categories(raw_categories: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    categories: list[str] = []
    social_modes: list[str] = []
    social_map = {
        "single-player": "single_player",
        "multi-player": "multiplayer",
        "multiplayer": "multiplayer",
        "co-op": "co_op",
        "online co-op": "online_co_op",
        "pvp": "pvp",
        "online pvp": "online_pvp",
    }
    for item in raw_categories:
        description = str(item.get("description", "")).strip()
        if not description:
            continue
        categories.append(description)
        social_mode = social_map.get(description.casefold())
        if social_mode and social_mode not in social_modes:
            social_modes.append(social_mode)
    return categories, social_modes


def normalize_languages(value: str) -> list[str]:
    extractor = _TextExtractor()
    extractor.feed(value or "")
    plain = "".join(extractor.parts)
    languages: list[str] = []
    for item in plain.split(","):
        normalized = re.sub(r"\*.*$", "", item).strip().casefold()
        if normalized and normalized not in languages:
            languages.append(normalized)
    return languages


def normalize_store_game(appid: int, data: dict[str, Any]) -> SteamStoreGame:
    genres, raw_genres = normalize_genres(data.get("genres") or [])
    categories, social_modes = normalize_categories(data.get("categories") or [])
    platforms_data = data.get("platforms") or {}
    platforms = [
        name.casefold() for name, supported in platforms_data.items() if supported
    ]

    is_free = bool(data.get("is_free", False))
    price_overview = data.get("price_overview") or {}
    price = 0 if is_free else price_overview.get("final")
    if not isinstance(price, int) or price < 0:
        price = None

    release = data.get("release_date") or {}
    if release.get("coming_soon") is True:
        release_state = "coming_soon"
    elif release.get("date"):
        release_state = "released"
    else:
        release_state = "unknown"

    return SteamStoreGame(
        appid=appid,
        name=str(data.get("name") or f"Steam App {appid}"),
        app_type=str(data.get("type") or "unknown"),
        short_description=sanitize_untrusted_text(
            str(data.get("short_description") or ""), max_chars=2_000
        ),
        detailed_description=sanitize_untrusted_text(
            str(data.get("detailed_description") or ""), max_chars=12_000
        ),
        genres=genres,
        raw_genres=raw_genres,
        categories=categories,
        platforms=platforms,
        languages=normalize_languages(str(data.get("supported_languages") or "")),
        social_modes=social_modes,
        price_usd_cents=price,
        is_free=is_free,
        release_state=release_state,
        raw_payload=data,
    )
