from dataclasses import dataclass
from math import log1p
from uuid import uuid4

from app.adapters.steam.client import SteamClient
from app.algorithms.profile_fusion import LibraryGeneSignal, fuse_profile
from app.domain.enums import CatalogStatus, GeneId
from app.domain.profiles import (
    FavoriteOwnedGame,
    OwnedGameRecord,
    PlayerProfile,
    SteamImportConfirmRequest,
    SteamImportPreview,
    SteamImportPreviewRequest,
)
from app.persistence.database import Database
from app.persistence.repositories import (
    GameRepository,
    OwnedGameRepository,
    ProfileRepository,
)
from app.services.catalog import CatalogService
from app.services.errors import NotFoundError, ServiceError
from app.services.jobs import ProgressCallback
from app.services.profile import parsed_preferences_from_profile


@dataclass(frozen=True)
class _PendingPreview:
    profile_id: str
    steam_id: str
    games: list[OwnedGameRecord]


def _mask_steam_id(steam_id: str) -> str:
    return f"{'*' * max(0, len(steam_id) - 4)}{steam_id[-4:]}"


class SteamImportService:
    def __init__(
        self,
        database: Database,
        steam: SteamClient,
        catalog: CatalogService,
        *,
        annotate_uncatalogued_inventory: bool = False,
    ) -> None:
        self.database = database
        self.steam = steam
        self.catalog = catalog
        self.annotate_uncatalogued_inventory = annotate_uncatalogued_inventory
        self._previews: dict[str, _PendingPreview] = {}

    async def preview(
        self, profile_id: str, request: SteamImportPreviewRequest
    ) -> SteamImportPreview:
        with self.database.session_factory() as session:
            if ProfileRepository(session).get(profile_id) is None:
                raise NotFoundError("Profile", profile_id)

        steam_id = await self.steam.resolve_steam_id(str(request.steam_id_or_url))
        library = await self.steam.get_owned_games(steam_id)
        games = [
            OwnedGameRecord(
                appid=item.appid,
                name=item.name,
                playtime_minutes=item.playtime_minutes,
                participates_in_profile=item.playtime_minutes > 0,
            )
            for item in library.games
        ]
        token = f"preview_{uuid4().hex}"
        self._previews[token] = _PendingPreview(
            profile_id=profile_id,
            steam_id=steam_id,
            games=games,
        )
        return SteamImportPreview(
            preview_token=token,
            steam_id_masked=_mask_steam_id(steam_id),
            games=games,
        )

    def _get_preview(
        self, profile_id: str, preview_token: str
    ) -> _PendingPreview:
        preview = self._previews.get(preview_token)
        if preview is None or preview.profile_id != profile_id:
            raise ServiceError(
                "invalid_preview_token",
                "Steam import preview token is invalid or expired.",
            )
        return preview

    @staticmethod
    def _favorite_map(
        favorites: list[FavoriteOwnedGame], owned_appids: set[int]
    ) -> dict[int, FavoriteOwnedGame]:
        if len({item.appid for item in favorites}) != len(favorites):
            raise ServiceError(
                "invalid_favorites", "Favorite games cannot contain duplicates."
            )
        if any(item.appid not in owned_appids for item in favorites):
            raise ServiceError(
                "invalid_favorites", "Favorites must come from the previewed library."
            )
        valid_aspects = set(GeneId._value2member_map_)
        if any(
            aspect not in valid_aspects
            for item in favorites
            for aspect in item.liked_aspects
        ):
            raise ServiceError(
                "invalid_favorites",
                "Liked aspects must use the fixed nine game-gene IDs.",
            )
        return {item.appid: item for item in favorites}

    def _build_library_signal(
        self, profile: PlayerProfile, records: list[OwnedGameRecord]
    ) -> LibraryGeneSignal:
        targets = {
            item.gene_id: item.questionnaire_target
            for item in profile.gene_contributions
        }
        totals = {gene_id: 0.0 for gene_id in GeneId}
        weights = {gene_id: 0.0 for gene_id in GeneId}
        sources: dict[GeneId, list[int]] = {gene_id: [] for gene_id in GeneId}

        with self.database.session_factory() as session:
            repository = GameRepository(session)
            games = {record.appid: repository.get(record.appid) for record in records}

        for record in records:
            game = games.get(record.appid)
            if (
                game is None
                or game.catalog_status
                not in {CatalogStatus.PARTIAL, CatalogStatus.VERIFIED}
                or record.playtime_minutes <= 0
            ):
                continue
            liked_genes = {
                GeneId(item)
                for item in record.liked_aspects
                if item in GeneId._value2member_map_
            }
            weak_weight = min(log1p(record.playtime_minutes) / log1p(6_000), 1.0) * 0.25
            for gene in game.genes:
                if gene.level is None:
                    continue
                weight = weak_weight
                if record.is_favorite and gene.gene_id in liked_genes:
                    weight += 1.0
                if weight <= 0:
                    continue
                totals[gene.gene_id] += gene.level * weight
                weights[gene.gene_id] += weight
                sources[gene.gene_id].append(record.appid)

        directions: dict[GeneId, int] = {}
        source_appids: dict[GeneId, list[int]] = {}
        for gene_id in GeneId:
            if weights[gene_id] <= 0:
                continue
            average = totals[gene_id] / weights[gene_id]
            difference = average - targets[gene_id]
            if difference >= 0.5:
                directions[gene_id] = 1
            elif difference <= -0.5:
                directions[gene_id] = -1
            if gene_id in directions:
                source_appids[gene_id] = sorted(set(sources[gene_id]))
        return LibraryGeneSignal(
            directions=directions,
            source_appids=source_appids,
        )

    async def confirm(
        self,
        profile_id: str,
        request: SteamImportConfirmRequest,
        progress: ProgressCallback,
    ) -> str:
        preview = self._get_preview(profile_id, request.preview_token)
        owned_appids = {item.appid for item in preview.games}
        favorites = self._favorite_map(request.favorite_games, owned_appids)
        records = [
            item.model_copy(
                update={
                    "is_favorite": item.appid in favorites,
                    "liked_aspects": (
                        favorites[item.appid].liked_aspects
                        if item.appid in favorites
                        else []
                    ),
                }
            )
            for item in preview.games
        ]

        with self.database.session_factory() as session:
            catalog_appids = {
                game.appid for game in GameRepository(session).list()
            }
        uncatalogued_count = sum(
            record.appid not in catalog_appids for record in records
        )
        total = len(records)
        for index, record in enumerate(records, start=1):
            if self.annotate_uncatalogued_inventory:
                await self.catalog.annotate_game(record.appid)
            progress(
                (
                    "annotating_inventory"
                    if self.annotate_uncatalogued_inventory
                    else "indexing_inventory"
                ),
                index,
                total,
            )

        with self.database.session_factory() as session:
            repository = ProfileRepository(session)
            current = repository.get(profile_id)
            submission = repository.get_questionnaire(profile_id)
        if current is None or submission is None:
            raise NotFoundError("Profile", profile_id)

        warnings = list(current.warnings)
        if uncatalogued_count and not self.annotate_uncatalogued_inventory:
            warnings.append(
                f"{uncatalogued_count} owned games are outside the reviewed catalog; "
                "they are excluded from recommendations but do not influence the gene profile."
            )
        profile = fuse_profile(
            profile_id=profile_id,
            submission=submission,
            library_signal=self._build_library_signal(current, records),
            parsed_preferences=parsed_preferences_from_profile(current),
            confirmed_hard_filters=current.hard_filters,
            owned_appids=owned_appids,
            warnings=warnings,
        )
        with self.database.session_factory.begin() as session:
            ProfileRepository(session).save(
                profile,
                steam_import_status="imported",
            )
            OwnedGameRepository(session).replace_for_profile(profile_id, records)
        self._previews.pop(request.preview_token, None)
        return profile_id
