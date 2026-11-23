from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class GameRow(Base):
    __tablename__ = "games"

    appid: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(256))
    sampling_bucket: Mapped[str | None] = mapped_column(String(32), nullable=True)
    catalog_status: Mapped[str] = mapped_column(String(32), index=True)
    genres_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    categories_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    platforms_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    languages_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    social_modes_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    price_usd_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_free: Mapped[bool] = mapped_column(Boolean, default=False)
    descriptors_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    store_source_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    store_fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    genes: Mapped[list["GameGeneRow"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )


class GameGeneRow(Base):
    __tablename__ = "game_genes"
    __table_args__ = (UniqueConstraint("game_appid", "gene_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_appid: Mapped[int] = mapped_column(
        ForeignKey("games.appid", ondelete="CASCADE"), index=True
    )
    gene_id: Mapped[str] = mapped_column(String(32))
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    suggested_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    level_support: Mapped[str] = mapped_column(String(32))
    semantic_review_status: Mapped[str] = mapped_column(String(32))
    annotation_stage: Mapped[str] = mapped_column(String(32), default="official")
    prompt_version: Mapped[str] = mapped_column(String(64), default="unassigned")
    model_name: Mapped[str] = mapped_column(String(128), default="unassigned")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    game: Mapped[GameRow] = relationship(back_populates="genes")
    evidence: Mapped[list["EvidenceRow"]] = relationship(
        back_populates="game_gene", cascade="all, delete-orphan"
    )


class EvidenceRow(Base):
    __tablename__ = "evidence"

    evidence_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    game_gene_id: Mapped[int] = mapped_column(
        ForeignKey("game_genes.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(64))
    source_priority: Mapped[str] = mapped_column(String(16))
    trace_status: Mapped[str] = mapped_column(String(16))
    level_support: Mapped[str] = mapped_column(String(16))
    quote_original: Mapped[str] = mapped_column(Text)
    source_locator: Mapped[str] = mapped_column(String(256))
    source_record_id: Mapped[str] = mapped_column(String(128))
    review_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    review_author_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_source_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    game_gene: Mapped[GameGeneRow] = relationship(back_populates="evidence")


class ProfileRow(Base):
    __tablename__ = "profiles"

    profile_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(80))
    questionnaire_version: Mapped[str] = mapped_column(String(32), default="v1")
    questionnaire_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    free_text: Mapped[str] = mapped_column(Text, default="")
    familiar_genres_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    hard_filters_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    soft_preferences_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    gene_profile_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    owned_appids_json: Mapped[list[int]] = mapped_column(JSON, default=list)
    warnings_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    steam_import_status: Mapped[str] = mapped_column(String(32), default="not_imported")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    owned_games: Mapped[list["OwnedGameRow"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class OwnedGameRow(Base):
    __tablename__ = "owned_games"

    profile_id: Mapped[str] = mapped_column(
        ForeignKey("profiles.profile_id", ondelete="CASCADE"), primary_key=True
    )
    appid: Mapped[int] = mapped_column(Integer, primary_key=True)
    playtime_minutes: Mapped[int] = mapped_column(Integer, default=0)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    liked_aspects_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    participates_in_profile: Mapped[bool] = mapped_column(Boolean, default=True)

    profile: Mapped[ProfileRow] = relationship(back_populates="owned_games")


class RecommendationRunRow(Base):
    __tablename__ = "recommendation_runs"

    run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("profiles.profile_id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), index=True)
    candidate_facts_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    llm_result_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    validated_result_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class JobRow(Base):
    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), index=True)
    current_step: Mapped[str] = mapped_column(String(128))
    processed_items: Mapped[int] = mapped_column(Integer, default=0)
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    result_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
