from app.domain.catalog import Game, GameGene
from app.domain.enums import GeneId, SourcePriority, TraceStatus, Track
from app.domain.evidence import Evidence
from app.domain.profiles import PlayerProfile
from app.domain.recommendations import CandidateFact, CandidateGeneFact


_SOURCE_ORDER = {
    SourcePriority.HIGH: 0,
    SourcePriority.MEDIUM: 1,
    SourcePriority.LOW: 2,
}


def _best_evidence(gene: GameGene) -> Evidence | None:
    valid = [
        item
        for item in gene.evidence
        if item.trace_status == TraceStatus.VERIFIED
        and item.level_support.value == "supported"
    ]
    if not valid:
        return None
    return sorted(
        valid,
        key=lambda item: (_SOURCE_ORDER[item.source_priority], item.evidence_id),
    )[0]


def _gene_fact(
    gene: GameGene,
    profile_by_id,
) -> CandidateGeneFact | None:
    if gene.level is None:
        return None
    evidence = _best_evidence(gene)
    if evidence is None:
        return None
    preference = profile_by_id[gene.gene_id]
    return CandidateGeneFact(
        gene_id=gene.gene_id,
        user_target=preference.final_target,
        game_level=gene.level,
        user_weight=preference.weight,
        evidence_id=evidence.evidence_id,
        evidence_quote=evidence.quote_original,
        source_priority=evidence.source_priority,
    )


def build_candidate_fact(
    game: Game,
    profile: PlayerProfile,
    *,
    track: Track,
    algorithm_rank: int,
    compatibility_score: float,
) -> CandidateFact:
    profile_by_id = {item.gene_id: item for item in profile.gene_contributions}
    facts: list[CandidateGeneFact] = []
    for gene in game.genes:
        fact = _gene_fact(gene, profile_by_id)
        if fact is not None:
            facts.append(fact)

    gene_order = {gene_id: index for index, gene_id in enumerate(GeneId)}
    matching = [
        fact
        for fact in facts
        if abs(fact.user_target - fact.game_level) <= 1
    ]
    matching.sort(
        key=lambda fact: (
            -fact.user_weight,
            abs(fact.user_target - fact.game_level),
            _SOURCE_ORDER[fact.source_priority],
            gene_order[fact.gene_id],
        )
    )

    differences = [
        fact
        for fact in facts
        if abs(fact.user_target - fact.game_level) > 1
    ]
    differences.sort(
        key=lambda fact: (
            -fact.user_weight,
            -abs(fact.user_target - fact.game_level),
            _SOURCE_ORDER[fact.source_priority],
            gene_order[fact.gene_id],
        )
    )

    return CandidateFact(
        appid=game.appid,
        name=game.name,
        track=track,
        algorithm_rank=algorithm_rank,
        compatibility_score=compatibility_score,
        matching_genes=matching[:3],
        difference_genes=differences[:2],
        descriptors=[item.descriptor_id for item in game.descriptors if item.value],
    )
