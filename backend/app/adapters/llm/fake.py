from collections import Counter

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


class FakeLLMClient:
    def __init__(
        self,
        *,
        official_result: OfficialAnnotationResult | None = None,
        review_result: ReviewSupplementResult | None = None,
        preference_result: PreferenceParseResult | None = None,
        ranking_result: RankingResult | None = None,
    ) -> None:
        self.official_result = official_result
        self.review_result = review_result
        self.preference_result = preference_result
        self.ranking_result = ranking_result
        self.calls: Counter[str] = Counter()

    async def annotate_official(
        self, request: OfficialAnnotationRequest
    ) -> OfficialAnnotationResult:
        self.calls["annotate_official"] += 1
        if self.official_result is None:
            raise RuntimeError("Fake official annotation result is not configured.")
        return self.official_result

    async def supplement_reviews(
        self, request: ReviewSupplementRequest
    ) -> ReviewSupplementResult:
        self.calls["supplement_reviews"] += 1
        if self.review_result is None:
            raise RuntimeError("Fake review supplement result is not configured.")
        return self.review_result

    async def parse_preferences(
        self, request: PreferenceParseRequest
    ) -> PreferenceParseResult:
        self.calls["parse_preferences"] += 1
        if self.preference_result is None:
            raise RuntimeError("Fake preference result is not configured.")
        return self.preference_result

    async def rank_candidates(self, request: RankingRequest) -> RankingResult:
        self.calls["rank_candidates"] += 1
        if self.ranking_result is None:
            raise RuntimeError("Fake ranking result is not configured.")
        return self.ranking_result
