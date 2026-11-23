import argparse
import asyncio
from typing import Any

import httpx

from app.api.dependencies import build_services
from app.config import get_settings
from app.main import create_app


FAVORITE_ASPECTS = {
    413150: ["creation", "exploration", "pace"],
    646570: ["strategy", "challenge", "creation"],
    1245620: ["challenge", "exploration", "immersion"],
}


def _questionnaire() -> dict[str, Any]:
    return {
        "display_name": "Live Demo Player",
        "gene_targets": {
            "challenge": 3,
            "strategy": 3,
            "pace": 2,
            "progression": 3,
            "exploration": 3,
            "creation": 2,
            "narrative": 3,
            "immersion": 3,
            "social": 1,
        },
        "important_genes": ["challenge", "strategy", "exploration"],
        "familiar_genres": [
            {"genre": "strategy", "rank": 1, "weight": 3},
            {"genre": "rpg", "rank": 2, "weight": 2},
            {"genre": "simulation", "rank": 3, "weight": 1},
        ],
        "hard_filters": {
            "platforms": ["windows"],
            "required_language": "english",
            "social_requirement": "any",
            "controller_required": False,
            "exclude_owned": True,
        },
        "additional_preferences": (
            "I want challenging strategic games with meaningful exploration, "
            "but I would rather avoid excessively frantic pacing."
        ),
    }


def _require(response: httpx.Response, expected: int = 200) -> dict[str, Any]:
    if response.status_code != expected:
        raise RuntimeError(
            f"{response.request.method} {response.request.url.path} returned "
            f"HTTP {response.status_code}: {response.text[:500]}"
        )
    return response.json()


async def run(steam_id: str | None, resume_profile_id: str | None = None) -> None:
    settings = get_settings()
    services = build_services(settings)
    app = create_app()
    app.state.services = services
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://live-e2e.local",
            timeout=420,
        ) as client:
            if resume_profile_id:
                print("[resume] Loading the imported live profile...", flush=True)
                profile = _require(
                    await client.get(f"/api/profiles/{resume_profile_id}")
                )["profile"]
                print("[resume] Ranking candidates with Qwen (call 2/2)...", flush=True)
                started = _require(
                    await client.post(
                        "/api/recommendations",
                        json={
                            "profile_id": resume_profile_id,
                            "tracks": ["same_track", "cross_track"],
                        },
                    ),
                    202,
                )
                rank_job = _require(
                    await client.get(f"/api/jobs/{started['job']['job_id']}")
                )["job"]
                if rank_job["status"] != "completed":
                    raise RuntimeError(f"Recommendation failed: {rank_job}")
                result = _require(
                    await client.get(f"/api/recommendations/{started['run_id']}")
                )["recommendation"]
                owned = set(profile["owned_appids"])
                recommendations = result["same_track"] + result["cross_track"]
                if any(item["appid"] in owned for item in recommendations):
                    raise RuntimeError("An owned game appeared in the recommendations.")
                if any(not item["evidence_ids"] for item in recommendations):
                    raise RuntimeError("A recommendation is missing evidence references.")
                print("[resume] Live E2E completed.", flush=True)
                print(f"profile_id={resume_profile_id}")
                print(f"library_games={len(profile['owned_appids'])}")
                print(f"status={result['status']}")
                print(f"warning_count={len(profile['warnings'])}")
                for track in ("same_track", "cross_track"):
                    for item in result[track]:
                        print(
                            f"{track} rank={item['ai_rank']} appid={item['appid']} "
                            f"name={item['name']} score={item['compatibility_score']:.3f}"
                        )
                return

            if steam_id is None:
                raise RuntimeError("--steam-id is required for a new live run.")
            print("[1/8] Checking API and curated catalog...", flush=True)
            _require(await client.get("/api/health"))
            stats = _require(await client.get("/api/catalog/stats"))["stats"]
            if stats["total"] != 30 or stats["verified"] < 29:
                raise RuntimeError(f"Curated catalog is not ready: {stats}")

            print("[2/8] Creating questionnaire profile...", flush=True)
            created = _require(
                await client.post("/api/profiles", json=_questionnaire()), 201
            )
            profile_id = created["profile"]["profile_id"]

            print("[3/8] Parsing free-text preference with Qwen (call 1/2)...", flush=True)
            parsed = _require(
                await client.post(
                    f"/api/profiles/{profile_id}/preferences/parse",
                    json={"text": _questionnaire()["additional_preferences"]},
                )
            )["parsed_preferences"]
            _require(
                await client.put(
                    f"/api/profiles/{profile_id}/preferences/confirm",
                    json={
                        "parsed_preferences": parsed,
                        "confirmed_hard_constraints": [],
                    },
                )
            )

            print("[4/8] Reading the public Steam library...", flush=True)
            preview = _require(
                await client.post(
                    f"/api/profiles/{profile_id}/steam-import/preview",
                    json={"steam_id_or_url": steam_id, "consent": True},
                )
            )["preview"]
            games_by_appid = {item["appid"]: item for item in preview["games"]}
            favorites = [
                {"appid": appid, "liked_aspects": aspects}
                for appid, aspects in FAVORITE_ASPECTS.items()
                if appid in games_by_appid
            ]

            print(
                f"[5/8] Importing {len(preview['games'])} owned games with "
                f"{len(favorites)} reviewed favorites (no catalog annotation calls)...",
                flush=True,
            )
            imported = _require(
                await client.post(
                    f"/api/profiles/{profile_id}/steam-import/confirm",
                    json={
                        "preview_token": preview["preview_token"],
                        "favorite_games": favorites,
                    },
                ),
                202,
            )
            import_job = _require(
                await client.get(f"/api/jobs/{imported['job']['job_id']}")
            )["job"]
            if import_job["status"] != "completed":
                raise RuntimeError(f"Steam import failed: {import_job}")

            profile = _require(
                await client.get(f"/api/profiles/{profile_id}")
            )["profile"]
            if len(profile["owned_appids"]) != len(preview["games"]):
                raise RuntimeError("The imported owned-game exclusion set is incomplete.")

            print("[6/8] Retrieving candidates and ranking with Qwen (call 2/2)...", flush=True)
            started = _require(
                await client.post(
                    "/api/recommendations",
                    json={
                        "profile_id": profile_id,
                        "tracks": ["same_track", "cross_track"],
                    },
                ),
                202,
            )
            rank_job = _require(
                await client.get(f"/api/jobs/{started['job']['job_id']}")
            )["job"]
            if rank_job["status"] != "completed":
                raise RuntimeError(f"Recommendation failed: {rank_job}")

            print("[7/8] Validating owned-game exclusion and evidence references...", flush=True)
            result = _require(
                await client.get(f"/api/recommendations/{started['run_id']}")
            )["recommendation"]
            owned = set(profile["owned_appids"])
            recommendations = result["same_track"] + result["cross_track"]
            if any(item["appid"] in owned for item in recommendations):
                raise RuntimeError("An owned game appeared in the recommendations.")
            if any(not item["evidence_ids"] for item in recommendations):
                raise RuntimeError("A recommendation is missing evidence references.")

            print("[8/8] Live E2E completed.", flush=True)
            print(f"profile_id={profile_id}")
            print(f"library_games={len(preview['games'])}")
            print(f"favorites={','.join(str(item['appid']) for item in favorites)}")
            print(f"status={result['status']}")
            print(f"warning_count={len(profile['warnings'])}")
            for track in ("same_track", "cross_track"):
                for item in result[track]:
                    print(
                        f"{track} rank={item['ai_rank']} appid={item['appid']} "
                        f"name={item['name']} score={item['compatibility_score']:.3f}"
                    )
    finally:
        if services.http_client is not None:
            await services.http_client.aclose()
        services.database.engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the explicit live Steam + Qwen end-to-end smoke test."
    )
    parser.add_argument("--steam-id", help="Public 17-digit SteamID64")
    parser.add_argument(
        "--resume-profile-id",
        help="Resume at candidate ranking using an already imported live profile.",
    )
    args = parser.parse_args()
    if not args.steam_id and not args.resume_profile_id:
        parser.error("provide --steam-id or --resume-profile-id")
    asyncio.run(run(args.steam_id, args.resume_profile_id))


if __name__ == "__main__":
    main()
