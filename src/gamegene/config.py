"""Runtime settings, read once from the environment (.env is loaded if present)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
RESOURCES = Path(__file__).resolve().parent / "resources"
PROMPTS = Path(__file__).resolve().parent / "prompts"


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    llm_api_key: str
    llm_model: str
    llm_base_url: str
    llm_max_retries: int
    llm_timeout_s: float
    steam_api_key: str
    steam_cc: str
    steam_lang: str
    steam_min_interval_s: float
    data_dir: Path
    catalog_source: str  # "fixture" | "store"
    service: str  # "demo" | "real"

    @property
    def raw_dir(self) -> Path:
        """Raw Steam snapshots (never committed). Sibling of the store directory."""
        return self.data_dir.parent / "raw"


def load_settings(env_file: str | os.PathLike[str] | None = None) -> Settings:
    load_dotenv(env_file or REPO_ROOT / ".env", override=False)
    e = os.environ.get
    data_dir = Path(e("GAMEGENE_DATA_DIR", "data/store"))
    if not data_dir.is_absolute():
        data_dir = REPO_ROOT / data_dir
    return Settings(
        llm_provider=e("LLM_PROVIDER", "fake").strip().lower(),
        llm_api_key=e("LLM_API_KEY", ""),
        llm_model=e("LLM_MODEL", ""),
        llm_base_url=e("LLM_BASE_URL", ""),
        llm_max_retries=int(e("LLM_MAX_RETRIES", "2")),
        llm_timeout_s=float(e("LLM_TIMEOUT_S", "60")),
        steam_api_key=e("STEAM_API_KEY", ""),
        steam_cc=e("STEAM_CC", "us"),
        steam_lang=e("STEAM_LANG", "english"),
        steam_min_interval_s=float(e("STEAM_MIN_INTERVAL_S", "1.5")),
        data_dir=data_dir,
        catalog_source=e("GAMEGENE_CATALOG", "fixture").strip().lower(),
        service=e("GAMEGENE_SERVICE", "demo").strip().lower(),
    )
