from copy import deepcopy
from uuid import uuid4

from app.adapters.llm.base import LLMClient
from app.algorithms.profile_fusion import LibraryGeneSignal, fuse_profile
from app.domain.llm import PreferenceParseRequest
from app.domain.profiles import (
    PlayerProfile,
    PreferenceConfirmRequest,
    PreferenceParseResult,
    QuestionnaireSubmission,
)
from app.persistence.database import Database
from app.persistence.repositories import ProfileRepository
from app.services.errors import ConfigurationUnavailable, NotFoundError, ServiceError


ALLOWED_HARD_CONSTRAINTS = {"controller_required"}


def parsed_preferences_from_profile(profile: PlayerProfile) -> PreferenceParseResult:
    return PreferenceParseResult(
        gene_adjustments={
            item.gene_id: item.text_adjustment
            for item in profile.gene_contributions
            if item.text_adjustment
        },
        soft_descriptor_preferences=profile.soft_descriptor_preferences,
    )


def library_signal_from_profile(profile: PlayerProfile) -> LibraryGeneSignal:
    return LibraryGeneSignal(
        directions={
            item.gene_id: item.library_adjustment
            for item in profile.gene_contributions
            if item.library_adjustment
        },
        source_appids={
            item.gene_id: [
                int(source.split(":", 1)[1])
                for source in item.sources
                if source.startswith("owned_game:")
            ]
            for item in profile.gene_contributions
        },
    )


class ProfileService:
    def __init__(self, database: Database, llm: LLMClient | None) -> None:
        self.database = database
        self.llm = llm

    def create(self, submission: QuestionnaireSubmission) -> PlayerProfile:
        profile_id = f"p_{uuid4().hex}"
        profile = fuse_profile(profile_id=profile_id, submission=submission)
        with self.database.session_factory.begin() as session:
            ProfileRepository(session).save(profile, questionnaire=submission)
        return profile

    def get(self, profile_id: str) -> PlayerProfile:
        with self.database.session_factory() as session:
            profile = ProfileRepository(session).get(profile_id)
        if profile is None:
            raise NotFoundError("Profile", profile_id)
        return profile

    async def parse_preferences(
        self, profile_id: str, request: PreferenceParseRequest
    ) -> PreferenceParseResult:
        self.get(profile_id)
        if self.llm is None:
            raise ConfigurationUnavailable("Qwen is not configured.")
        parsed = await self.llm.parse_preferences(request)
        allowed = [
            item
            for item in parsed.potential_hard_constraints
            if item in ALLOWED_HARD_CONSTRAINTS
        ]
        unsupported = list(parsed.unsupported_requests)
        unsupported.extend(
            item
            for item in parsed.potential_hard_constraints
            if item not in ALLOWED_HARD_CONSTRAINTS and item not in unsupported
        )
        return parsed.model_copy(
            update={
                "potential_hard_constraints": allowed,
                "unsupported_requests": unsupported,
            }
        )

    def confirm_preferences(
        self, profile_id: str, request: PreferenceConfirmRequest
    ) -> PlayerProfile:
        unknown = set(request.confirmed_hard_constraints) - ALLOWED_HARD_CONSTRAINTS
        if unknown:
            raise ServiceError(
                "unsupported_constraint",
                f"Unsupported hard constraint: {sorted(unknown)[0]}.",
            )

        current = self.get(profile_id)
        with self.database.session_factory() as session:
            submission = ProfileRepository(session).get_questionnaire(profile_id)
        if submission is None:
            raise ServiceError("profile_corrupt", "Profile questionnaire is unavailable.")

        hard_filters = deepcopy(current.hard_filters)
        if "controller_required" in request.confirmed_hard_constraints:
            hard_filters.controller_required = True

        profile = fuse_profile(
            profile_id=profile_id,
            submission=submission,
            library_signal=library_signal_from_profile(current),
            parsed_preferences=request.parsed_preferences,
            confirmed_hard_filters=hard_filters,
            owned_appids=current.owned_appids,
            warnings=current.warnings,
        )
        with self.database.session_factory.begin() as session:
            ProfileRepository(session).save(profile)
        return profile
