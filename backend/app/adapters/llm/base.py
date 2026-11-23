from typing import Protocol

from app.domain.llm import (
    OfficialAnnotationRequest,
    OfficialAnnotationResult,
    PreferenceParseRequest,
    RankingRequest,
    RankingResult,
    ReviewSupplementRequest,
    ReviewSupplementResult,
)
from app.domain.profiles import PreferenceParseResult


class LLMClient(Protocol):
    async def annotate_official(
        self, request: OfficialAnnotationRequest
    ) -> OfficialAnnotationResult: ...

    async def supplement_reviews(
        self, request: ReviewSupplementRequest
    ) -> ReviewSupplementResult: ...

    async def parse_preferences(
        self, request: PreferenceParseRequest
    ) -> PreferenceParseResult: ...

    async def rank_candidates(self, request: RankingRequest) -> RankingResult: ...
