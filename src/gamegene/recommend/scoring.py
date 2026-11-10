"""[FW] Frozen scoring core: pure functions, no I/O, no model.

"AI recommends, rules decide" (Lec 9): everything that decides WHETHER a game is
recommended lives here and is deterministic. The model only words the explanation.
docs/04-recommendation-spec.md is the prose version; tests/framework/test_scoring.py
pins the numbers. Change thresholds only through an ADR.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts.genes import GENE_ORDER, GENES, MAX_LEVEL
from ..contracts.models import (
    MIN_KNOWN_GENES,
    Confidence,
    Evidence,
    EvidenceGrade,
    GameRecord,
    SharedGene,
    Track,
    UserProfile,
)

STRONG_SCORE = 0.72  # at or above: may be recommended
CLOSEST_FLOOR = 0.55  # at or above (but not recommendable): may be shown as "closest"
TRACK_OVERLAP = 0.30  # surface_overlap at or above: same track, below: cross track
SHARED_USER_MIN = 2.5  # user target at or above ...
SHARED_GAME_MIN = 3  # ... and game level at or above -> a shared gene
COVERAGE_FLOOR = 0.7  # score = similarity * (COVERAGE_FLOOR + (1-COVERAGE_FLOOR)*coverage)
BARRIER_GAP = 2.0  # |target - level| at or above, on a gene with weight >= 0.6 -> barrier
BARRIER_WEIGHT = 0.6

_GRADE_RANK = {EvidenceGrade.A: 0, EvidenceGrade.B: 1, EvidenceGrade.C: 2}


@dataclass(frozen=True)
class ScoreParts:
    similarity: float
    coverage: float
    score: float


def gene_score(profile: UserProfile, game: GameRecord) -> ScoreParts | None:
    """Weighted closeness over the genes the game actually knows.

    similarity = 1 - sum_k(w*|target-level|) / (4 * sum_k(w))      k = known genes
    coverage   = sum_k(w) / sum_all(w)
    score      = similarity * (0.7 + 0.3 * coverage)
    Returns None when the game has fewer than MIN_KNOWN_GENES known genes or the
    profile has zero total weight (not scorable -> filtered as 'insufficient_genes').
    """
    total_w = sum(profile.genes[g].weight for g in GENE_ORDER)
    known = [g for g in GENE_ORDER if game.genes[g].level is not None]
    known_w = sum(profile.genes[g].weight for g in known)
    if len(known) < MIN_KNOWN_GENES or total_w <= 0 or known_w <= 0:
        return None
    dist = sum(
        profile.genes[g].weight * abs(profile.genes[g].target - game.genes[g].level)  # type: ignore[operator]
        for g in known
    ) / (MAX_LEVEL * known_w)
    similarity = 1.0 - dist
    coverage = known_w / total_w
    score = similarity * (COVERAGE_FLOOR + (1.0 - COVERAGE_FLOOR) * coverage)
    return ScoreParts(round(similarity, 4), round(coverage, 4), round(score, 4))


def surface_labels(game: GameRecord) -> set[str]:
    return {t.lower() for t in game.store.genres} | {t.lower() for t in game.store.tags}


def surface_overlap(profile: UserProfile, game: GameRecord) -> float:
    """How much the game LOOKS like what the user already plays (0..1).

    overlap = sum of familiar weights of the game's labels
              / sum of the user's n largest familiar weights, n = min(#labels, #familiar)
    i.e. 1.0 means "as familiar as a game with this many labels could possibly be".
    0.0 when the user has no familiar tags or the game has no labels.
    """
    labels = surface_labels(game)
    fam = profile.familiar_tags
    if not labels or not fam:
        return 0.0
    hit = sum(fam.get(t, 0.0) for t in labels)
    n = min(len(labels), len(fam))
    best = sum(sorted(fam.values(), reverse=True)[:n])
    return round(min(1.0, hit / best), 4) if best > 0 else 0.0


def assign_track(overlap: float) -> Track:
    return Track.SAME if overlap >= TRACK_OVERLAP else Track.CROSS


def best_evidence(game: GameRecord, evidence_ids: list[str]) -> Evidence | None:
    by_id = game.evidence_by_id()
    items = [by_id[i] for i in evidence_ids if i in by_id]
    if not items:
        return None
    return min(items, key=lambda e: (_GRADE_RANK[e.grade], -e.match_score, e.evidence_id))


def shared_genes(profile: UserProfile, game: GameRecord) -> list[SharedGene]:
    """Genes the user wants (target >= 2.5) AND the game has (level >= 3) with evidence.
    Ordered by weight * level, strongest first; ties broken by gene order."""
    out: list[tuple[float, int, SharedGene]] = []
    for idx, g in enumerate(GENE_ORDER):
        pref, value = profile.genes[g], game.genes[g]
        if value.level is None or pref.target < SHARED_USER_MIN or value.level < SHARED_GAME_MIN:
            continue
        ev = best_evidence(game, value.evidence_ids)
        if ev is None:
            continue
        out.append(
            (
                -pref.weight * value.level,
                idx,
                SharedGene(
                    gene=g,
                    user_target=round(pref.target, 2),
                    game_level=value.level,
                    evidence_id=ev.evidence_id,
                    quote=ev.quote,
                    grade=ev.grade,
                    source_type=ev.source_type,
                    source_ref=ev.source_ref,
                ),
            )
        )
    return [s for _, _, s in sorted(out, key=lambda t: (t[0], t[1]))]


def is_recommendable(parts: ScoreParts, shared: list[SharedGene]) -> bool:
    """The evidence gate: strong score AND at least one shared gene backed by grade A or B."""
    return parts.score >= STRONG_SCORE and any(
        s.grade in (EvidenceGrade.A, EvidenceGrade.B) for s in shared
    )


def confidence_for(parts: ScoreParts, shared: list[SharedGene]) -> Confidence:
    grades = {s.grade for s in shared}
    if parts.score >= 0.82 and parts.coverage >= 0.8 and EvidenceGrade.A in grades:
        return Confidence.HIGH
    if parts.score >= STRONG_SCORE and grades & {EvidenceGrade.A, EvidenceGrade.B}:
        return Confidence.MEDIUM
    return Confidence.LOW


def barriers(profile: UserProfile, game: GameRecord, overlap: float) -> list[str]:
    """Plain-language surface turn-offs, deterministic, max 3 (shown as '可能劝退')."""
    out: list[str] = []
    for g in GENE_ORDER:
        pref, value = profile.genes[g], game.genes[g]
        if value.level is None or pref.weight < BARRIER_WEIGHT:
            continue
        gap = value.level - pref.target
        if abs(gap) >= BARRIER_GAP:
            more = "明显高于" if gap > 0 else "明显低于"
            out.append(
                f"{GENES[g].label_zh}（{value.level}/4）{more}你的偏好（{pref.target:.1f}/4）"
            )
    if overlap < TRACK_OVERLAP:
        labels = ", ".join(game.store.tags[:3] or game.store.genres[:3])
        if labels:
            out.append(f"表层类型（{labels}）不在你常玩的范围内")
    unknown = [GENES[g].label_zh for g in GENE_ORDER if game.genes[g].level is None]
    if unknown:
        out.append("证据不足、未参与匹配的维度：" + "、".join(unknown))
    return out[:3]
