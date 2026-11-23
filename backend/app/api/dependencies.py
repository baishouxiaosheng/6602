from dataclasses import dataclass
from typing import Annotated

import httpx
from fastapi import Depends, Request

from app.adapters.http import JsonHttpClient, RetryPolicy
from app.adapters.llm.base import LLMClient
from app.adapters.llm.qwen import QwenLLMClient
from app.adapters.steam.client import SteamClient
from app.config import Settings, get_settings
from app.persistence.database import Database
from app.persistence.migrations import initialize_database
from app.services.catalog import CatalogService
from app.services.jobs import JobService
from app.services.profile import ProfileService
from app.services.recommendation import RecommendationService
from app.services.steam_import import SteamImportService


@dataclass
class AppServices:
    database: Database
    profile: ProfileService
    catalog: CatalogService
    steam_import: SteamImportService
    recommendation: RecommendationService
    jobs: JobService
    http_client: httpx.AsyncClient | None = None


def build_services(settings: Settings) -> AppServices:
    database = initialize_database(settings.database_url)
    http_client = httpx.AsyncClient()
    steam = SteamClient(
        http=JsonHttpClient(service="steam", client=http_client),
        web_api_key=settings.steam_web_api_key,
        review_author_hash_salt=(
            settings.review_author_hash_salt or "development-review-salt"
        ),
    )
    llm: LLMClient | None = None
    if settings.dashscope_api_key and settings.qwen_base_url and settings.qwen_model:
        llm = QwenLLMClient(
            http=JsonHttpClient(
                service="qwen",
                client=http_client,
                retry_policy=RetryPolicy(
                    max_attempts=2,
                    backoff_seconds=1,
                    timeout_seconds=settings.qwen_timeout_seconds,
                ),
            ),
            api_key=settings.dashscope_api_key,
            base_url=settings.qwen_base_url,
            model=settings.qwen_model,
        )
    catalog = CatalogService(database, steam, llm)
    return AppServices(
        database=database,
        profile=ProfileService(database, llm),
        catalog=catalog,
        steam_import=SteamImportService(
            database,
            steam,
            catalog,
            annotate_uncatalogued_inventory=settings.annotate_uncatalogued_inventory,
        ),
        recommendation=RecommendationService(database, llm),
        jobs=JobService(database),
        http_client=http_client,
    )


def get_services(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AppServices:
    services = getattr(request.app.state, "services", None)
    if services is None:
        services = build_services(settings)
        request.app.state.services = services
    return services


ServicesDependency = Annotated[AppServices, Depends(get_services)]
