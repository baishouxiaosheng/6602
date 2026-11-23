# Batch 6C Live End-to-End Report

Date: 2026-11-22

## Scope

Batch 6C validates the 30-game curated catalog through the real FastAPI workflow,
a public Steam library, the configured Alibaba Cloud Qwen endpoint, and the React
demo UI. Bulk Qwen annotation of owned games is disabled by default.

## Live inputs

- Public Steam account: masked as `*************9608`.
- Steam Web API Key: loaded from `.env`; never printed.
- Curated catalog: 30 games, 29 verified and 1 partial.
- Library: 48 owned games, 47 with recorded playtime.
- Catalog overlap: 5 games.
- Reviewed favorites used for the library signal: Stardew Valley, Slay the Spire,
  and ELDEN RING.

All 48 owned AppIDs were persisted in the exclusion set. The 43 games outside the
reviewed catalog were not sent to Qwen; they do not influence gene levels and the
profile exposes this limitation as a warning.

Live Qwen usage during construction was one preference-parse request and four ranking
requests: the first ranking was rejected, and three later runs verified the repair
path and two evidence corrections. There were zero per-game annotation requests.

## Final live result

The final recommendation run completed with status `ok`:

| Track | Rank | Game | Compatibility |
|---|---:|---|---:|
| Same-track | 1 | Divinity: Original Sin 2 - Definitive Edition | 0.797 |
| Cross-track | 1 | Hollow Knight | 0.745 |

The workflow returned fewer than three games per track instead of filling slots with
lower-quality candidates. Neither result is owned by the test account.

Manual semantic review confirmed that every displayed matched gene has a stored
official-source evidence ID. The reasons also state unverified needs and mismatches:

- Divinity matches strategy, exploration, and low turn-based pace; challenge remains
  explicitly unverified.
- Hollow Knight matches challenge, exploration, and progression; strategy is weaker
  than requested and calm pacing is explicitly unverified.

## Issues found and corrected

1. The Steam partner hostname timed out on the current network. `GetOwnedGames` and
   vanity resolution now use the official public `api.steampowered.com` hostname.
2. Inventory confirmation previously attempted annotation for every uncatalogued
   owned game. A safe default now indexes and excludes those games without paid bulk
   annotation. The old behavior remains an explicit configuration option.
3. A semantically invalid Qwen ranking was correctly rejected, but no repair was
   attempted. Ranking now receives one constrained repair attempt with the rejected
   JSON and deterministic validation error; the evidence whitelist is not relaxed.
4. “Build a legacy” was rejected as creation evidence for Crusader Kings III.
5. Generic “action adventure” was rejected as pace evidence for Hollow Knight.
   Both facts were nulled and the recommendation was rerun.
6. The live smoke script used outdated track strings on its first attempt. It now
   uses the frozen `same_track` and `cross_track` contract and can resume an imported
   profile without repeating preference parsing or Steam import.

## Verification

- Backend: 59 tests passed.
- Frontend: 5 tests passed.
- TypeScript and Vite production build: passed.
- Browser smoke test: React questionnaire rendered and showed `Backend connected`;
  `/api/health` and `/api/questionnaire` returned HTTP 200.
- Steam live read: 48 games returned successfully.
- Owned-game exclusion: 48 of 48 imported AppIDs present; 0 appeared in results.
- Qwen: real preference parsing and real final ranking completed.
- Evidence review: final displayed results approved after two weak facts were nulled.

## Reproduction

```bash
cd backend
uv run python -m app.cli.import_curated_catalog
uv run python -m app.cli.live_e2e_smoke --steam-id YOUR_PUBLIC_STEAMID64
```

The command intentionally requires a SteamID argument and does not store it in source
control. API keys remain backend-only in `.env`.
