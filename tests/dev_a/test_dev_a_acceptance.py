"""Acceptance tests for Dev A. Skipped while the stub raises NotImplementedError.
No test here touches the network: HTTP goes through httpx.MockTransport or fakes.
If a test contradicts docs/, the docs win: tell the designer instead of bending code."""

from __future__ import annotations

import httpx
import pytest

from gamegene.catalog import annotator, pipeline, verifier
from gamegene.contracts import (
    CatalogStatus,
    ConfigError,
    EvidenceGrade,
    GameRecord,
    InvalidInput,
    NotFound,
    Platform,
    RateLimited,
    SocialMode,
    SourceType,
    SteamProfilePrivate,
    UpstreamError,
)
from gamegene.llm import FakeLLM
from gamegene.steam.http import ThrottledHttp
from gamegene.steam.library import HttpSteamLibraryClient
from gamegene.steam.store import HttpSteamStoreClient, normalize_store_info
from gamegene.storage import Kind
from tests.conftest import load_json

pytestmark = pytest.mark.dev_a
APPID = 424242


def _http(handler, **kw) -> ThrottledHttp:
    return ThrottledHttp(
        min_interval_s=kw.pop("min_interval_s", 0),
        sleep=kw.pop("sleep", lambda s: None),
        transport=httpx.MockTransport(handler),
        **kw,
    )


# ------------------------------------------------------------------ A1 http
def test_a1_json_ok_and_error_mapping():
    assert _http(lambda r: httpx.Response(200, json={"a": 1})).get_json("https://x.test/a") == {
        "a": 1
    }
    with pytest.raises(NotFound):
        _http(lambda r: httpx.Response(404)).get_json("https://x.test/a")
    with pytest.raises(RateLimited):
        _http(lambda r: httpx.Response(429)).get_json("https://x.test/a")
    with pytest.raises(UpstreamError):
        _http(lambda r: httpx.Response(200, text="<html>oops</html>")).get_json("https://x.test/a")


def test_a1_retries_5xx_three_times_then_gives_up():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503)

    with pytest.raises(UpstreamError):
        _http(handler).get_json("https://x.test/a")
    assert len(calls) == 3


def test_a1_recovers_after_a_transient_failure():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(503) if len(calls) == 1 else httpx.Response(200, json={"ok": True})

    assert _http(handler).get_json("https://x.test/a") == {"ok": True}


def test_a1_throttles_same_host():
    now, sleeps = [0.0], []

    def sleep(s):
        sleeps.append(s)
        now[0] += s

    http = _http(
        lambda r: httpx.Response(200, json={}),
        min_interval_s=1.5,
        sleep=sleep,
        clock=lambda: now[0],
    )
    http.get_json("https://x.test/a")
    http.get_json("https://x.test/b")
    assert sum(sleeps) == pytest.approx(1.5)


# ------------------------------------------------------------------ A2 store client
def _store_handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if "appdetails" in url and "steamspy" not in url:
        appid = request.url.params["appids"]
        if appid == str(APPID):
            return httpx.Response(
                200,
                json={appid: {"success": True, "data": load_json("steam_appdetails_sample.json")}},
            )
        return httpx.Response(200, json={appid: {"success": False}})
    if "appreviews" in url:
        page = load_json("steam_reviews_sample.json")
        if request.url.params.get("cursor") != "*":
            page["reviews"] = []
        return httpx.Response(200, json=page)
    if "steamspy" in url:
        return httpx.Response(
            200, json={"appid": APPID, "tags": {"Roguelike": 900, "Card Game": 500, "Indie": 100}}
        )
    return httpx.Response(500)


def test_a2_details_reviews_tags_and_raw_cache(tmp_path):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return _store_handler(request)

    client = HttpSteamStoreClient(_http(handler), tmp_path / "raw")
    assert client.get_app_details(APPID)["name"] == "Sample Quest"
    reviews = client.get_reviews(APPID, limit=100)
    assert [r["recommendationid"] for r in reviews] == [
        "1001",
        "1002",
    ]  # the 3-char review is dropped
    assert client.get_tags(APPID)["Roguelike"] == 900
    assert (tmp_path / "raw" / str(APPID) / "appdetails.json").is_file()
    n = len(calls)
    client.get_app_details(APPID)  # second call is served from the raw snapshot
    assert len(calls) == n


def test_a2_unknown_app_and_optional_tags(tmp_path):
    client = HttpSteamStoreClient(_http(_store_handler), tmp_path / "raw")
    with pytest.raises(NotFound):
        client.get_app_details(1)
    broken = HttpSteamStoreClient(_http(lambda r: httpx.Response(500)), tmp_path / "raw2")
    assert broken.get_tags(APPID) == {}  # tags never fail the pipeline


# ------------------------------------------------------------------ A3 normalisation
def test_a3_normalize_store_info():
    info = normalize_store_info(
        APPID,
        load_json("steam_appdetails_sample.json"),
        {"Roguelike": 900, "Card Game": 500, "Indie": 100},
        cc="us",
        lang="english",
    )
    assert info.genres == ["indie", "strategy"]
    assert info.tags == ["roguelike", "card game", "indie"]
    assert info.platforms == [Platform.WINDOWS, Platform.LINUX]
    assert set(info.social_modes) == {SocialMode.SINGLE, SocialMode.COOP, SocialMode.PVP}
    assert info.languages == ["english", "simplified chinese", "japanese"]
    assert (info.price.final_cents, info.price.initial_cents, info.price.discount_percent) == (
        1499,
        1999,
        25,
    )
    assert info.store_url == f"https://store.steampowered.com/app/{APPID}/"
    assert info.release_date == "Jan 23, 2019" and not info.is_free


def test_a3_free_game_has_no_price():
    raw = load_json("steam_appdetails_sample.json")
    raw["is_free"] = True
    del raw["price_overview"]
    info = normalize_store_info(APPID, raw, {}, cc="us", lang="english")
    assert info.is_free and info.price is None and info.tags == []


# ------------------------------------------------------------------ A4 library
ID64 = "76561198000000001"


def _lib_handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if "ResolveVanityURL" in url:
        ok = request.url.params["vanityurl"] == "gabe"
        return httpx.Response(
            200, json={"response": {"success": 1, "steamid": ID64} if ok else {"success": 42}}
        )
    if request.url.params["steamid"] == ID64:
        return httpx.Response(
            200,
            json={
                "response": {
                    "game_count": 1,
                    "games": [{"appid": 620, "name": "Portal 2", "playtime_forever": 600}],
                }
            },
        )
    return httpx.Response(200, json={"response": {}})


def test_a4_resolve_all_input_forms():
    lib = HttpSteamLibraryClient(_http(_lib_handler), "KEY")
    assert lib.resolve_steam_id(ID64) == ID64
    assert lib.resolve_steam_id(f"https://steamcommunity.com/profiles/{ID64}/") == ID64
    assert lib.resolve_steam_id("https://steamcommunity.com/id/gabe/") == ID64
    assert lib.resolve_steam_id("gabe") == ID64
    with pytest.raises(NotFound):
        lib.resolve_steam_id("nobody-here")
    with pytest.raises(InvalidInput):
        lib.resolve_steam_id("   ")
    with pytest.raises(InvalidInput):
        lib.resolve_steam_id("https://example.com/whatever")


def test_a4_owned_games_private_and_missing_key():
    lib = HttpSteamLibraryClient(_http(_lib_handler), "KEY")
    games = lib.get_owned_games(ID64)
    assert (games[0].appid, games[0].playtime_minutes) == (620, 600)
    with pytest.raises(SteamProfilePrivate):
        lib.get_owned_games("76561198000000002")
    with pytest.raises(ConfigError):
        HttpSteamLibraryClient(_http(_lib_handler), "").resolve_steam_id("gabe")


# ------------------------------------------------------------------ A6 verifier
PASSAGE = "<p>Every run is different. You will die a lot, and that is the point.</p>"


def test_a6_match_score():
    assert verifier.match_score("You will die a lot, and that is the point.", PASSAGE) == 1.0
    assert (
        verifier.match_score("you  will DIE a lot, and that is the point.", PASSAGE) == 1.0
    )  # normalised
    assert (
        verifier.match_score("You will die a lot and that's the point", PASSAGE)
        >= verifier.FUZZY_MIN
    )
    assert (
        verifier.match_score("The soundtrack is a masterpiece of synthwave.", PASSAGE)
        < verifier.FUZZY_MIN
    )
    assert verifier.match_score("die", PASSAGE) == 0.0  # too short to count as evidence


def test_a6_grade_table():
    g = verifier.grade_evidence
    assert g(SourceType.STORE_DESCRIPTION, 1.0) is EvidenceGrade.A
    assert g(SourceType.OFFICIAL_DOCS, 1.0) is EvidenceGrade.A
    assert g(SourceType.WIKI, 1.0) is EvidenceGrade.B
    assert g(SourceType.STORE_REVIEW, 1.0, supporting_reviews=2) is EvidenceGrade.B
    assert g(SourceType.STORE_REVIEW, 1.0, supporting_reviews=1) is EvidenceGrade.C
    assert g(SourceType.STORE_DESCRIPTION, 0.9) is EvidenceGrade.C
    assert g(SourceType.STORE_DESCRIPTION, 0.84) is None


# ------------------------------------------------------------------ A5 annotator
def _passages():
    return annotator.build_passages(
        APPID,
        load_json("steam_appdetails_sample.json"),
        load_json("steam_reviews_sample.json")["reviews"][:2],
        {"Roguelike": 900},
    )


def _claims(passages, **levels):
    """Nine claims; genes named in ``levels`` get (level, quote, passage index)."""
    from gamegene.contracts import GENE_ORDER

    out = []
    for g in GENE_ORDER:
        if g.value in levels:
            level, quote, idx = levels[g.value]
            out.append(
                {
                    "gene": g.value,
                    "level": level,
                    "confidence": "high",
                    "quote": quote,
                    "source_index": idx,
                }
            )
        else:
            out.append({"gene": g.value, "level": None})
    return {"claims": out}


def test_a5_passages_are_clean_and_ordered():
    ps = _passages()
    assert [p.index for p in ps] == list(range(len(ps)))
    assert ps[0].source_type == "store_description" and "<" not in ps[0].text
    review = [p for p in ps if p.source_type == "store_review"]
    assert [p.source_ref for p in review] == ["1001", "1002"]  # votes_up desc


def test_a5_annotate_downgrades_unsupported_claims():
    ps = _passages()
    answer = _claims(ps, challenge=(4, "You will die a lot, and that is the point.", 0))
    answer["claims"][1].update(
        level=3, confidence="medium", quote="x" * 20, source_index=0
    )  # not high
    answer["claims"][2].update(level=2, confidence="high")  # no quote
    out = annotator.annotate(FakeLLM(script=[answer]), "Sample Quest", ps, {"Roguelike": 900})
    levels = {c.gene.value: c.level for c in out.claims}
    assert levels["challenge"] == 4 and levels["strategy"] is None and levels["pace"] is None


# ------------------------------------------------------------------ A7 pipeline
class FakeSteam:
    def __init__(self, fail_details: Exception | None = None):
        self.fail_details = fail_details

    def get_app_details(self, appid):
        if self.fail_details:
            raise self.fail_details
        return load_json("steam_appdetails_sample.json")

    def get_reviews(self, appid, *, limit=100):
        return load_json("steam_reviews_sample.json")["reviews"][:2]

    def get_tags(self, appid):
        return {"Roguelike": 900, "Card Game": 500}


Q_DIE = "You will die a lot, and that is the point."
Q_RUN = "Every run is different."
Q_DECK = "Build a deck of over 200 cards & relics."
Q_SOLO = "A strictly single-player experience."
Q_HARD = "the combat is brutally hard and every mistake gets punished"


def _five_gene_answer(ps):
    def idx(needle):
        return next(p.index for p in ps if needle.lower()[:20] in p.text.lower())

    return _claims(
        ps,
        challenge=(4, Q_DIE, idx(Q_DIE)),
        progression=(2, Q_RUN, idx(Q_RUN)),
        strategy=(3, Q_DECK, idx("Build a deck")),
        social=(0, Q_SOLO, idx(Q_SOLO)),
        pace=(2, Q_HARD, idx(Q_HARD)),
    )


def test_a7_verified_record(store):
    answer = _five_gene_answer(_passages())
    report = pipeline.process_game(
        APPID, steam=FakeSteam(), llm=FakeLLM(script=[answer]), store=store
    )
    assert (report.outcome, report.known_genes) == ("verified", 5)
    rec: GameRecord = store.get(Kind.GAME, str(APPID))
    assert (
        rec.status is CatalogStatus.VERIFIED
        and rec.annotation.prompt_version == annotator.PROMPT_VERSION
    )
    grades = {e.gene.value: e.grade for e in rec.evidence}
    assert grades["challenge"] is EvidenceGrade.A  # verbatim in the store description
    assert grades["pace"] is EvidenceGrade.B  # verbatim in two reviews
    assert rec.genes["narrative"].level is None and rec.genes["narrative"].unknown_reason


def test_a7_invented_quote_becomes_unknown_and_partial(store):
    ps = _passages()
    answer = _five_gene_answer(ps)
    answer["claims"][0]["quote"] = (
        "Critics call it the hardest game of the decade."  # not in any source
    )
    report = pipeline.process_game(
        APPID, steam=FakeSteam(), llm=FakeLLM(script=[answer]), store=store
    )
    assert report.outcome == "partial"
    rec = store.get(Kind.GAME, str(APPID))
    assert rec.status is CatalogStatus.PARTIAL and rec.genes["challenge"].level is None
    assert rec.genes["challenge"].unknown_reason == "evidence_unverified" and rec.review_note


def test_a7_model_failure_is_recorded_not_lost(store):
    report = pipeline.process_game(
        APPID, steam=FakeSteam(), llm=FakeLLM(script=[UpstreamError("llm down")]), store=store
    )
    assert (report.outcome, report.step, report.error_code) == (
        "failed",
        "annotate",
        "upstream_error",
    )
    rec = store.get(Kind.GAME, str(APPID))
    assert rec.status is CatalogStatus.FAILED and "llm down" in rec.review_note
    assert rec.store.genres == ["indie", "strategy"]  # the fetch survived


def test_a7_failure_never_overwrites_a_verified_record(store):
    pipeline.process_game(
        APPID, steam=FakeSteam(), llm=FakeLLM(script=[_five_gene_answer(_passages())]), store=store
    )
    report = pipeline.process_game(
        APPID,
        steam=FakeSteam(fail_details=UpstreamError("steam down")),
        llm=FakeLLM(),
        store=store,
        force=True,
    )
    assert (report.outcome, report.step) == ("failed", "fetch")
    assert store.get(Kind.GAME, str(APPID)).status is CatalogStatus.VERIFIED


def test_a7_batch_skips_verified_and_survives_failures(store, tmp_path):
    answer = _five_gene_answer(_passages())
    llm = FakeLLM(script=[answer, UpstreamError("llm down")])
    report = pipeline.run_batch(
        [APPID, 555], steam=FakeSteam(), llm=llm, store=store, report_dir=tmp_path / "rep"
    )
    assert report.counts() == {"verified": 1, "failed": 1}
    again = pipeline.run_batch(
        [APPID], steam=FakeSteam(), llm=FakeLLM(), store=store, report_dir=tmp_path / "rep"
    )
    assert again.counts() == {"skipped": 1}
    assert len(list((tmp_path / "rep").glob("catalog-batch-*.json"))) == 2
