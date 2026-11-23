from dataclasses import dataclass
from math import isfinite

from app.domain.catalog import Game
from app.domain.enums import GeneId
from app.domain.profiles import PlayerProfile


@dataclass(frozen=True)
class SimilarityResult:
    similarity: float
    weighted_coverage: float
    compatibility_score: float
    known_gene_ids: tuple[GeneId, ...]


def priority_gene_ids(profile: PlayerProfile) -> tuple[GeneId, GeneId, GeneId]:
    by_id = {item.gene_id: item for item in profile.gene_contributions}
    elevated = [gene_id for gene_id in GeneId if by_id[gene_id].weight == 2]
    ordered = elevated + [gene_id for gene_id in GeneId if gene_id not in elevated]
    return tuple(ordered[:3])  # type: ignore[return-value]


def calculate_similarity(game: Game, profile: PlayerProfile) -> SimilarityResult:
    profile_by_id = {item.gene_id: item for item in profile.gene_contributions}
    game_by_id = {
        item.gene_id: item
        for item in game.genes
        if item.level is not None
    }
    known = tuple(gene_id for gene_id in GeneId if gene_id in game_by_id)
    total_weight = sum(item.weight for item in profile.gene_contributions)
    known_weight = sum(profile_by_id[gene_id].weight for gene_id in known)

    if not known or total_weight <= 0 or known_weight <= 0:
        return SimilarityResult(0.0, 0.0, 0.0, known)

    weighted_distance = sum(
        profile_by_id[gene_id].weight
        * abs(
            profile_by_id[gene_id].final_target
            - int(game_by_id[gene_id].level)
        )
        for gene_id in known
    )
    similarity = 1 - weighted_distance / (4 * known_weight)
    coverage = known_weight / total_weight
    score = similarity * (0.7 + 0.3 * coverage)

    values = (similarity, coverage, score)
    if not all(isfinite(value) for value in values):
        return SimilarityResult(0.0, 0.0, 0.0, known)

    return SimilarityResult(
        similarity=max(0.0, min(1.0, similarity)),
        weighted_coverage=max(0.0, min(1.0, coverage)),
        compatibility_score=max(0.0, min(1.0, score)),
        known_gene_ids=known,
    )


def is_recommendation_eligible(
    game: Game,
    profile: PlayerProfile,
    similarity: SimilarityResult,
    *,
    minimum_coverage: float = 0.70,
) -> bool:
    if similarity.weighted_coverage < minimum_coverage:
        return False
    known = set(similarity.known_gene_ids)
    return sum(gene_id in known for gene_id in priority_gene_ids(profile)) >= 2
