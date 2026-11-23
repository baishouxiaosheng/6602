import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import unquote, urlparse


_VANITY_RE = re.compile(r"^[A-Za-z0-9_-]{2,64}$")


class InvalidSteamIdentity(ValueError):
    pass


@dataclass(frozen=True)
class SteamIdentity:
    kind: Literal["steam_id", "vanity"]
    value: str


def _validated_steam_id(value: str) -> str:
    if not value.isascii() or not value.isdecimal():
        raise InvalidSteamIdentity("SteamID64 must contain only ASCII digits.")
    number = int(value)
    if number <= 0 or number > (2**64 - 1):
        raise InvalidSteamIdentity("SteamID64 is outside the uint64 range.")
    return value


def parse_steam_identity(raw_value: str) -> SteamIdentity:
    """Parse a SteamID64 or an official Steam Community profile URL."""
    value = raw_value.strip()
    if not value:
        raise InvalidSteamIdentity("Steam identity is required.")

    if value.isascii() and value.isdecimal():
        return SteamIdentity(kind="steam_id", value=_validated_steam_id(value))

    parsed = urlparse(value)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise InvalidSteamIdentity("Steam profile URL must use HTTP or HTTPS.")
    if (parsed.hostname or "").lower() not in {
        "steamcommunity.com",
        "www.steamcommunity.com",
    }:
        raise InvalidSteamIdentity("Only steamcommunity.com profile URLs are accepted.")

    parts = [unquote(part) for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise InvalidSteamIdentity("Steam profile URL has an unsupported path.")

    profile_kind, identifier = parts
    if profile_kind.lower() == "profiles":
        return SteamIdentity(
            kind="steam_id", value=_validated_steam_id(identifier)
        )
    if profile_kind.lower() == "id" and _VANITY_RE.fullmatch(identifier):
        return SteamIdentity(kind="vanity", value=identifier)
    raise InvalidSteamIdentity("Steam profile URL has an invalid identifier.")
