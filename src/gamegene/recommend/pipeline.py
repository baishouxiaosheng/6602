"""[B] Workflow 3 orchestration (task B5). Spec: docs/04-recommendation-spec.md.

    validate -> route(mode) -> load profile -> hard filters -> score -> tracks
             -> evidence gate -> explain (LLM, fallback template) -> save run

Every step appends a TraceStep (step, branch, detail): that trace IS the execution
evidence the course asks for, and the UI shows it.
"""

from __future__ import annotations

from ..contracts.models import RecommendationRun, RecommendRequest
from ..contracts.protocols import CatalogReader, LLMClient
from ..storage import JsonStore


def recommend(
    request: RecommendRequest,
    *,
    store: JsonStore,
    catalog: CatalogReader,
    llm: LLMClient,
) -> RecommendationRun:
    """Branches (each must be reachable in a test and visible in ``trace``):

    A  request_id already claimed        -> return the SAVED run unchanged (no new work)
    B  profile_id missing in store       -> raise NotFound (nothing saved, no model call)
    C  mode not in SUPPORTED_MODES       -> save + return NO_MATCH, message names the mode
                                            and the supported ones; no scoring, no model call
    D  0 candidates after hard filters   -> NO_MATCH, filter_drops explains why
    E  >= 1 recommendable in asked tracks-> OK; top_k per track by (score desc, appid asc)
    F  none recommendable, best score >= CLOSEST_FLOOR
                                         -> CLOSEST_ONLY with ``closest`` + mismatch text
    G  none recommendable, best below    -> NO_MATCH ("no sufficiently supported match")
    H  unexpected GameGeneError after the profile was loaded (storage, catalog)
                                         -> save + return ERROR with error=to_response()
    Model failures are NOT branch H: they fall back to the template (explainer) and
    are counted in ``llm.fallbacks``.

    run_id: "r-" + UTC timestamp yyyymmddHHMMSS + "-" + 4 hex chars.
    mode 'same_track' / 'cross_track' returns only that list.
    """
    raise NotImplementedError("Dev B: task B5")
