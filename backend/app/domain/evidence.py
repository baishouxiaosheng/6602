from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import GeneId, LevelSupport, SourcePriority, TraceStatus


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1, max_length=128)
    appid: int = Field(gt=0, le=4_294_967_295)
    gene_id: GeneId | None = None
    source_type: str = Field(min_length=1, max_length=64)
    source_priority: SourcePriority
    trace_status: TraceStatus
    level_support: LevelSupport
    quote_original: str = Field(min_length=1, max_length=8_000)
    source_locator: str = Field(min_length=1, max_length=256)
    source_record_id: str = Field(min_length=1, max_length=128)
    review_id: str | None = None
    review_author_hash: str | None = None

    @model_validator(mode="after")
    def low_priority_requires_review_identity(self) -> "Evidence":
        if self.source_priority == SourcePriority.LOW:
            if not self.review_id or not self.review_author_hash:
                raise ValueError(
                    "Low-priority review evidence requires review_id and author hash."
                )
        return self
