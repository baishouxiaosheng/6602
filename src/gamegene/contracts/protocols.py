"""Interfaces between the three owners. Code against these, never against a concrete class.

Owner legend:  [FW] framework (done)   [A] Dev A   [B] Dev B   [UI] front end (done)
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

from .models import (
    CatalogStats,
    GameRecord,
    InterviewSpec,
    OwnedGame,
    ProfileRequest,
    RecommendationRun,
    RecommendRequest,
    RunSummary,
    UserProfile,
)

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class LLMClient(Protocol):
    """[FW] Provider-independent model access. Implemented in gamegene.llm."""

    provider: str
    model: str

    def complete_json(
        self, *, system: str, user: str, schema: type[T], temperature: float = 0.2
    ) -> T:
        """Return a validated ``schema`` instance.

        Raises UpstreamError (retryable transport failure, after bounded retries)
        or LLMOutputInvalid (answer never validated; details has model + raw_head).
        """
        ...


@runtime_checkable
class SteamStoreClient(Protocol):
    """[A] Public store data, no key needed. Implemented in gamegene.steam.store."""

    def get_app_details(self, appid: int) -> dict[str, Any]:
        """Raw ``data`` object of store appdetails. Raises NotFound when success=false."""
        ...

    def get_reviews(self, appid: int, *, limit: int = 100) -> list[dict[str, Any]]:
        """Up to ``limit`` raw review objects (most helpful recent English reviews)."""
        ...

    def get_tags(self, appid: int) -> dict[str, int]:
        """User tag -> vote count (SteamSpy). Empty dict when unavailable; never raises
        for a merely missing game."""
        ...


@runtime_checkable
class SteamLibraryClient(Protocol):
    """[A] Steam Web API (needs STEAM_API_KEY). Implemented in gamegene.steam.library."""

    def resolve_steam_id(self, steam_id_or_url: str) -> str:
        """Accepts a 17-digit id, /profiles/<id> URL, /id/<vanity> URL or bare vanity name.
        Returns the 64-bit id as a string. Raises InvalidInput / NotFound."""
        ...

    def get_owned_games(self, steam_id: str) -> list[OwnedGame]:
        """Raises SteamProfilePrivate when the response is empty (private profile)."""
        ...


@runtime_checkable
class CatalogReader(Protocol):
    """[FW] Read side of the catalog. FixtureCatalog and StoreCatalog implement it."""

    source: str

    def list_games(self) -> list[GameRecord]: ...

    def get_game(self, appid: int) -> GameRecord:
        """Raises NotFound."""
        ...


@runtime_checkable
class GameGeneService(Protocol):
    """[B] The ONLY surface the UI and the HTTP API call.

    DemoService [FW] is a working reference stub; RealService [B] is the product.
    Every method raises GameGeneError subclasses only.
    """

    def get_interview(self) -> InterviewSpec: ...

    def build_profile(self, request: ProfileRequest) -> UserProfile:
        """Workflow 1. Validate -> score interview -> optional library import -> save."""
        ...

    def get_profile(self, profile_id: str) -> UserProfile: ...

    def list_profiles(self) -> list[str]: ...

    def recommend(self, request: RecommendRequest) -> RecommendationRun:
        """Workflow 3. Always returns a SAVED run (status ok / closest_only / no_match /
        error) once the request passed validation and the profile exists; raises
        InvalidInput / NotFound before that point."""
        ...

    def get_run(self, run_id: str) -> RecommendationRun: ...

    def list_runs(self, profile_id: str | None = None) -> list[RunSummary]: ...

    def catalog_stats(self) -> CatalogStats: ...
