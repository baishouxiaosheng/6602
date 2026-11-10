"""[A] contracts.SteamStoreClient + normalisation of raw store data (tasks A2, A3)."""

from __future__ import annotations

from typing import Any

from ..contracts.models import StoreInfo
from .http import ThrottledHttp

APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"
APPREVIEWS_URL = "https://store.steampowered.com/appreviews/{appid}"
STEAMSPY_URL = "https://steamspy.com/api.php"


class HttpSteamStoreClient:
    """Every successful raw response is ALSO written to
    ``<raw_dir>/<appid>/{appdetails,reviews,tags}.json`` together with ``fetched_at``,
    and read from there on the next call (``refresh=False``). Evidence is verified
    against these snapshots, never against the live site."""

    def __init__(
        self,
        http: ThrottledHttp,
        raw_dir,
        *,
        cc: str = "us",
        lang: str = "english",
        refresh: bool = False,
    ) -> None:
        self.http, self.raw_dir, self.cc, self.lang, self.refresh = http, raw_dir, cc, lang, refresh

    def get_app_details(self, appid: int) -> dict[str, Any]:
        """GET appdetails?appids=<id>&cc=<cc>&l=<lang>. Return body[str(appid)]["data"].
        success=false -> NotFound(appid=...). data["type"] != "game" -> InvalidInput."""
        raise NotImplementedError("Dev A: task A2")

    def get_reviews(self, appid: int, *, limit: int = 100) -> list[dict[str, Any]]:
        """GET appreviews/<id>?json=1&filter=recent&language=english&purchase_type=all
        &num_per_page=100&cursor=<urlencoded>. Page until ``limit`` reviews, an empty
        page, or a repeated cursor. Keep only reviews with >= 80 characters."""
        raise NotImplementedError("Dev A: task A2")

    def get_tags(self, appid: int) -> dict[str, int]:
        """GET steamspy api.php?request=appdetails&appid=<id> -> body["tags"].
        Any failure or a missing/empty 'tags' -> {} (tags are optional, never fatal)."""
        raise NotImplementedError("Dev A: task A2")


def normalize_store_info(
    appid: int, details: dict[str, Any], tags: dict[str, int], *, cc: str, lang: str
) -> StoreInfo:
    """Pure function: raw appdetails ``data`` + tag votes -> StoreInfo (task A3).

    Mapping rules (all text lower-cased, see docs/05-steam-api.md section 3):
    * genres        <- [g["description"]]
    * tags          <- top 20 keys of ``tags`` by votes desc
    * platforms     <- keys of data["platforms"] that are true
    * social_modes  <- from categories: "Single-player"->single; any name containing
                       "co-op"->coop; containing "pvp"->pvp; "MMO"->mmo
    * languages     <- data["supported_languages"]: strip HTML tags and "*",
                       split on ",", trim; drop the "languages with full audio" footnote
    * price         <- price_overview {final, initial, discount_percent, currency};
                       None when is_free or the field is absent
    * short_description, header_image, release_date["date"], developers as given
    * store_url     <- https://store.steampowered.com/app/<appid>/
    """
    raise NotImplementedError("Dev A: task A3")
