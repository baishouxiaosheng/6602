import hashlib
import json
from typing import Any

from app.adapters.http import InvalidUpstreamPayload, JsonHttpClient
from app.adapters.steam.identity import parse_steam_identity
from app.adapters.steam.normalization import normalize_store_game, sanitize_untrusted_text
from app.adapters.steam.schemas import (
    SteamLibrary,
    SteamOwnedGame,
    SteamReview,
    SteamReviewPage,
    SteamStoreGame,
)


class SteamLibraryUnavailable(InvalidUpstreamPayload):
    pass


class SteamAppUnavailable(InvalidUpstreamPayload):
    pass


class SteamIdentityUnavailable(InvalidUpstreamPayload):
    pass


class SteamClient:
    OWNED_GAMES_URL = (
        "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
    )
    APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"
    REVIEWS_URL = (
        "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/"
    )
    RESOLVE_VANITY_URL = (
        "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/"
    )

    def __init__(
        self,
        *,
        http: JsonHttpClient,
        web_api_key: str | None,
        review_author_hash_salt: str,
    ) -> None:
        self.http = http
        self.web_api_key = web_api_key
        self.review_author_hash_salt = review_author_hash_salt

    async def resolve_steam_id(self, raw_identity: str) -> str:
        identity = parse_steam_identity(raw_identity)
        if identity.kind == "steam_id":
            return identity.value
        if not self.web_api_key:
            raise SteamIdentityUnavailable(
                service="steam",
                message="Steam Web API key is required to resolve a custom profile URL.",
            )

        payload = await self.http.request_json(
            "GET",
            self.RESOLVE_VANITY_URL,
            params={
                "key": self.web_api_key,
                "vanityurl": identity.value,
                "url_type": 1,
            },
        )
        response = payload.get("response")
        if not isinstance(response, dict) or response.get("success") != 1:
            raise SteamIdentityUnavailable(
                service="steam",
                message="Steam custom profile URL could not be resolved.",
            )
        steam_id = response.get("steamid")
        if not isinstance(steam_id, str):
            raise SteamIdentityUnavailable(
                service="steam",
                message="Steam returned an invalid SteamID64.",
            )
        try:
            return parse_steam_identity(steam_id).value
        except ValueError as exc:
            raise SteamIdentityUnavailable(
                service="steam",
                message="Steam returned an invalid SteamID64.",
            ) from exc

    async def get_owned_games(self, steam_id: str) -> SteamLibrary:
        if not self.web_api_key:
            raise SteamLibraryUnavailable(
                service="steam",
                message="Steam Web API key is not configured.",
            )
        input_data = {
            "steamid": steam_id,
            "include_appinfo": True,
            "include_played_free_games": True,
        }
        payload = await self.http.request_json(
            "GET",
            self.OWNED_GAMES_URL,
            params={
                "key": self.web_api_key,
                "input_json": json.dumps(input_data, separators=(",", ":")),
            },
        )
        response = payload.get("response")
        if not isinstance(response, dict):
            raise SteamLibraryUnavailable(
                service="steam",
                message="Steam library response is unavailable.",
            )
        raw_games = response.get("games")
        game_count = response.get("game_count")
        if raw_games is None and game_count not in (0, "0"):
            raise SteamLibraryUnavailable(
                service="steam",
                message="Steam library is private or unavailable.",
            )

        games: list[SteamOwnedGame] = []
        for item in raw_games or []:
            if not isinstance(item, dict) or not isinstance(item.get("appid"), int):
                continue
            games.append(
                SteamOwnedGame(
                    appid=item["appid"],
                    name=item.get("name"),
                    playtime_minutes=max(0, int(item.get("playtime_forever") or 0)),
                    playtime_last_two_weeks_minutes=(
                        max(0, int(item["playtime_2weeks"]))
                        if item.get("playtime_2weeks") is not None
                        else None
                    ),
                )
            )
        return SteamLibrary(steam_id=steam_id, games=games)

    async def get_store_game(self, appid: int) -> SteamStoreGame:
        payload = await self.http.request_json(
            "GET",
            self.APPDETAILS_URL,
            params={"appids": appid, "cc": "us", "l": "english"},
        )
        item = payload.get(str(appid))
        if not isinstance(item, dict) or item.get("success") is not True:
            raise SteamAppUnavailable(
                service="steam",
                message=f"Steam app {appid} is unavailable.",
            )
        data = item.get("data")
        if not isinstance(data, dict):
            raise SteamAppUnavailable(
                service="steam",
                message=f"Steam app {appid} has no store data.",
            )
        return normalize_store_game(appid, data)

    async def get_reviews(
        self,
        appid: int,
        *,
        cursor: str | None = None,
        num_per_page: int = 20,
    ) -> SteamReviewPage:
        input_data: dict[str, Any] = {
            "appid": appid,
            "languages": ["english"],
            "filter": 0,
            "review_type": 0,
            "purchase_type": 1,
            "num_per_page": max(1, min(100, num_per_page)),
            "filter_offtopic_activity": True,
            "use_review_quality": True,
        }
        if cursor:
            input_data["cursor"] = cursor
        payload = await self.http.request_json(
            "GET",
            self.REVIEWS_URL,
            params={"input_json": json.dumps(input_data, separators=(",", ":"))},
        )

        reviews: list[SteamReview] = []
        for item in payload.get("reviews") or []:
            if not isinstance(item, dict):
                continue
            author = item.get("author") or {}
            author_steam_id = str(author.get("steamid") or "")
            review_id = str(item.get("recommendationid") or "")
            text = sanitize_untrusted_text(
                str(item.get("review") or ""), max_chars=4_000
            )
            if not author_steam_id or not review_id or not text:
                continue
            author_hash = hashlib.sha256(
                f"{self.review_author_hash_salt}:{author_steam_id}".encode("utf-8")
            ).hexdigest()
            reviews.append(
                SteamReview(
                    review_id=review_id,
                    author_hash=author_hash,
                    language=str(item.get("language") or "english"),
                    text=text,
                    voted_up=bool(item.get("voted_up", False)),
                    playtime_forever_minutes=max(
                        0, int(author.get("playtime_forever") or 0)
                    ),
                    playtime_at_review_minutes=(
                        max(0, int(author["playtime_at_review"]))
                        if author.get("playtime_at_review") is not None
                        else None
                    ),
                    weighted_vote_score=max(
                        0.0, float(item.get("weighted_vote_score") or 0.0)
                    ),
                )
            )

        summary = payload.get("query_summary") or {}
        total_matching = payload.get("total_matching")
        if total_matching is None and isinstance(summary, dict):
            total_matching = summary.get("total_reviews")
        return SteamReviewPage(
            appid=appid,
            reviews=reviews,
            cursor=str(payload.get("cursor")) if payload.get("cursor") else None,
            total_matching=(
                int(total_matching) if total_matching is not None else None
            ),
        )
