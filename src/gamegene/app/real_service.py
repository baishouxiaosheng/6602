"""[B] The production implementation of contracts.GameGeneService (task B6).

Thin: every method delegates to profile.builder / recommend.pipeline / the store.
No business logic lives here. Selected with GAMEGENE_SERVICE=real.
"""

from __future__ import annotations

from ..config import Settings
from ..contracts.models import (
    CatalogStats,
    InterviewSpec,
    ProfileRequest,
    RecommendationRun,
    RecommendRequest,
    RunSummary,
    UserProfile,
)


class RealService:
    def __init__(self, settings: Settings) -> None:
        """Build JsonStore(settings.data_dir), catalog.reader.make_catalog, llm.make_llm
        and (when STEAM_API_KEY is set) HttpSteamLibraryClient, as PUBLIC attributes
        ``self.store``, ``self.catalog``, ``self.llm``, ``self.steam`` (None without a
        key) so tests can swap them. Keep the warnings of the last build_profile call
        in ``self.last_warnings`` (the UI shows them)."""
        raise NotImplementedError("Dev B: task B6")

    last_warnings: list[str]

    def get_interview(self) -> InterviewSpec:
        raise NotImplementedError("Dev B: task B6")

    def build_profile(self, request: ProfileRequest) -> UserProfile:
        raise NotImplementedError("Dev B: task B6")

    def get_profile(self, profile_id: str) -> UserProfile:
        raise NotImplementedError("Dev B: task B6")

    def list_profiles(self) -> list[str]:
        raise NotImplementedError("Dev B: task B6")

    def recommend(self, request: RecommendRequest) -> RecommendationRun:
        raise NotImplementedError("Dev B: task B6")

    def get_run(self, run_id: str) -> RecommendationRun:
        raise NotImplementedError("Dev B: task B6")

    def list_runs(self, profile_id: str | None = None) -> list[RunSummary]:
        """Newest first. RunSummary.titles = names of recommended games (or closest)."""
        raise NotImplementedError("Dev B: task B6")

    def catalog_stats(self) -> CatalogStats:
        raise NotImplementedError("Dev B: task B6")
