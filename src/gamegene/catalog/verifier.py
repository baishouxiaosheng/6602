"""[A] Evidence verification and grading (task A6). Pure functions, no network.

The retrieval check of the plan: a quote only counts if it can be FOUND in the
cached source it claims to come from.
"""

from __future__ import annotations

from ..contracts.models import EvidenceGrade, SourceType

EXACT = 1.0
FUZZY_MIN = 0.85  # below this the quote is rejected


def normalize_text(text: str) -> str:
    """Lower-case, strip HTML tags and entities, unify quotes/dashes, collapse
    whitespace. Both the quote and the passage go through this before matching."""
    raise NotImplementedError("Dev A: task A6")


def match_score(quote: str, passage: str) -> float:
    """1.0 if normalize(quote) is a substring of normalize(passage); otherwise the
    best difflib.SequenceMatcher ratio of the quote against a sliding window of the
    same length over the passage (step = max(1, len//8)). Quotes shorter than
    8 characters after normalisation -> 0.0."""
    raise NotImplementedError("Dev A: task A6")


def grade_evidence(
    source_type: SourceType, score: float, supporting_reviews: int = 1
) -> EvidenceGrade | None:
    """The grade table (docs/02-gene-schema.md section 4). None = rejected.

    score < 0.85                                   -> None
    store_description / official_docs, score == 1  -> A
    wiki, score == 1                               -> B
    store_review, score == 1, >= 2 reviews support -> B
    everything else that passed 0.85               -> C
    """
    raise NotImplementedError("Dev A: task A6")
