from pydantic import BaseModel, Field

from app.algorithms.questionnaire import build_questionnaire_preferences
from app.domain.enums import GeneId
from app.domain.genes import GeneContribution
from app.domain.profiles import (
    PlayerProfile,
    PreferenceParseResult,
    QuestionnaireSubmission,
)


class LibraryGeneSignal(BaseModel):
    directions: dict[GeneId, int] = Field(default_factory=dict)
    source_appids: dict[GeneId, list[int]] = Field(default_factory=dict)

    def direction_for(self, gene_id: GeneId) -> int:
        value = self.directions.get(gene_id, 0)
        return max(-1, min(1, value))


def _clamp_gene_level(value: int) -> int:
    return max(0, min(4, value))


def fuse_profile(
    *,
    profile_id: str,
    submission: QuestionnaireSubmission,
    library_signal: LibraryGeneSignal | None = None,
    parsed_preferences: PreferenceParseResult | None = None,
    confirmed_hard_filters=None,
    owned_appids: set[int] | None = None,
    warnings: list[str] | None = None,
) -> PlayerProfile:
    library_signal = library_signal or LibraryGeneSignal()
    parsed_preferences = parsed_preferences or PreferenceParseResult()
    preferences = build_questionnaire_preferences(submission)
    contributions: list[GeneContribution] = []

    for preference in preferences:
        gene_id = preference.gene_id
        library_adjustment = library_signal.direction_for(gene_id)
        after_library = _clamp_gene_level(preference.target + library_adjustment)
        text_adjustment = parsed_preferences.gene_adjustments.get(gene_id, 0)
        final_target = _clamp_gene_level(after_library + text_adjustment)

        sources = ["questionnaire"]
        for appid in library_signal.source_appids.get(gene_id, []):
            sources.append(f"owned_game:{appid}")
        if text_adjustment:
            sources.append("free_text")

        contributions.append(
            GeneContribution(
                gene_id=gene_id,
                questionnaire_target=preference.target,
                library_adjustment=library_adjustment,
                text_adjustment=text_adjustment,
                final_target=final_target,
                weight=preference.weight,
                sources=sources,
            )
        )

    return PlayerProfile(
        profile_id=profile_id,
        display_name=submission.display_name,
        gene_contributions=contributions,
        familiar_genres=submission.familiar_genres,
        hard_filters=confirmed_hard_filters or submission.hard_filters,
        soft_descriptor_preferences=parsed_preferences.soft_descriptor_preferences,
        owned_appids=owned_appids or set(),
        free_text=submission.additional_preferences,
        warnings=warnings or [],
    )
