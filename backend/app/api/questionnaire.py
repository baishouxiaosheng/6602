from fastapi import APIRouter
from pydantic import BaseModel

from app.domain.enums import CanonicalGenre, GeneId

router = APIRouter(tags=["questionnaire"])


GENE_TEXT = {
    GeneId.CHALLENGE: ("Mechanical Challenge", "Execution, practice, and failure recovery."),
    GeneId.STRATEGY: ("Strategic Depth", "Planning, optimization, and trade-offs."),
    GeneId.PACE: ("Pace Intensity", "Real-time pressure and action density."),
    GeneId.PROGRESSION: ("Progression", "Levels, gear, unlocks, and long-term growth."),
    GeneId.EXPLORATION: ("Exploration", "Discovery, secrets, and unknown spaces."),
    GeneId.CREATION: ("Creation", "Building, design, and player expression."),
    GeneId.NARRATIVE: ("Narrative", "Story, characters, and dialogue."),
    GeneId.IMMERSION: ("Immersion", "Atmosphere and world coherence."),
    GeneId.SOCIAL: ("Social Dependency", "Dependence on cooperation or competition."),
}


class QuestionnaireGene(BaseModel):
    gene_id: GeneId
    label: str
    description: str


class QuestionnaireResponse(BaseModel):
    version: str = "v1"
    genes: list[QuestionnaireGene]
    scale: dict[int, str]
    canonical_genres: list[CanonicalGenre]
    max_important_genes: int = 3
    max_familiar_genres: int = 3


@router.get("/questionnaire", response_model=QuestionnaireResponse)
async def questionnaire() -> QuestionnaireResponse:
    return QuestionnaireResponse(
        genes=[
            QuestionnaireGene(
                gene_id=gene_id,
                label=GENE_TEXT[gene_id][0],
                description=GENE_TEXT[gene_id][1],
            )
            for gene_id in GeneId
        ],
        scale={
            0: "Not part of the desired experience",
            1: "Minor or optional",
            2: "Present but not central",
            3: "One of the main attractions",
            4: "Core to the experience",
        },
        canonical_genres=list(CanonicalGenre),
    )
