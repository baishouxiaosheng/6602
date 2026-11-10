"""[B] Constrained explanation (task B4). Prompt: prompts/explain_v1.md."""

from __future__ import annotations

from ..contracts.models import Explanation, GameRecord, SharedGene, Track, UserProfile
from ..contracts.protocols import LLMClient

PROMPT_VERSION = "explain-v1"


def template_explanation(
    game: GameRecord, shared: list[SharedGene], *, mismatch: str | None = None
) -> Explanation:
    """Deterministic fallback, never fails. generated_by='template'. One reason per
    shared gene (max 3): '你想要的强度是 x / 4，本作为 y / 4。' (the UI already shows the
    gene name and the evidence quote next to each reason, so do not repeat them)."""
    raise NotImplementedError("Dev B: task B4")


def check_explanation(explanation: Explanation, shared: list[SharedGene]) -> list[str]:
    """Rules decide (Lec 9). Return a list of violations, empty = accepted:
    * 1 <= len(reasons) <= 3
    * every reason.gene is one of the shared genes
    * every reason.evidence_id equals the evidence_id supplied for that gene
    * no gene appears twice
    """
    raise NotImplementedError("Dev B: task B4")


def explain(
    llm: LLMClient,
    profile: UserProfile,
    game: GameRecord,
    track: Track,
    shared: list[SharedGene],
    *,
    mismatch: str | None = None,
) -> tuple[Explanation, bool]:
    """Return (explanation, fell_back).

    llm.complete_json(schema=Explanation) -> check_explanation.
    Violations, LLMOutputInvalid or UpstreamError -> template_explanation, True.
    (The adapter already retried; do not add another retry loop here.)
    Force generated_by='llm' on an accepted model answer."""
    raise NotImplementedError("Dev B: task B4")
