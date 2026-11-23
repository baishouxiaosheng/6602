from fastapi import APIRouter
from pydantic import BaseModel

from app.api.dependencies import ServicesDependency
from app.domain.catalog import Game

router = APIRouter(tags=["catalog"])


class CatalogStatsResponse(BaseModel):
    ok: bool = True
    stats: dict[str, int]


class CatalogGameResponse(BaseModel):
    ok: bool = True
    game: Game


@router.get("/catalog/stats", response_model=CatalogStatsResponse)
async def catalog_stats(services: ServicesDependency) -> CatalogStatsResponse:
    return CatalogStatsResponse(stats=services.catalog.stats())


@router.get("/catalog/games/{appid}", response_model=CatalogGameResponse)
async def catalog_game(
    appid: int, services: ServicesDependency
) -> CatalogGameResponse:
    return CatalogGameResponse(game=services.catalog.get_game(appid))
