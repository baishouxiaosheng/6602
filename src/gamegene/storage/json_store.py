"""Versioned JSON store = the project's Data Store.

Layout (under GAMEGENE_DATA_DIR):
    <kind>/<id>.json                 latest revision, wrapped in an envelope
    <kind>/_history/<id>.r0001.json  every earlier revision, never modified
    requests/<request_id>.json       idempotency index: request_id -> run_id

Guarantees:
* writes are atomic (temp file + os.replace), so a crash never leaves a half file;
* a failed write leaves the previous revision untouched;
* every envelope carries schema_version, revision and timestamps;
* ``put(..., expected_revision=n)`` gives optimistic locking (Conflict on mismatch).
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from ..contracts.errors import Conflict, InvalidInput, NotFound, StorageError
from ..contracts.models import SCHEMA_VERSION, GameRecord, RecommendationRun, UserProfile, utcnow

T = TypeVar("T", bound=BaseModel)

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


class Kind(StrEnum):
    PROFILE = "profiles"
    GAME = "catalog"
    RUN = "runs"


_MODEL_FOR: dict[Kind, type[BaseModel]] = {
    Kind.PROFILE: UserProfile,
    Kind.GAME: GameRecord,
    Kind.RUN: RecommendationRun,
}


class StoredRecord(BaseModel, Generic[T]):
    schema_version: str
    kind: Kind
    id: str
    revision: int
    created_at: datetime
    updated_at: datetime
    data: T


class JsonStore:
    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root)

    # ------------------------------------------------------------------ paths
    def _path(self, kind: Kind, record_id: str) -> Path:
        if not _ID_RE.match(record_id):
            raise InvalidInput(f"illegal record id: {record_id!r}", kind=kind.value)
        return self.root / kind.value / f"{record_id}.json"

    def _history_path(self, kind: Kind, record_id: str, revision: int) -> Path:
        return self.root / kind.value / "_history" / f"{record_id}.r{revision:04d}.json"

    # ------------------------------------------------------------------ io
    @staticmethod
    def _write_atomic(path: Path, text: str) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(text)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp, path)
            except BaseException:
                Path(tmp).unlink(missing_ok=True)
                raise
        except OSError as err:
            raise StorageError(f"cannot write {path.name}: {err}", path=str(path)) from err

    def _read_envelope(self, kind: Kind, path: Path) -> StoredRecord:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            envelope = StoredRecord[_MODEL_FOR[kind]].model_validate(raw)  # type: ignore[valid-type]
        except FileNotFoundError as err:
            raise NotFound(f"{kind.value}/{path.stem} does not exist", kind=kind.value) from err
        except (OSError, json.JSONDecodeError, ValidationError) as err:
            raise StorageError(
                f"{kind.value}/{path.name} is unreadable or violates the schema: {err}",
                path=str(path),
            ) from err
        return envelope

    # ------------------------------------------------------------------ api
    def exists(self, kind: Kind, record_id: str) -> bool:
        return self._path(kind, record_id).is_file()

    def get_record(self, kind: Kind, record_id: str, revision: int | None = None) -> StoredRecord:
        latest = self._read_envelope(kind, self._path(kind, record_id))
        if revision is None or revision == latest.revision:
            return latest
        return self._read_envelope(kind, self._history_path(kind, record_id, revision))

    def get(self, kind: Kind, record_id: str, revision: int | None = None) -> BaseModel:
        return self.get_record(kind, record_id, revision).data

    def put(
        self,
        kind: Kind,
        record_id: str,
        data: BaseModel,
        *,
        expected_revision: int | None = None,
    ) -> StoredRecord:
        """Create (revision 1) or replace (revision n+1). Returns the new envelope."""
        model = _MODEL_FOR[kind]
        if not isinstance(data, model):
            raise InvalidInput(f"{kind.value} expects {model.__name__}, got {type(data).__name__}")
        path = self._path(kind, record_id)
        now = utcnow()
        previous: StoredRecord | None = None
        if path.is_file():
            previous = self._read_envelope(kind, path)
        current_rev = previous.revision if previous else 0
        if expected_revision is not None and expected_revision != current_rev:
            raise Conflict(
                f"{kind.value}/{record_id} is at revision {current_rev}, "
                f"expected {expected_revision}",
                current_revision=current_rev,
            )
        envelope = StoredRecord[model](  # type: ignore[valid-type]
            schema_version=SCHEMA_VERSION,
            kind=kind,
            id=record_id,
            revision=current_rev + 1,
            created_at=previous.created_at if previous else now,
            updated_at=now,
            data=data,
        )
        if previous is not None:
            self._write_atomic(
                self._history_path(kind, record_id, previous.revision),
                previous.model_dump_json(indent=2),
            )
        self._write_atomic(path, envelope.model_dump_json(indent=2))
        return envelope

    def list_ids(self, kind: Kind) -> list[str]:
        folder = self.root / kind.value
        if not folder.is_dir():
            return []
        return sorted(p.stem for p in folder.glob("*.json") if not p.name.startswith("."))

    def list_revisions(self, kind: Kind, record_id: str) -> list[int]:
        latest = self.get_record(kind, record_id).revision
        return list(range(1, latest + 1))

    # ------------------------------------------------------------ idempotency
    def claim_request(self, request_id: str, run_id: str) -> str:
        """Bind request_id -> run_id. Returns the run_id that owns the request:
        ``run_id`` if this call claimed it, or the earlier one for a duplicate."""
        if not _ID_RE.match(request_id):
            raise InvalidInput(f"illegal request_id: {request_id!r}")
        path = self.root / "requests" / f"{request_id}.json"
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))["run_id"]
        self._write_atomic(path, json.dumps({"request_id": request_id, "run_id": run_id}))
        return run_id
