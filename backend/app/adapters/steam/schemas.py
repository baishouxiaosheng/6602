from pydantic import BaseModel, Field

from app.domain.enums import CanonicalGenre


class SteamOwnedGame(BaseModel):
    appid: int = Field(gt=0, le=4_294_967_295)
    name: str | None = None
    playtime_minutes: int = Field(default=0, ge=0)
    playtime_last_two_weeks_minutes: int | None = Field(default=None, ge=0)


class SteamLibrary(BaseModel):
    steam_id: str
    games: list[SteamOwnedGame] = Field(default_factory=list)


class SteamStoreGame(BaseModel):
    appid: int = Field(gt=0, le=4_294_967_295)
    name: str
    app_type: str
    short_description: str = ""
    detailed_description: str = ""
    genres: list[CanonicalGenre] = Field(default_factory=list)
    raw_genres: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    social_modes: list[str] = Field(default_factory=list)
    price_usd_cents: int | None = Field(default=None, ge=0)
    is_free: bool = False
    release_state: str = "unknown"
    raw_payload: dict = Field(default_factory=dict)


class SteamReview(BaseModel):
    review_id: str
    author_hash: str
    language: str
    text: str
    voted_up: bool
    playtime_forever_minutes: int = Field(default=0, ge=0)
    playtime_at_review_minutes: int | None = Field(default=None, ge=0)
    weighted_vote_score: float = Field(default=0.0, ge=0.0)


class SteamReviewPage(BaseModel):
    appid: int
    reviews: list[SteamReview] = Field(default_factory=list)
    cursor: str | None = None
    total_matching: int | None = Field(default=None, ge=0)
