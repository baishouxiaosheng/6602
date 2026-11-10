"""The five course tests, run against the DemoService through the HTTP API.
tests/dev_b/test_real_service.py repeats them against RealService."""

import pytest
from fastapi.testclient import TestClient

from gamegene.app.api import create_app
from gamegene.app.demo_service import DemoService
from tests.conftest import PERSONAS


@pytest.fixture
def client(settings):
    return TestClient(create_app(DemoService(settings), settings, with_ui=False))


def _profile(client, persona="roguelike"):
    r = client.post("/api/profiles", json={"display_name": persona, "answers": PERSONAS[persona]})
    assert r.status_code == 201, r.text
    return r.json()["profile_id"]


def test_1_normal_input(client):
    pid = _profile(client)
    run = client.post("/api/recommendations", json={"profile_id": pid}).json()
    assert run["status"] == "ok"
    assert [r["name"] for r in run["same_track"]] == ["Dead Cells", "Hades"]
    assert [r["name"] for r in run["cross_track"]] == ["Hollow Knight", "Celeste"]
    for rec in run["same_track"] + run["cross_track"]:
        assert rec["shared_genes"] and rec["explanation"]["reasons"]
    assert run["trace"][-1]["step"] == "save"


def test_2_invalid_input(client):
    r = client.post("/api/profiles", json={"display_name": "x", "answers": {"q01_failure": ["a"]}})
    assert r.status_code == 400 and r.json()["code"] == "invalid_input"
    assert len(r.json()["details"]["problems"]) == 10
    r = client.post("/api/recommendations", json={"profile_id": "p-x", "top_k": 99})
    assert r.status_code == 400 and r.json()["code"] == "invalid_input"
    assert client.get("/api/runs").json() == []  # nothing was saved


def test_3_no_matching_path(client):
    pid = _profile(client)
    run = client.post(
        "/api/recommendations", json={"profile_id": pid, "mode": "surprise_me"}
    ).json()
    assert run["status"] == "no_match" and "surprise_me" in run["message"]
    assert run["same_track"] == [] and run["cross_track"] == []
    assert any(t["branch"] == "no_matching_path" for t in run["trace"])


def test_unknown_ids_are_404(client):
    assert client.post("/api/recommendations", json={"profile_id": "p-missing"}).status_code == 404
    assert client.get("/api/runs/r-missing").status_code == 404
    assert client.get("/api/profiles/p-missing").status_code == 404


def test_5_later_read(client, settings):
    pid = _profile(client, "story")
    run = client.post("/api/recommendations", json={"profile_id": pid}).json()
    fresh = TestClient(
        create_app(DemoService(settings), settings, with_ui=False)
    )  # "later": new process state
    again = fresh.get(f"/api/runs/{run['run_id']}").json()
    assert again == run
    assert fresh.get("/api/runs", params={"profile_id": pid}).json()[0]["run_id"] == run["run_id"]
    assert fresh.get(f"/api/profiles/{pid}").json()["display_name"] == "story"


def test_revising_a_profile_keeps_its_id(client):
    pid = _profile(client)
    r = client.post(
        "/api/profiles",
        json={"profile_id": pid, "display_name": "v2", "answers": PERSONAS["builder"]},
    )
    assert r.status_code == 201 and r.json()["profile_id"] == pid
    assert client.get(f"/api/profiles/{pid}").json()["display_name"] == "v2"


def test_ui_builds(settings):
    from gamegene.app.ui import build_ui

    assert build_ui(DemoService(settings), settings) is not None
