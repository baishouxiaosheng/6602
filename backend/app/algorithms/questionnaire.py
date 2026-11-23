from app.domain.enums import GeneId
from app.domain.genes import GenePreference
from app.domain.profiles import QuestionnaireSubmission


def build_questionnaire_preferences(
    submission: QuestionnaireSubmission,
) -> list[GenePreference]:
    important = set(submission.important_genes)
    return [
        GenePreference(
            gene_id=gene_id,
            target=submission.gene_targets[gene_id],
            weight=2 if gene_id in important else 1,
        )
        for gene_id in GeneId
    ]
