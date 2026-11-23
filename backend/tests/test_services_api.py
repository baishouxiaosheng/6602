from pathlib import Path

import httpx
import pytest

from app.adapters.llm.fake import FakeLLMClient
from app.adapters.steam.schemas import (
    SteamLibrary,
    SteamOwnedGame,
    SteamReview,
    SteamReviewPage,
    SteamStoreGame,
)
from app.api.dependencies import AppServices
from app.domain.catalog import GameGene
from app.domain.enums import (
    CatalogStatus,
    GeneId,
    JobStatus,
    LevelSupport,
    RecommendationStatus,
    SourcePriority,
    TraceStatus,
    Track,
)
from app.domain.evidence import Evidence
from app.domain.llm import (
    OfficialAnnotationResult,
    RankedCandidate,
    RankingResult,
    ReviewSupplementResult,
)
from app.domain.profiles import PreferenceParseResult
from app.domain.recommendations import StartRecommendationRequest
from app.main import create_app
from app.persistence.database import create_database
from app.persistence.repositories import GameRepository
from app.services.catalog import CatalogService
from app.services.jobs import JobService
from app.services.profile import ProfileService
from app.services.recommendation import RecommendationService
from app.services.errors import ServiceError
from app.services.steam_import import SteamImportService
from tests.factories import make_game, make_submission


class StubSteamClient:
    async def resolve_steam_id(self, raw_identity: str) -> str:
        assert raw_identity == "76561198000000000"
        return raw_identity

    async def get_owned_games(self, steam_id: str) -> SteamLibrary:
        return SteamLibrary(
            steam_id=steam_id,
            games=[
                SteamOwnedGame(
                    appid=10,
                    name="Owned Example",
                    playtime_minutes=600,
                )
            ],
        )

    async def get_store_game(self, appid: int) -> SteamStoreGame:
        assert appid == 10
        return SteamStoreGame(
            appid=10,
            name="Owned Example",
            app_type="game",
            short_description="Verified evidence for challenge.",
            detailed_description=" ".join(
                f"Verified evidence for {gene_id.value}." for gene_id in GeneId
            ),
            genres=["rpg"],
            raw_genres=["RPG"],
            categories=["Single-player", "Full Controller Support"],
            platforms=["windows"],
            languages=["english"],
            social_modes=["single_player"],
            price_usd_cents=999,
        )

    async def get_reviews(self, appid: int, **kwargs):  # pragma: no cover
        raise AssertionError("Stage B must not run when Stage A has nine genes.")


@pytest.fixture
def api_app(tmp_path: Path):
    database = create_database(f"sqlite:///{tmp_path / 'api.db'}")
    database.create_schema()

    owned_annotation = make_game(10)
    llm = FakeLLMClient(
        official_result=OfficialAnnotationResult(
            genes=owned_annotation.genes,
            descriptors=[],
        ),
        preference_result=PreferenceParseResult(
            gene_adjustments={GeneId.PACE: -1},
            soft_descriptor_preferences=["pixel_graphics"],
            potential_hard_constraints=["controller_required"],
        ),
        ranking_result=RankingResult(
            same_track=[
                RankedCandidate(
                    appid=20,
                    rank=1,
                    ranking_reason="Strong evidence-grounded gene fit.",
                    matched_gene_ids=[GeneId.CHALLENGE],
                    evidence_ids=["ev_20_challenge"],
                )
            ]
        ),
    )
    steam = StubSteamClient()
    catalog = CatalogService(database, steam, llm)  # type: ignore[arg-type]
    services = AppServices(
        database=database,
        profile=ProfileService(database, llm),
        catalog=catalog,
        steam_import=SteamImportService(  # type: ignore[arg-type]
            database,
            steam,
            catalog,
            annotate_uncatalogued_inventory=True,
        ),
        recommendation=RecommendationService(database, llm),
        jobs=JobService(database),
    )
    with database.session_factory.begin() as session:
        GameRepository(session).upsert(make_game(20))

    app = create_app()
    app.state.services = services
    yield app, llm
    database.engine.dispose()


def questionnaire_payload() -> dict:
    return {
        "display_name": "Demo Player",
        "gene_targets": {gene_id.value: 2 for gene_id in GeneId},
        "important_genes": ["challenge", "strategy", "pace"],
        "familiar_genres": [{"genre": "rpg", "rank": 1, "weight": 3}],
        "hard_filters": {
            "platforms": ["windows"],
            "required_language": "english",
            "social_requirement": "any",
        },
        "additional_preferences": "I prefer a slightly calmer pace.",
    }


@pytest.mark.asyncio
async def test_mock_end_to_end_api_workflow(api_app) -> None:
    app, llm = api_app
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        questionnaire = await client.get("/api/questionnaire")
        assert questionnaire.status_code == 200
        assert len(questionnaire.json()["genes"]) == 9

        created = await client.post("/api/profiles", json=questionnaire_payload())
        assert created.status_code == 201
        profile_id = created.json()["profile"]["profile_id"]

        parsed = await client.post(
            f"/api/profiles/{profile_id}/preferences/parse",
            json={"text": "Please make the experience calmer and use a controller."},
        )
        assert parsed.status_code == 200
        parsed_preferences = parsed.json()["parsed_preferences"]

        confirmed = await client.put(
            f"/api/profiles/{profile_id}/preferences/confirm",
            json={
                "parsed_preferences": parsed_preferences,
                "confirmed_hard_constraints": ["controller_required"],
            },
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["profile"]["hard_filters"]["controller_required"]

        preview = await client.post(
            f"/api/profiles/{profile_id}/steam-import/preview",
            json={"steam_id_or_url": "76561198000000000", "consent": True},
        )
        assert preview.status_code == 200
        preview_body = preview.json()["preview"]
        assert preview_body["steam_id_masked"].endswith("0000")
        assert len(preview_body["games"]) == 1

        imported = await client.post(
            f"/api/profiles/{profile_id}/steam-import/confirm",
            json={
                "preview_token": preview_body["preview_token"],
                "favorite_games": [
                    {"appid": 10, "liked_aspects": ["exploration"]}
                ],
            },
        )
        assert imported.status_code == 202
        import_job_id = imported.json()["job"]["job_id"]
        import_job = await client.get(f"/api/jobs/{import_job_id}")
        assert import_job.json()["job"]["status"] == JobStatus.COMPLETED

        started = await client.post(
            "/api/recommendations",
            json={"profile_id": profile_id, "tracks": [Track.SAME]},
        )
        assert started.status_code == 202
        run_id = started.json()["run_id"]
        recommendation_job = await client.get(
            f"/api/jobs/{started.json()['job']['job_id']}"
        )
        assert recommendation_job.json()["job"]["status"] == "completed"

        result = await client.get(f"/api/recommendations/{run_id}")
        assert result.status_code == 200
        recommendation = result.json()["recommendation"]
        assert recommendation["status"] == "ok"
        assert recommendation["same_track"][0]["appid"] == 20
        assert recommendation["same_track"][0]["ai_rank"] == 1

        profile = await client.get(f"/api/profiles/{profile_id}")
        assert profile.json()["profile"]["owned_appids"] == [10]
        assert profile.json()["profile"]["soft_descriptor_preferences"] == [
            "pixel_graphics"
        ]

        stats = await client.get("/api/catalog/stats")
        assert stats.json()["stats"]["verified"] == 2

    assert llm.calls["parse_preferences"] == 1
    assert llm.calls["annotate_official"] == 1
    assert llm.calls["rank_candidates"] == 1


@pytest.mark.asyncio
async def test_inventory_import_can_defer_uncatalogued_annotation(api_app) -> None:
    app, llm = api_app
    app.state.services.steam_import.annotate_uncatalogued_inventory = False
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        created = await client.post("/api/profiles", json=questionnaire_payload())
        profile_id = created.json()["profile"]["profile_id"]
        preview = await client.post(
            f"/api/profiles/{profile_id}/steam-import/preview",
            json={"steam_id_or_url": "76561198000000000", "consent": True},
        )
        token = preview.json()["preview"]["preview_token"]
        imported = await client.post(
            f"/api/profiles/{profile_id}/steam-import/confirm",
            json={"preview_token": token, "favorite_games": []},
        )
        assert imported.status_code == 202
        job = await client.get(f"/api/jobs/{imported.json()['job']['job_id']}")
        assert job.json()["job"]["status"] == JobStatus.COMPLETED
        profile = (await client.get(f"/api/profiles/{profile_id}")).json()["profile"]

    assert profile["owned_appids"] == [10]
    assert profile["warnings"] == [
        "1 owned games are outside the reviewed catalog; they are excluded from "
        "recommendations but do not influence the gene profile."
    ]
    assert llm.calls["annotate_official"] == 0


@pytest.mark.asyncio
async def test_openapi_contains_all_architecture_endpoints(api_app) -> None:
    app, _ = api_app
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        paths = (await client.get("/openapi.json")).json()["paths"]

    expected = {
        "/api/health",
        "/api/questionnaire",
        "/api/profiles",
        "/api/profiles/{profile_id}",
        "/api/profiles/{profile_id}/preferences/parse",
        "/api/profiles/{profile_id}/preferences/confirm",
        "/api/profiles/{profile_id}/steam-import/preview",
        "/api/profiles/{profile_id}/steam-import/confirm",
        "/api/jobs/{job_id}",
        "/api/recommendations",
        "/api/recommendations/{run_id}",
        "/api/catalog/stats",
        "/api/catalog/games/{appid}",
    }
    assert expected.issubset(paths)


@pytest.mark.asyncio
async def test_catalog_stage_b_accepts_only_three_independent_reviews(
    tmp_path: Path,
) -> None:
    database = create_database(f"sqlite:///{tmp_path / 'stage-b.db'}")
    database.create_schema()
    official_genes = make_game(30).genes[:2]
    reviews = [
        SteamReview(
            review_id=f"review-{index}",
            author_hash=f"author-{index}",
            language="english",
            text=f"The pacing is deliberate and calm example {index}.",
            voted_up=True,
        )
        for index in range(1, 4)
    ]
    review_gene = GameGene(
        gene_id=GeneId.PACE,
        level=1,
        level_support=LevelSupport.SUPPORTED,
        evidence=[
            Evidence(
                evidence_id=f"ev_30_pace_{index}",
                appid=30,
                gene_id=GeneId.PACE,
                source_type="steam_review",
                source_priority=SourcePriority.LOW,
                trace_status=TraceStatus.VERIFIED,
                level_support=LevelSupport.SUPPORTED,
                quote_original=review.text,
                source_locator="steam_review.text",
                source_record_id=review.review_id,
                review_id=review.review_id,
                review_author_hash=review.author_hash,
            )
            for index, review in enumerate(reviews, start=1)
        ],
    )

    class StageBSteam:
        async def get_store_game(self, appid: int) -> SteamStoreGame:
            return SteamStoreGame(
                appid=30,
                name="Stage B Example",
                app_type="game",
                detailed_description=" ".join(
                    gene.evidence[0].quote_original for gene in official_genes
                ),
                genres=["rpg"],
                categories=["Single-player"],
                platforms=["windows"],
                languages=["english"],
                social_modes=["single_player"],
            )

        async def get_reviews(self, appid: int, **kwargs) -> SteamReviewPage:
            return SteamReviewPage(appid=30, reviews=reviews)

    llm = FakeLLMClient(
        official_result=OfficialAnnotationResult(genes=official_genes),
        review_result=ReviewSupplementResult(genes=[review_gene]),
    )
    catalog = CatalogService(database, StageBSteam(), llm)  # type: ignore[arg-type]

    game = await catalog.annotate_game(30)

    assert game.catalog_status == CatalogStatus.PARTIAL
    assert {gene.gene_id for gene in game.genes} == {
        GeneId.CHALLENGE,
        GeneId.STRATEGY,
        GeneId.PACE,
    }
    assert llm.calls["supplement_reviews"] == 1
    database.engine.dispose()


@pytest.mark.asyncio
async def test_no_match_is_success_without_calling_an_llm(tmp_path: Path) -> None:
    database = create_database(f"sqlite:///{tmp_path / 'no-match.db'}")
    database.create_schema()
    profile = ProfileService(database, None).create(make_submission())
    service = RecommendationService(database, None)
    request = StartRecommendationRequest(profile_id=profile.profile_id)
    run = service.create_run(request)

    result_ref = await service.execute(
        run.run_id,
        request,
        lambda step, processed, total: None,
    )

    assert result_ref == run.run_id
    assert service.get(run.run_id).status == RecommendationStatus.NO_MATCH
    database.engine.dispose()


@pytest.mark.asyncio
async def test_invalid_llm_whitelist_result_fails_recommendation_run(
    tmp_path: Path,
) -> None:
    database = create_database(f"sqlite:///{tmp_path / 'invalid-rank.db'}")
    database.create_schema()
    profile = ProfileService(database, None).create(make_submission())
    with database.session_factory.begin() as session:
        GameRepository(session).upsert(make_game(20))
    llm = FakeLLMClient(
        ranking_result=RankingResult(
            same_track=[
                RankedCandidate(
                    appid=999,
                    rank=1,
                    ranking_reason="Invented candidate.",
                    matched_gene_ids=[GeneId.CHALLENGE],
                    evidence_ids=["ev_unknown"],
                )
            ]
        )
    )
    service = RecommendationService(database, llm)
    request = StartRecommendationRequest(profile_id=profile.profile_id)
    run = service.create_run(request)

    with pytest.raises(ServiceError, match="outside the supplied track whitelist"):
        await service.execute(
            run.run_id,
            request,
            lambda step, processed, total: None,
        )

    assert service.get(run.run_id).status == RecommendationStatus.FAILED
    assert llm.calls["rank_candidates"] == 2
    database.engine.dispose()


@pytest.mark.asyncio
async def test_invalid_llm_ranking_is_repaired_once(tmp_path: Path) -> None:
    database = create_database(f"sqlite:///{tmp_path / 'rank-repair.db'}")
    database.create_schema()
    profile = ProfileService(database, None).create(make_submission())
    with database.session_factory.begin() as session:
        GameRepository(session).upsert(make_game(20))

    invalid = RankingResult(
        same_track=[
            RankedCandidate(
                appid=20,
                rank=1,
                ranking_reason="Invalid evidence reference.",
                matched_gene_ids=[GeneId.CHALLENGE],
                evidence_ids=["ev_unknown"],
            )
        ]
    )
    valid = RankingResult(
        same_track=[
            RankedCandidate(
                appid=20,
                rank=1,
                ranking_reason="Evidence-grounded challenge match.",
                matched_gene_ids=[GeneId.CHALLENGE],
                evidence_ids=["ev_20_challenge"],
            )
        ]
    )

    class RepairingLLM(FakeLLMClient):
        async def rank_candidates(self, request):
            self.calls["rank_candidates"] += 1
            if self.calls["rank_candidates"] == 1:
                assert request.repair_feedback is None
                return invalid
            assert "ev_unknown" in request.repair_feedback
            return valid

    llm = RepairingLLM()
    service = RecommendationService(database, llm)
    request = StartRecommendationRequest(profile_id=profile.profile_id)
    run = service.create_run(request)

    await service.execute(run.run_id, request, lambda *_: None)

    result = service.get(run.run_id)
    assert result.status == RecommendationStatus.OK
    assert result.same_track[0].evidence_ids == ["ev_20_challenge"]
    assert llm.calls["rank_candidates"] == 2
    database.engine.dispose()


def test_seed_csv_contract_is_versionable_and_validated(tmp_path: Path) -> None:
    csv_path = tmp_path / "seed_games.csv"
    csv_path.write_text(
        "appid,sampling_bucket,selection_reason,added_by,batch,replacement_for\n"
        "10,rpg,Genre coverage,team-member,batch-1,\n",
        encoding="utf-8",
    )

    entries = CatalogService.load_seed_csv(csv_path)

    assert len(entries) == 1
    assert entries[0].appid == 10
    assert entries[0].sampling_bucket.value == "rpg"


def test_bundled_mvp_seed_csv_has_six_balanced_buckets() -> None:
    path = Path(__file__).parents[1] / "data" / "seed_games.csv"

    entries = CatalogService.load_mvp_seed_csv(path)

    assert len(entries) == 30
    assert len({entry.appid for entry in entries}) == 30
    assert all(
        sum(entry.sampling_bucket.value == bucket for entry in entries) == 5
        for bucket in {"action", "adventure", "rpg", "strategy", "simulation", "casual"}
    )
    obra_dinn = next(entry for entry in entries if entry.appid == 653530)
    assert obra_dinn.replacement_for == 558990
