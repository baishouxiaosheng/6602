"""[B] Workflow 1 orchestration (task B2)."""

from __future__ import annotations

from ..contracts.models import ProfileRequest, UserProfile
from ..contracts.protocols import CatalogReader, SteamLibraryClient
from ..storage import JsonStore


def validate_profile_request(request: ProfileRequest, *, store: JsonStore) -> None:
    """Deterministic checks, BEFORE any Steam call. Collect ALL problems, then raise
    InvalidInput(problems=[...]). NotFound if profile_id is given but does not exist.

    * display_name: 1-40 chars after strip
    * answers: profile.interview.validate_answers
    * filters.max_price_cents >= 0; excluded tags lower-cased and stripped
    * steam_id_or_url: if given, non-empty after strip and <= 200 chars
    """
    raise NotImplementedError("Dev B: task B2")


def build_profile(
    request: ProfileRequest,
    *,
    store: JsonStore,
    catalog: CatalogReader,
    steam: SteamLibraryClient | None,
) -> tuple[UserProfile, list[str]]:
    """Return (saved profile, warnings).

    1. validate (above)                       -> InvalidInput / NotFound, nothing saved
    2. score_interview                        -> prefs, familiar tags
    3. if steam_id_or_url: resolve + get_owned_games (retry.retry_call, attempts=3)
         SteamProfilePrivate / UpstreamError / NotFound / missing client or key
         -> DO NOT fail: keep the interview-only profile and append a warning such as
            "Steam 库导入失败（profile private）：已仅用访谈结果生成画像"
         success -> profile.library.blend_library, owned_appids = all owned appids
    4. profile_id: given -> revise (store.put creates revision n+1; when the request
       has no steam id, keep owned_appids and steam_id of the previous revision);
       None -> new id "p-" + 8 lower-case hex chars
    5. store.put(Kind.PROFILE, ...) and return the stored data
    """
    raise NotImplementedError("Dev B: task B2")
