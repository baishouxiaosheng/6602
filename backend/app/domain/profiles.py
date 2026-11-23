from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.domain.enums import (
    CanonicalGenre,
    GeneId,
    SocialRequirement,
)
from app.domain.genes import GeneContribution, GeneLevel


class FamiliarGenre(BaseModel):
    genre: CanonicalGenre
    rank: Annotated[int, Field(ge=1, le=3)]
    weight: Annotated[int, Field(ge=1, le=3)]


class HardFilters(BaseModel):
    platforms: list[str] = Field(default_factory=list, max_length=3)
    required_language: str = "english"
    max_price_usd_cents: int | None = Field(default=None, ge=0)
    social_requirement: SocialRequirement = SocialRequirement.ANY
    controller_required: bool = False
    exclude_owned: bool = True


class QuestionnaireSubmission(BaseModel):
    display_name: str = Field(min_length=1, max_length=80)
    gene_targets: dict[GeneId, GeneLevel]
    important_genes: list[GeneId] = Field(default_factory=list, max_length=3)
    familiar_genres: list[FamiliarGenre] = Field(min_length=1, max_length=3)
    hard_filters: HardFilters = Field(default_factory=HardFilters)
    additional_preferences: str = Field(default="", max_length=2_000)

    @model_validator(mode="after")
    def validate_complete_questionnaire(self) -> "QuestionnaireSubmission":
        if set(self.gene_targets) != set(GeneId):
            raise ValueError("All nine gene targets are required exactly once.")
        if len(self.important_genes) != len(set(self.important_genes)):
            raise ValueError("important_genes cannot contain duplicates.")

        genres = [item.genre for item in self.familiar_genres]
        ranks = [item.rank for item in self.familiar_genres]
        if len(genres) != len(set(genres)):
            raise ValueError("Familiar genres cannot contain duplicates.")
        if sorted(ranks) != list(range(1, len(ranks) + 1)):
            raise ValueError("Familiar genre ranks must be contiguous from 1.")
        expected_weight = {1: 3, 2: 2, 3: 1}
        if any(item.weight != expected_weight[item.rank] for item in self.familiar_genres):
            raise ValueError("Familiar genre weight must match rank 3/2/1.")
        return self


class PreferenceParseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gene_adjustments: dict[GeneId, Annotated[int, Field(ge=-1, le=1)]] = Field(
        default_factory=dict
    )
    soft_descriptor_preferences: list[str] = Field(
        default_factory=list, max_length=20
    )
    potential_hard_constraints: list[str] = Field(
        default_factory=list, max_length=10
    )
    unsupported_requests: list[str] = Field(default_factory=list, max_length=10)


class PreferenceConfirmRequest(BaseModel):
    parsed_preferences: PreferenceParseResult
    confirmed_hard_constraints: list[str] = Field(
        default_factory=list, max_length=10
    )

    @model_validator(mode="after")
    def confirmed_constraints_must_be_suggested(self) -> "PreferenceConfirmRequest":
        suggested = set(self.parsed_preferences.potential_hard_constraints)
        if not set(self.confirmed_hard_constraints).issubset(suggested):
            raise ValueError("Confirmed constraints must come from the parsed suggestions.")
        return self


class PlayerProfile(BaseModel):
    profile_id: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)
    gene_contributions: list[GeneContribution] = Field(min_length=9, max_length=9)
    familiar_genres: list[FamiliarGenre] = Field(min_length=1, max_length=3)
    hard_filters: HardFilters
    soft_descriptor_preferences: list[str] = Field(default_factory=list)
    owned_appids: set[int] = Field(default_factory=set)
    free_text: str = Field(default="", max_length=2_000)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_complete_genes(self) -> "PlayerProfile":
        gene_ids = [item.gene_id for item in self.gene_contributions]
        if set(gene_ids) != set(GeneId) or len(gene_ids) != len(set(gene_ids)):
            raise ValueError("A profile requires one contribution for every gene.")
        return self


class SteamImportPreviewRequest(BaseModel):
    steam_id_or_url: str | HttpUrl
    consent: bool

    @model_validator(mode="after")
    def require_consent(self) -> "SteamImportPreviewRequest":
        if not self.consent:
            raise ValueError("Steam import consent is required.")
        return self


class FavoriteOwnedGame(BaseModel):
    appid: int = Field(gt=0, le=4_294_967_295)
    liked_aspects: list[str] = Field(default_factory=list, max_length=9)
    liked_reason: str = Field(default="", max_length=1_000)


class OwnedGameRecord(BaseModel):
    appid: int = Field(gt=0, le=4_294_967_295)
    name: str | None = Field(default=None, max_length=256)
    playtime_minutes: int = Field(default=0, ge=0)
    is_favorite: bool = False
    liked_aspects: list[str] = Field(default_factory=list, max_length=9)
    participates_in_profile: bool = True


class SteamImportConfirmRequest(BaseModel):
    preview_token: str = Field(min_length=1, max_length=256)
    favorite_games: list[FavoriteOwnedGame] = Field(default_factory=list)


class SteamImportPreview(BaseModel):
    preview_token: str
    steam_id_masked: str
    games: list[OwnedGameRecord]
    warnings: list[str] = Field(default_factory=list)


class ProfileApiResponse(BaseModel):
    ok: bool = True
    profile: PlayerProfile
    meta: dict[str, Any] = Field(default_factory=dict)
