"""[A] Workflow 2 orchestration (task A7): fetch -> annotate -> verify -> save.

Status lifecycle of one catalog record (same idea as Lec 6/9):

    (none) --fetch ok--> PENDING --annotate+verify--> VERIFIED   (>= 5 supported genes)
                             |                    \\-> PARTIAL    (< 5 supported genes)
                             \\--any error--------> FAILED       (review_note says what failed)

Rules:
* PENDING is saved BEFORE the model is called, so a crash never loses the fetch.
* An existing VERIFIED record is never overwritten by a FAILED one: on error keep
  the old record and only report the failure in the batch report (plan section 7).
* Re-running skips VERIFIED records unless ``force=True`` (duplicate control).
* Every failure ends in the report with appid, step and message; nothing is silent.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ..contracts.models import CatalogStatus, GameRecord
from ..contracts.protocols import LLMClient, SteamStoreClient
from ..storage import JsonStore


class ItemReport(BaseModel):
    appid: int
    name: str = ""
    outcome: str  # "verified" | "partial" | "failed" | "skipped"
    known_genes: int = 0
    step: str | None = None  # failing step: "fetch" | "annotate" | "verify" | "save"
    error_code: str | None = None
    message: str | None = None


class BatchReport(BaseModel):
    started_at: datetime
    finished_at: datetime
    provider: str
    model: str
    prompt_version: str
    items: list[ItemReport] = Field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for i in self.items:
            out[i.outcome] = out.get(i.outcome, 0) + 1
        return out


def process_game(
    appid: int, *, steam: SteamStoreClient, llm: LLMClient, store: JsonStore, force: bool = False
) -> ItemReport:
    """Run the lifecycle above for one appid and return its report. Never raises
    GameGeneError: errors become ItemReport(outcome='failed', ...)."""
    raise NotImplementedError("Dev A: task A7")


def build_record(appid: int, *args, **kwargs) -> GameRecord:
    """Assemble a GameRecord from StoreInfo + verified claims. Unsupported genes get
    GeneValue(level=None, unknown_reason=...). evidence_id format: 'ev-<gene>-<n>'."""
    raise NotImplementedError("Dev A: task A7")


def run_batch(
    appids: list[int],
    *,
    steam: SteamStoreClient,
    llm: LLMClient,
    store: JsonStore,
    force: bool = False,
    report_dir=None,
) -> BatchReport:
    """Process appids one by one (a failure never stops the batch), then write
    ``<report_dir>/catalog-batch-<UTC timestamp>.json``."""
    raise NotImplementedError("Dev A: task A7")


__all__ = [
    "BatchReport",
    "CatalogStatus",
    "ItemReport",
    "build_record",
    "process_game",
    "run_batch",
]
