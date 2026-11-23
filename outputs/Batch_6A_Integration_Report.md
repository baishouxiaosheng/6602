# Batch 6A Fixture Integration Report

Date: 2026-11-22

## Scope

Batch 6A integrates the supplied five-game JSON fixture into the V1.3 domain and
SQLite catalog without calling Steam or Qwen. The fixture remains a development
and integration set; it does not replace the planned 30-game MVP seed catalog.

## Imported catalog

| AppID | Game | Sampling bucket | Known genes | Status |
|---:|---|---|---:|---|
| 1145360 | Hades | action | 6 | verified |
| 558990 | Opus Magnum | simulation | 5 | verified |
| 646570 | Slay the Spire | strategy | 7 | verified |
| 413150 | Stardew Valley | simulation | 5 | verified |
| 1135690 | Unpacking | casual | 7 | verified |

Opus Magnum is assigned to `simulation` because the embedded Steam snapshot does
not contain the Strategy genre. The importer never uses the fixture's top-level
genre list to override the embedded Steam source.

## Normalization and validation

- All nine genes are represented; unsupported values remain `null`.
- Non-null gene levels require verified high/medium-priority evidence.
- Evidence quotes are trace-checked after Unicode quote and whitespace normalization.
- Descriptor strings become stable IDs and keep only supporting evidence IDs.
- Duplicate AppIDs and duplicate evidence IDs are rejected.
- Steam categories are converted into normalized social-mode markers.
- The offline fixture declares Windows and English as its supported demo surface.
- Import is transactional and idempotent.

## Verification

- Backend: 54 tests passed.
- Frontend: 5 tests passed.
- Python compilation: passed.
- TypeScript and Vite production build: passed.
- Offline CLI smoke test: 5 games imported, 5 verified.
- Dual-track fixture scenario: Hades appeared in same-track retrieval and a verified
  fixture game appeared in cross-track retrieval; the ranking whitelist and evidence
  contract remained enforced.
- No API keys or SQLite databases were added to the repository.

## Deferred to later Batch 6 work

- Expand to the curated 30-game `6 x 5` catalog.
- Run Stage B against real review snapshots where required.
- Connect a real Steam Web API key and public test SteamID64.
- Connect the configured Qwen endpoint and record live cost/latency/error metrics.
