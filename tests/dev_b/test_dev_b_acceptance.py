"""Acceptance tests for Dev B. Skipped while the stub raises NotImplementedError.
Everything runs offline on the synthetic fixture catalog with FakeLLM / FakeSteamLibraryClient.
If a test contradicts docs/, the docs win: tell the designer instead of bending code."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gamegene.contracts import (
    Explanation,
    GeneId,
    HardFilters,
    InvalidInput,
    NotFound,
    OwnedGame,
    Platform,
    ProfileRequest,
    Reason,
    RecommendRequest,
    RunStatus,
    SocialMode,
    SteamProfilePrivate,
    StorageError,
    Track,
    UpstreamError,
)
from gamegene.llm import FakeLLM
from gamegene.profile import builder, library
from gamegene.recommend import explainer, filters, pipeline, scoring
from gamegene.steam.library import FakeSteamLibraryClient
from gamegene.storage import Kind
from tests.conftest import PERSONAS, make_profile

pytestmark = pytest.mark.dev_b
HADES, DEAD_CELLS, HOLLOW, CELESTE, TERRARIA, DISCO, FACTORIO = (
    1145360,
    588650,
    367520,
    504230,
    105600,
    632470,
    427520,
)
ID64 = "76561198000000001"


def _names(recs):
    return [r.name for r in recs]


# ------------------------------------------------------------------ B1 library blend
def test_b1_blend_library(catalog):
    p = make_profile("roguelike")
    owned = [
        OwnedGame(appid=FACTORIO, playtime_minutes=600),
        OwnedGame(appid=HADES, playtime_minutes=30),
        OwnedGame(appid=5, playtime_minutes=9999),
    ]
    games = {g.appid: g for g in catalog.list_games()}
    prefs, tags, matched = library.blend_library(p.genes, p.familiar_tags, owned, games)
    assert matched == [FACTORIO]  # Hades under 60 minutes, appid 5 not in the catalog
    assert (prefs[GeneId.STRATEGY].target, prefs[GeneId.STRATEGY].weight) == (
        1.3,
        0.61,
    )  # 0.9*1 + 0.1*4
    assert prefs[GeneId.CHALLENGE].target == 3.8  # 0.9*4 + 0.1*2
    assert tags["automation"] == 1.0 and tags["strategy"] == 1.0 and tags["roguelike"] == 1.0


def test_b1_no_match_changes_nothing(catalog):
    p = make_profile("roguelike")
    prefs, tags, matched = library.blend_library(p.genes, p.familiar_tags, [OwnedGame(appid=5)], {})
    assert (prefs, tags, matched) == (p.genes, p.familiar_tags, [])


# ------------------------------------------------------------------ B2 profile builder
def _request(**kw) -> ProfileRequest:
    return ProfileRequest(**{"display_name": "Ann", "answers": PERSONAS["roguelike"], **kw})


def test_b2_invalid_input_stops_before_steam(store, catalog):
    steam = FakeSteamLibraryClient()
    bad = _request(display_name="   ", answers={"q01_failure": ["a"]}, steam_id_or_url=ID64)
    with pytest.raises(InvalidInput) as info:
        builder.build_profile(bad, store=store, catalog=catalog, steam=steam)
    assert len(info.value.details["problems"]) >= 2  # name AND answers reported together
    assert steam.calls == 0 and store.list_ids(Kind.PROFILE) == []


def test_b2_create_then_revise(store, catalog):
    profile, warnings = builder.build_profile(_request(), store=store, catalog=catalog, steam=None)
    assert warnings == [] and profile.profile_id.startswith("p-") and len(profile.profile_id) == 10
    assert store.get_record(Kind.PROFILE, profile.profile_id).revision == 1
    revised, _ = builder.build_profile(
        _request(profile_id=profile.profile_id, display_name="Ann v2", answers=PERSONAS["builder"]),
        store=store,
        catalog=catalog,
        steam=None,
    )
    assert revised.profile_id == profile.profile_id and revised.display_name == "Ann v2"
    assert store.get_record(Kind.PROFILE, profile.profile_id).revision == 2
    assert store.get(Kind.PROFILE, profile.profile_id, revision=1).display_name == "Ann"
    with pytest.raises(NotFound):
        builder.build_profile(
            _request(profile_id="p-00000000"), store=store, catalog=catalog, steam=None
        )


def test_b2_library_import(store, catalog):
    steam = FakeSteamLibraryClient(
        {
            ID64: [
                OwnedGame(appid=FACTORIO, playtime_minutes=600),
                OwnedGame(appid=5, playtime_minutes=10),
            ]
        }
    )
    profile, warnings = builder.build_profile(
        _request(steam_id_or_url=ID64), store=store, catalog=catalog, steam=steam
    )
    assert warnings == [] and profile.owned_appids == [FACTORIO, 5]
    assert profile.sources.steam_id == ID64 and profile.sources.library_matched_appids == [FACTORIO]
    assert profile.genes[GeneId.STRATEGY].target == 1.3


@pytest.mark.parametrize("failure", [SteamProfilePrivate("private"), UpstreamError("steam down")])
def test_b2_steam_failure_degrades_to_interview_only(store, catalog, failure):
    steam = FakeSteamLibraryClient(error=failure)
    profile, warnings = builder.build_profile(
        _request(steam_id_or_url=ID64), store=store, catalog=catalog, steam=steam
    )
    assert len(warnings) == 1 and profile.owned_appids == []
    assert profile.genes[GeneId.STRATEGY].target == 1.0  # interview only
    assert store.exists(Kind.PROFILE, profile.profile_id)
    assert steam.calls == (3 if failure.retryable else 1)  # bounded retry only for retryable errors


# ------------------------------------------------------------------ B3 hard filters
@pytest.mark.parametrize(
    ("filters_kw", "owned", "expected"),
    [
        ({}, [], {"not_verified": 1}),
        ({}, [HADES], {"not_verified": 1, "excluded": 1}),
        ({"exclude_owned": False}, [HADES], {"not_verified": 1}),
        ({"excluded_appids": [HADES, DEAD_CELLS]}, [], {"not_verified": 1, "excluded": 2}),
        ({"excluded_tags": ["roguelike"]}, [], {"not_verified": 1, "excluded_tag": 3}),
        ({"platforms": [Platform.MAC]}, [], {"not_verified": 1, "platform": 2}),
        ({"social_modes": [SocialMode.COOP]}, [], {"not_verified": 1, "social_mode": 10}),
        ({"required_language": "japanese"}, [], {"not_verified": 1, "language": 16}),
        ({"max_price_cents": 1000}, [], {"not_verified": 1, "price": 14}),
    ],
)
def test_b3_drop_reasons(catalog, filters_kw, owned, expected):
    p = make_profile("roguelike", filters=HardFilters(**filters_kw), owned_appids=owned)
    kept, drops = filters.apply_hard_filters(p, catalog.list_games())
    assert drops == expected
    assert len(kept) == 17 - sum(expected.values())


def test_b3_first_reason_wins_and_order_is_kept(catalog):
    p = make_profile(
        "roguelike", filters=HardFilters(platforms=[Platform.MAC], max_price_cents=1000)
    )
    kept, drops = filters.apply_hard_filters(p, catalog.list_games())
    assert drops == {"not_verified": 1, "platform": 2, "price": 12}
    assert _names(kept) == ["Portal 2", "Terraria"]


# ------------------------------------------------------------------ B4 explainer
def _shared(catalog, appid=HADES):
    p = make_profile("roguelike")
    game = catalog.get_game(appid)
    return p, game, scoring.shared_genes(p, game)


def test_b4_template_never_fails(catalog):
    _, game, shared = _shared(catalog)
    exp = explainer.template_explanation(game, shared, mismatch="差异")
    assert exp.generated_by == "template" and len(exp.reasons) == 3 and exp.mismatch == "差异"
    assert explainer.check_explanation(exp, shared) == []
    assert explainer.template_explanation(game, []).reasons == []


def test_b4_check_explanation_rules(catalog):
    _, _, shared = _shared(catalog)
    good = Reason(gene=shared[0].gene, text="ok", evidence_id=shared[0].evidence_id)

    def exp(reasons):
        return Explanation(headline="h", reasons=reasons, generated_by="llm")

    assert explainer.check_explanation(exp([good]), shared) == []
    assert explainer.check_explanation(exp([]), shared)  # no reason
    assert explainer.check_explanation(exp([good, good]), shared)  # same gene twice
    assert explainer.check_explanation(
        exp([good.model_copy(update={"evidence_id": "ev-made-up"})]), shared
    )
    assert explainer.check_explanation(
        exp([good.model_copy(update={"gene": GeneId.SOCIAL})]), shared
    )


def test_b4_explain_accepts_valid_and_falls_back_otherwise(catalog):
    p, game, shared = _shared(catalog)
    ok = {
        "headline": "快节奏动作",
        "generated_by": "template",
        "reasons": [
            {"gene": shared[0].gene.value, "text": "t", "evidence_id": shared[0].evidence_id}
        ],
    }
    exp, fell_back = explainer.explain(FakeLLM(script=[ok]), p, game, Track.SAME, shared)
    assert (exp.generated_by, fell_back, exp.headline) == ("llm", False, "快节奏动作")
    invented = {**ok, "reasons": [{**ok["reasons"][0], "evidence_id": "ev-made-up"}]}
    for script in ([invented], ["Sure! Here is my explanation"], [UpstreamError("llm down")]):
        llm = FakeLLM(script=script)
        exp, fell_back = explainer.explain(llm, p, game, Track.SAME, shared)
        assert (exp.generated_by, fell_back) == ("template", True) and llm.calls == 1


# ------------------------------------------------------------------ B5 pipeline branches
def _saved_profile(store, persona="roguelike", **overrides):
    p = make_profile(persona, **overrides)
    store.put(Kind.PROFILE, p.profile_id, p)
    return p


def _run(store, catalog, llm=None, **req):
    llm = llm if llm is not None else FakeLLM()  # empty script -> every explanation falls back
    request = RecommendRequest(**{"profile_id": "p-roguelike", **req})
    return pipeline.recommend(request, store=store, catalog=catalog, llm=llm), llm


def test_b5_branch_e_ok_both_tracks(store, catalog):
    _saved_profile(store)
    run, llm = _run(store, catalog)
    assert run.status is RunStatus.OK and run.profile_revision == 1
    assert _names(run.same_track) == ["Dead Cells", "Hades"]
    assert _names(run.cross_track) == ["Hollow Knight", "Celeste"]
    assert (run.candidates_total, run.candidates_after_filters, run.filter_drops) == (
        17,
        16,
        {"not_verified": 1},
    )
    assert (
        run.llm.calls == 4 and run.llm.fallbacks == 4 and llm.calls == 4
    )  # only shown games are explained
    assert all(r.explanation.generated_by == "template" for r in run.same_track + run.cross_track)
    assert [t.step for t in run.trace][:2] == ["validate", "route"] and run.trace[-1].step == "save"
    assert store.get(Kind.RUN, run.run_id) == run


def test_b5_modes_and_top_k(store, catalog):
    _saved_profile(store)
    run, llm = _run(store, catalog, mode="same_track", top_k=1)
    assert _names(run.same_track) == ["Dead Cells"] and run.cross_track == [] and llm.calls == 1
    run, _ = _run(store, catalog, mode="cross_track")
    assert run.same_track == [] and _names(run.cross_track) == ["Hollow Knight", "Celeste"]


def test_b5_model_answer_changes_the_stored_result(store, catalog):
    _saved_profile(store)
    answer = {
        "headline": "高难度动作循环",
        "generated_by": "llm",
        "reasons": [
            {
                "gene": "challenge",
                "text": "你想要高挑战，本作正是如此。",
                "evidence_id": "ev-challenge-1",
            }
        ],
    }
    run, llm = _run(store, catalog, llm=FakeLLM(script=[answer]), mode="same_track", top_k=1)
    rec = store.get(Kind.RUN, run.run_id).same_track[0]
    assert rec.explanation.generated_by == "llm" and rec.explanation.headline == "高难度动作循环"
    assert (run.llm.calls, run.llm.fallbacks) == (1, 0)


def test_b5_branch_a_duplicate_request_id(store, catalog):
    _saved_profile(store)
    first, llm = _run(store, catalog, request_id="req-001")
    second, _ = _run(store, catalog, llm=llm, request_id="req-001")
    assert second.run_id == first.run_id and llm.calls == 4 and len(store.list_ids(Kind.RUN)) == 1


def test_b5_branch_b_unknown_profile(store, catalog):
    llm = FakeLLM()
    with pytest.raises(NotFound):
        pipeline.recommend(
            RecommendRequest(profile_id="p-missing"), store=store, catalog=catalog, llm=llm
        )
    assert llm.calls == 0 and store.list_ids(Kind.RUN) == []


def test_b5_branch_c_unsupported_mode(store, catalog):
    _saved_profile(store)
    run, llm = _run(store, catalog, mode="surprise_me")
    assert run.status is RunStatus.NO_MATCH and "surprise_me" in run.message and llm.calls == 0
    assert run.candidates_total == 0 and store.exists(Kind.RUN, run.run_id)


def test_b5_branch_d_filters_remove_everything(store, catalog):
    _saved_profile(store, filters=HardFilters(required_language="japanese"))
    run, llm = _run(store, catalog)
    assert run.status is RunStatus.NO_MATCH and llm.calls == 0
    assert (
        run.filter_drops == {"not_verified": 1, "language": 16}
        and run.candidates_after_filters == 0
    )


def test_b5_branch_f_closest_only(store, catalog):
    _saved_profile(store, filters=HardFilters(excluded_appids=[HADES, DEAD_CELLS, HOLLOW, CELESTE]))
    run, _ = _run(store, catalog)
    assert run.status is RunStatus.CLOSEST_ONLY and run.same_track == [] and run.cross_track == []
    assert run.closest.name == "Terraria" and run.closest.explanation.mismatch


def test_b5_branch_g_nothing_close_enough(store, catalog):
    everything_but_disco = [g.appid for g in catalog.list_games() if g.appid != DISCO]
    _saved_profile(store, filters=HardFilters(excluded_appids=everything_but_disco))
    run, llm = _run(store, catalog)
    assert run.status is RunStatus.NO_MATCH and run.closest is None and llm.calls == 0
    assert run.candidates_after_filters == 1


def test_b5_branch_h_storage_failure_is_saved_as_error_run(store):
    _saved_profile(store)

    class BrokenCatalog:
        source = "store"

        def list_games(self):
            raise StorageError("catalog/620.json is unreadable")

        def get_game(self, appid):
            raise StorageError("catalog is unreadable")

    run, llm = _run(store, BrokenCatalog())
    assert run.status is RunStatus.ERROR and run.error["code"] == "storage_error" and llm.calls == 0
    assert store.get(Kind.RUN, run.run_id).status is RunStatus.ERROR
    assert store.get(Kind.PROFILE, "p-roguelike").display_name == "roguelike"  # saved state intact


# ------------------------------------------------------------------ B6 RealService: the five course tests
@pytest.fixture
def real(settings):
    from dataclasses import replace

    from gamegene.app.api import create_app
    from gamegene.app.real_service import RealService

    cfg = replace(settings, service="real")
    service = RealService(cfg)
    return service, TestClient(create_app(service, cfg, with_ui=False)), cfg


def _profile(client, persona="roguelike", **extra):
    r = client.post(
        "/api/profiles", json={"display_name": persona, "answers": PERSONAS[persona], **extra}
    )
    assert r.status_code == 201, r.text
    return r.json()["profile_id"]


def test_b6_1_normal_input(real):
    _, client, _ = real
    run = client.post("/api/recommendations", json={"profile_id": _profile(client)}).json()
    assert run["status"] == "ok" and run["same_track"] and run["cross_track"]
    assert client.get(f"/api/runs/{run['run_id']}").json() == run


def test_b6_2_invalid_input(real):
    service, client, _ = real
    service.llm = FakeLLM()
    r = client.post("/api/profiles", json={"display_name": "", "answers": {}})
    assert (
        r.status_code == 400
        and r.json()["code"] == "invalid_input"
        and r.json()["details"]["problems"]
    )
    assert service.llm.calls == 0 and client.get("/api/runs").json() == []


def test_b6_3_no_matching_path(real):
    _, client, _ = real
    run = client.post(
        "/api/recommendations", json={"profile_id": _profile(client), "mode": "surprise_me"}
    ).json()
    assert run["status"] == "no_match"
    pid = _profile(client, "story", filters={"required_language": "klingon"})
    run = client.post("/api/recommendations", json={"profile_id": pid}).json()
    assert run["status"] == "no_match" and run["candidates_after_filters"] == 0


def test_b6_4_forced_error(real):
    service, client, _ = real
    pid = _profile(client)
    service.llm = FakeLLM(script=[UpstreamError("forced model failure")] * 10)
    run = client.post("/api/recommendations", json={"profile_id": pid}).json()
    assert (
        run["status"] == "ok" and run["llm"]["fallbacks"] == 4
    )  # visible recovery: template explanations
    service.steam = FakeSteamLibraryClient(error=UpstreamError("forced steam failure"))
    r = client.post(
        "/api/profiles",
        json={"display_name": "x", "answers": PERSONAS["story"], "steam_id_or_url": ID64},
    )
    assert r.status_code == 201 and service.last_warnings  # profile saved from the interview alone


def test_b6_5_later_read(real):
    _, client, cfg = real
    pid = _profile(client, "builder")
    run = client.post("/api/recommendations", json={"profile_id": pid}).json()
    from gamegene.app.api import create_app
    from gamegene.app.real_service import RealService

    later = TestClient(create_app(RealService(cfg), cfg, with_ui=False))
    assert later.get(f"/api/runs/{run['run_id']}").json() == run
    summaries = later.get("/api/runs", params={"profile_id": pid}).json()
    assert summaries[0]["run_id"] == run["run_id"] and "Factorio" in summaries[0]["titles"]
