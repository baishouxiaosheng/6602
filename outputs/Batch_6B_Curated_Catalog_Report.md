# Batch 6B Curated Catalog Report

Date: 2026-11-22

## Scope

Batch 6B turns the balanced 30-game seed list into a locally importable catalog.
The curation path uses captured public Steam store descriptions and human-reviewed
gene levels. It does not call Qwen and does not consume an LLM API quota.

## Result

- 30 unique Steam AppIDs across six sampling buckets, five games per bucket.
- 29 games are `verified` under the existing evidence threshold.
- What Remains of Edith Finch is `partial`: four gene dimensions have direct
  official-source support, so unsupported dimensions remain null.
- Every non-null gene has an exact quote from the captured official description or
  Steam category list.
- Descriptors refer only to evidence IDs already accepted for the same game.
- Import is transactional, repeatable, and overwrites stale annotations for these
  30 seed games without affecting unrelated catalog entries.

## Evidence review

Generic keyword matching was tightened with word boundaries and narrower semantic
vocabulary. Hand-reviewed anchors are used for passages whose meaning is clear but
whose wording is game-specific. Known false positives are explicitly rejected,
including packaging upgrades, developer authorship, and browsing Workshop mods.

This intentionally favors missing values over unsupported certainty. The catalog
does not force every game to nine known genes or force all 30 games to `verified`.

## Files

- `backend/data/seed_games.csv`: balanced seed manifest.
- `backend/data/seed_store_snapshots.json`: normalized Steam store snapshots.
- `backend/data/curated_gene_levels.json`: reviewed 0–4 gene judgments.
- `backend/app/services/curated_catalog.py`: evidence-gated conversion.
- `backend/app/cli/import_curated_catalog.py`: offline database importer.
- `backend/tests/test_curated_catalog.py`: balance, traceability, status, and
  idempotency checks.

## Command

```bash
cd backend
uv run python -m app.cli.import_curated_catalog
```

No Steam or Qwen credentials are required for this command.

## Verification

- Backend test suite: 57 passed.
- Curated import smoke test: 30 games persisted, 29 verified and 1 partial.
- Persisted accepted evidence records: 174.
- Frontend TypeScript check: passed (frontend source was not changed in Batch 6B).
- Frontend Vitest/Vite rerun was blocked by the desktop runtime's macOS native
  Rollup signature mismatch; this is an execution-environment issue rather than a
  reported passing check.
