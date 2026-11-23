import json
from pathlib import Path

import httpx
import pytest

from app.adapters.http import JsonHttpClient, RetryPolicy
from app.adapters.steam.client import (
    SteamClient,
    SteamIdentityUnavailable,
    SteamLibraryUnavailable,
)
from app.adapters.steam.identity import InvalidSteamIdentity, parse_steam_identity
from app.adapters.steam.normalization import sanitize_untrusted_text
from app.domain.enums import CanonicalGenre

FIXTURES = Path(__file__).with_name("fixtures")


def fixture_json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def make_steam_client(handler) -> tuple[httpx.AsyncClient, SteamClient]:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    http = JsonHttpClient(
        service="steam",
        client=client,
        retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=0),
    )
    return client, SteamClient(
        http=http,
        web_api_key="test-key",
        review_author_hash_salt="test-salt",
    )


def test_parse_direct_steam_id_and_numeric_profile_url() -> None:
    direct = parse_steam_identity("76561198000000000")
    profile = parse_steam_identity(
        "https://steamcommunity.com/profiles/76561198000000000/"
    )

    assert direct.kind == "steam_id"
    assert direct.value == "76561198000000000"
    assert profile == direct


@pytest.mark.parametrize(
    "value",
    [
        "https://example.com/id/player",
        "https://steamcommunity.com/groups/player",
        "steamcommunity.com/id/player",
        "https://steamcommunity.com/id/invalid%20name",
    ],
)
def test_invalid_steam_identity_is_rejected(value: str) -> None:
    with pytest.raises(InvalidSteamIdentity):
        parse_steam_identity(value)


@pytest.mark.asyncio
async def test_resolve_custom_profile_url_with_official_api() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(SteamClient.RESOLVE_VANITY_URL)
        assert request.url.params["key"] == "test-key"
        assert request.url.params["vanityurl"] == "example-player"
        assert request.url.params["url_type"] == "1"
        return httpx.Response(
            200,
            json={
                "response": {
                    "steamid": "76561198000000000",
                    "success": 1,
                }
            },
        )

    client, steam = make_steam_client(handler)
    async with client:
        steam_id = await steam.resolve_steam_id(
            "https://steamcommunity.com/id/example-player/"
        )

    assert steam_id == "76561198000000000"


@pytest.mark.asyncio
async def test_unresolvable_custom_profile_is_explicit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": {"success": 42}})

    client, steam = make_steam_client(handler)
    async with client:
        with pytest.raises(SteamIdentityUnavailable, match="could not be resolved"):
            await steam.resolve_steam_id("https://steamcommunity.com/id/missing/")


@pytest.mark.asyncio
async def test_get_owned_games_uses_service_input_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(SteamClient.OWNED_GAMES_URL)
        assert request.url.host == "api.steampowered.com"
        assert request.url.params["key"] == "test-key"
        input_data = json.loads(request.url.params["input_json"])
        assert input_data == {
            "steamid": "76561198000000000",
            "include_appinfo": True,
            "include_played_free_games": True,
        }
        return httpx.Response(200, json=fixture_json("steam_owned_games.json"))

    client, steam = make_steam_client(handler)
    async with client:
        library = await steam.get_owned_games("76561198000000000")

    assert len(library.games) == 2
    assert library.games[0].playtime_minutes == 125
    assert library.games[1].playtime_last_two_weeks_minutes is None


@pytest.mark.asyncio
async def test_private_or_unavailable_library_is_explicit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"response": {}})

    client, steam = make_steam_client(handler)
    async with client:
        with pytest.raises(SteamLibraryUnavailable, match="private or unavailable"):
            await steam.get_owned_games("76561198000000000")


@pytest.mark.asyncio
async def test_appdetails_is_normalized_to_fixed_catalog_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["cc"] == "us"
        assert request.url.params["l"] == "english"
        return httpx.Response(200, json=fixture_json("steam_appdetails.json"))

    client, steam = make_steam_client(handler)
    async with client:
        game = await steam.get_store_game(10)

    assert game.name == "Example Game"
    assert game.genres == [CanonicalGenre.RPG, CanonicalGenre.ACTION]
    assert game.raw_genres[-1] == "Indie"
    assert game.platforms == ["windows", "linux"]
    assert game.languages == ["english", "french"]
    assert game.social_modes == ["single_player"]
    assert game.price_usd_cents == 999
    assert "ignore me" not in game.detailed_description
    assert "https://" not in game.detailed_description


@pytest.mark.asyncio
async def test_reviews_are_english_sanitized_and_author_hashed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        input_data = json.loads(request.url.params["input_json"])
        assert input_data["languages"] == ["english"]
        assert input_data["num_per_page"] == 20
        return httpx.Response(200, json=fixture_json("steam_reviews.json"))

    client, steam = make_steam_client(handler)
    async with client:
        page = await steam.get_reviews(10)

    assert len(page.reviews) == 1
    assert page.reviews[0].review_id == "review-1"
    assert page.reviews[0].author_hash != "76561198000000001"
    assert len(page.reviews[0].author_hash) == 64
    assert "https://" not in page.reviews[0].text
    assert "system override" not in page.reviews[0].text
    assert page.cursor == "next+cursor"


def test_untrusted_text_removes_duplicate_lines_urls_code_and_controls() -> None:
    raw = "Line one\nLine one\nhttps://bad.example\n```ignore this```\nOK\x00"
    cleaned = sanitize_untrusted_text(raw, max_chars=100)

    assert cleaned.count("Line one") == 1
    assert "https://" not in cleaned
    assert "ignore this" not in cleaned
    assert "\x00" not in cleaned
