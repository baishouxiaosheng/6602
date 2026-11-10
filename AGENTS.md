# AGENTS.md

Instructions for AI coding assistants (Claude Code, Codex, Cursor, Copilot…) and a 2-minute
orientation for humans. Design docs are in Chinese; code, identifiers, docstrings and commit
messages are in English.

## Commands

```bash
uv sync                          # install
uv run pytest -q                 # all tests (offline, < 10 s)
uv run pytest -q -m dev_a        # Dev A acceptance tests only
uv run pytest -q -m dev_b        # Dev B acceptance tests only
uv run ruff check . && uv run ruff format --check .
uv run gamegene serve            # UI + API on http://127.0.0.1:7860
uv run python scripts/build_fixtures.py   # regenerate synthetic fixtures (framework owner only)
```

## Map and ownership

```
src/gamegene/
  contracts/          FROZEN  genes, pydantic models, errors, Protocols      [framework]
  storage/            FROZEN  versioned atomic JSON store                    [framework]
  llm/                FROZEN  provider-independent adapter + FakeLLM         [framework]
  retry.py config.py  FROZEN                                                 [framework]
  recommend/scoring.py   FROZEN  deterministic scoring core                  [framework]
  profile/interview.py   FROZEN  interview scoring                           [framework]
  catalog/reader.py      FROZEN  catalog read side                           [framework]
  app/ui.py render.py api.py demo_service.py service.py   front end          [framework]
  steam/              Dev A   http, store client, library client
  catalog/            Dev A   annotator, verifier, pipeline
  prompts/annotate_genes_v1.md   Dev A
  profile/library.py builder.py  Dev B
  recommend/filters.py explainer.py pipeline.py   Dev B
  app/real_service.py            Dev B
  prompts/explain_v1.md          Dev B
tests/framework  must always pass     tests/dev_a, tests/dev_b  acceptance tests = definition of done
```

## Hard rules

1. **Do not edit FROZEN files or anything in `tests/`** to make your code pass. If a contract,
   threshold or acceptance test looks wrong, stop and open an issue / tell the designer. Contract
   changes need an ADR in `docs/adr/` and a `SCHEMA_VERSION` bump.
2. **Stay in your owner's directories.** Never implement the other developer's stubs.
3. **Signatures of stubs are fixed.** Replace `raise NotImplementedError` with code; keep names,
   parameters and return types. Add private helpers freely.
4. **No network and no real API key in tests.** Use `httpx.MockTransport`, `FakeLLM`,
   `FakeSteamLibraryClient`. Tests that need the network get `@pytest.mark.live` and never run in CI.
5. **Never commit secrets or runtime data**: `.env`, `data/store/`, `data/raw/`, `evidence/*`.
   Never print an API key; never paste one into an issue, screenshot or prompt.
6. **Errors**: raise only `gamegene.contracts.errors` classes across module boundaries; never
   return `None` for a failure; never swallow an exception silently.
7. **Deterministic first**: validation and hard rules run before any Steam or model call. The model
   words explanations and proposes annotations; code decides (see `docs/01-architecture.md` §5).
8. **Never invent evidence.** A gene without a verified quote is `level=None`. Do not hand-edit
   catalog JSON to make a demo look better.
9. Use `retry.retry_call` for retries (bounded, retryable errors only). No other retry loops.
10. All text shown in the UI is HTML-escaped in `app/render.py`; do not build HTML elsewhere.

## Definition of done (per task)

- its acceptance tests pass, none skipped; `uv run pytest -q` and `ruff check` are clean;
- public functions have a one-paragraph docstring; no TODO left in the touched file;
- the PR description lists which task IDs (A1…/B1…) it completes.

## Working style for assistants

Read the task's section in `docs/handoff/DEV_*.md` and the spec it links before writing code.
Implement one task ID per change. Run the task's tests after each step. Prefer the standard
library and the dependencies already in `pyproject.toml`; ask before adding a dependency.
