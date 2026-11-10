"""[A] contracts.SteamLibraryClient (task A4). Needs STEAM_API_KEY."""

from __future__ import annotations

from ..contracts.models import OwnedGame
from .http import ThrottledHttp

RESOLVE_URL = "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/"
OWNED_URL = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"


class HttpSteamLibraryClient:
    def __init__(self, http: ThrottledHttp, api_key: str) -> None:
        self.http, self.api_key = http, api_key

    def resolve_steam_id(self, steam_id_or_url: str) -> str:
        """Accept: 17-digit id | .../profiles/<id>[/] | .../id/<vanity>[/] | bare vanity.
        Vanity -> ResolveVanityURL (success==1 -> steamid; 42 -> NotFound).
        Anything else (empty, spaces, other URL) -> InvalidInput WITHOUT a network call.
        Empty api_key -> ConfigError."""
        raise NotImplementedError("Dev A: task A4")

    def get_owned_games(self, steam_id: str) -> list[OwnedGame]:
        """GetOwnedGames?include_appinfo=1&include_played_free_games=1.
        ``response == {}`` (no 'games' key and no 'game_count') -> SteamProfilePrivate.
        playtime_forever is already minutes."""
        raise NotImplementedError("Dev A: task A4")


class FakeSteamLibraryClient:
    """[FW] Offline stand-in for tests and for Dev B. Not a stub: it works."""

    def __init__(
        self,
        libraries: dict[str, list[OwnedGame]] | None = None,
        private: set[str] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.libraries = libraries or {}
        self.private = private or set()
        self.error = error
        self.calls = 0

    def resolve_steam_id(self, steam_id_or_url: str) -> str:
        from ..contracts.errors import InvalidInput

        text = steam_id_or_url.strip().rstrip("/").split("/")[-1]
        if not (text.isdigit() and len(text) == 17):
            raise InvalidInput("fake client only accepts 17-digit steam ids", value=steam_id_or_url)
        return text

    def get_owned_games(self, steam_id: str) -> list[OwnedGame]:
        from ..contracts.errors import NotFound, SteamProfilePrivate

        self.calls += 1
        if self.error is not None:
            raise self.error
        if steam_id in self.private:
            raise SteamProfilePrivate("this Steam profile or its game details are private")
        if steam_id not in self.libraries:
            raise NotFound(f"steam id {steam_id} not found")
        return self.libraries[steam_id]
