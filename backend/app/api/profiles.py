from fastapi import APIRouter
from pydantic import BaseModel

from app.api.dependencies import ServicesDependency
from app.domain.llm import PreferenceParseRequest
from app.domain.profiles import (
    PlayerProfile,
    PreferenceConfirmRequest,
    PreferenceParseResult,
    QuestionnaireSubmission,
)

router = APIRouter(tags=["profiles"])


class ProfileResponse(BaseModel):
    ok: bool = True
    profile: PlayerProfile


class PreferenceParseResponse(BaseModel):
    ok: bool = True
    parsed_preferences: PreferenceParseResult


@router.post("/profiles", response_model=ProfileResponse, status_code=201)
async def create_profile(
    submission: QuestionnaireSubmission,
    services: ServicesDependency,
) -> ProfileResponse:
    return ProfileResponse(profile=services.profile.create(submission))


@router.get("/profiles/{profile_id}", response_model=ProfileResponse)
async def get_profile(profile_id: str, services: ServicesDependency) -> ProfileResponse:
    return ProfileResponse(profile=services.profile.get(profile_id))


@router.post(
    "/profiles/{profile_id}/preferences/parse",
    response_model=PreferenceParseResponse,
)
async def parse_preferences(
    profile_id: str,
    request: PreferenceParseRequest,
    services: ServicesDependency,
) -> PreferenceParseResponse:
    parsed = await services.profile.parse_preferences(profile_id, request)
    return PreferenceParseResponse(parsed_preferences=parsed)


@router.put(
    "/profiles/{profile_id}/preferences/confirm",
    response_model=ProfileResponse,
)
async def confirm_preferences(
    profile_id: str,
    request: PreferenceConfirmRequest,
    services: ServicesDependency,
) -> ProfileResponse:
    return ProfileResponse(
        profile=services.profile.confirm_preferences(profile_id, request)
    )
