"""[A] LLM gene annotation (task A5). Prompt: prompts/annotate_genes_v1.md."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..contracts.genes import GeneId
from ..contracts.models import Confidence
from ..contracts.protocols import LLMClient

PROMPT_VERSION = "annotate-v1"


class GeneClaim(BaseModel):
    """What the model must return for ONE gene."""

    gene: GeneId
    level: int | None = Field(default=None, ge=0, le=4)  # null = "I cannot support a level"
    confidence: Confidence | None = None
    quote: str | None = None  # copied verbatim from ONE numbered source passage
    source_index: int | None = None  # index of that passage in the prompt


class AnnotationOut(BaseModel):
    """Schema passed to LLMClient.complete_json. Exactly nine claims, one per gene."""

    claims: list[GeneClaim]


class SourcePassage(BaseModel):
    index: int
    source_type: str  # contracts.SourceType value
    source_ref: str  # URL or recommendationid
    text: str


def build_passages(
    appid: int, details: dict[str, Any], reviews: list[dict[str, Any]], tags: dict[str, int]
) -> list[SourcePassage]:
    """Deterministic. Passage 0..n: store description split into paragraphs (HTML
    stripped, source_type=store_description, ref=store URL); then up to 30 reviews
    ordered by votes_up desc (truncate each to 1200 chars, ref=recommendationid).
    Total prompt budget <= 24k characters: drop the least-voted reviews first."""
    raise NotImplementedError("Dev A: task A5")


def annotate(
    llm: LLMClient, name: str, passages: list[SourcePassage], tags: dict[str, int]
) -> AnnotationOut:
    """Render the prompt, call ``llm.complete_json(schema=AnnotationOut)`` and
    post-check deterministically (model output is a CLAIM, not a fact):
    * exactly one claim per gene, else LLMOutputInvalid;
    * a claim with level but without quote/source_index -> downgrade to level=None;
    * confidence != high -> downgrade to level=None (plan: 'only high-confidence values').
    Errors (UpstreamError / LLMOutputInvalid) propagate to the pipeline."""
    raise NotImplementedError("Dev A: task A5")
