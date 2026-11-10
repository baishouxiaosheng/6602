"""[FW] Service selection: the UI and the API get their service from here only."""

from __future__ import annotations

from ..config import Settings, load_settings
from ..contracts.errors import ConfigError
from ..contracts.protocols import GameGeneService


def make_service(settings: Settings | None = None) -> GameGeneService:
    settings = settings or load_settings()
    if settings.service == "demo":
        from .demo_service import DemoService

        return DemoService(settings)
    if settings.service == "real":
        from .real_service import RealService

        return RealService(settings)
    raise ConfigError(f"GAMEGENE_SERVICE must be 'demo' or 'real', got {settings.service!r}")
