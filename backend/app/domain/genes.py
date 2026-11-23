from typing import Annotated

from pydantic import BaseModel, Field

from app.domain.enums import GeneId

GeneLevel = Annotated[int, Field(ge=0, le=4)]
GeneWeight = Annotated[int, Field(ge=1, le=2)]


class GenePreference(BaseModel):
    gene_id: GeneId
    target: GeneLevel
    weight: GeneWeight = 1


class GeneContribution(BaseModel):
    gene_id: GeneId
    questionnaire_target: GeneLevel
    library_adjustment: Annotated[int, Field(ge=-1, le=1)] = 0
    text_adjustment: Annotated[int, Field(ge=-1, le=1)] = 0
    final_target: GeneLevel
    weight: GeneWeight = 1
    sources: list[str] = Field(default_factory=list)
