import json

import pytest

from gamegene.contracts import Conflict, InvalidInput, NotFound, StorageError
from gamegene.storage import Kind
from tests.conftest import make_profile


def test_put_get_and_revisions(store):
    p = make_profile()
    assert store.put(Kind.PROFILE, p.profile_id, p).revision == 1
    p2 = p.model_copy(update={"display_name": "renamed"})
    assert store.put(Kind.PROFILE, p.profile_id, p2).revision == 2
    assert store.get(Kind.PROFILE, p.profile_id).display_name == "renamed"
    assert store.get(Kind.PROFILE, p.profile_id, revision=1).display_name == "roguelike"
    assert store.list_revisions(Kind.PROFILE, p.profile_id) == [1, 2]
    assert store.list_ids(Kind.PROFILE) == [p.profile_id]


def test_missing_and_illegal_ids(store):
    with pytest.raises(NotFound):
        store.get(Kind.PROFILE, "p-nope")
    with pytest.raises(InvalidInput):
        store.get(Kind.PROFILE, "../etc/passwd")


def test_optimistic_lock(store):
    p = make_profile()
    store.put(Kind.PROFILE, p.profile_id, p, expected_revision=0)
    with pytest.raises(Conflict):
        store.put(Kind.PROFILE, p.profile_id, p, expected_revision=0)


def test_wrong_model_type_rejected(store, catalog):
    with pytest.raises(InvalidInput):
        store.put(Kind.PROFILE, "p-abc", catalog.get_game(620))


def test_corrupt_file_is_a_storage_error_not_a_crash(store):
    p = make_profile()
    store.put(Kind.PROFILE, p.profile_id, p)
    (store.root / "profiles" / f"{p.profile_id}.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(StorageError):
        store.get(Kind.PROFILE, p.profile_id)


def test_failed_write_keeps_previous_revision(store, monkeypatch):
    p = make_profile()
    store.put(Kind.PROFILE, p.profile_id, p)
    import os

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(StorageError):
        store.put(Kind.PROFILE, p.profile_id, p.model_copy(update={"display_name": "new"}))
    monkeypatch.undo()
    assert store.get(Kind.PROFILE, p.profile_id).display_name == "roguelike"
    leftovers = [f.name for f in (store.root / "profiles").iterdir() if f.name.startswith(".tmp-")]
    assert leftovers == []


def test_envelope_on_disk(store):
    p = make_profile()
    store.put(Kind.PROFILE, p.profile_id, p)
    raw = json.loads((store.root / "profiles" / f"{p.profile_id}.json").read_text(encoding="utf-8"))
    assert raw["schema_version"] == "1.0" and raw["revision"] == 1 and raw["kind"] == "profiles"


def test_request_claim_is_idempotent(store):
    assert store.claim_request("req-1", "r-a") == "r-a"
    assert store.claim_request("req-1", "r-b") == "r-a"
