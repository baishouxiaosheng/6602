from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import (
    CanonicalGenre,
    CatalogStatus,
    GeneId,
    LevelSupport,
    SemanticReviewStatus,
)
from app.domain.evidence import Evidence
from app.domain.genes import GeneLevel


class Descriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    descriptor_id: str = Field(min_length=1, max_length=64)
    value: bool | str
    evidence_ids: list[str] = Field(default_factory=list)


class GameGene(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gene_id: GeneId
    level: GeneLevel | None = None
    suggested_level: GeneLevel | None = None
    level_support: LevelSupport
    semantic_review_status: SemanticReviewStatus = SemanticReviewStatus.PENDING
    evidence: list[Evidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def supported_level_requires_evidence(self) -> "GameGene":
        if self.level is not None:
            if self.level_support != LevelSupport.SUPPORTED:
                raise ValueError("A non-null level must be supported.")
            if not any(item.trace_status.value == "verified" for item in self.evidence):
                raise ValueError("A non-null level requires verified evidence.")
        return self


class Game(BaseModel):
    appid: int = Field(gt=0, le=4_294_967_295)
    name: str = Field(min_length=1, max_length=256)
    sampling_bucket: CanonicalGenre | None = None
    catalog_status: CatalogStatus = CatalogStatus.PENDING
    genres: list[CanonicalGenre] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    platforms: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    social_modes: list[str] = Field(default_factory=list)
    price_usd_cents: int | None = Field(default=None, ge=0)
    is_free: bool = False
    genes: list[GameGene] = Field(default_factory=list)
    descriptors: list[Descriptor] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_identity_and_unique_genes(self) -> "Game":
        gene_ids = [gene.gene_id for gene in self.genes]
        if len(gene_ids) != len(set(gene_ids)):
            raise ValueError("A game cannot contain duplicate gene IDs.")
        if self.sampling_bucket and self.sampling_bucket not in self.genres:
            raise ValueError("sampling_bucket must be one of the game's genres.")
        if self.is_free and self.price_usd_cents not in (None, 0):
            raise ValueError("A free game cannot have a positive price.")
        return self
