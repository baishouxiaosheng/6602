"""[FW] DemoService: a deliberately SIMPLIFIED reference so the UI runs on day one.

What it does: interview scoring, exclusion set, frozen scoring core, both tracks,
template explanations, persistence in <data_dir>/demo.
What it does NOT do (Dev B's RealService must): Steam library import, the other
hard filters and their drop counts, the LLM explanation with constrained checks,
idempotent request_id, ERROR runs, a complete trace. Never demo this to the class.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from ..catalog.reader import make_catalog, stats_of
from ..config import Settings
from ..contracts.errors import InvalidInput
from ..contracts.genes import GENES
from ..contracts.models import (
    SUPPORTED_MODES,
    CatalogStats,
    CatalogStatus,
    Explanation,
    GameRecord,
    InterviewSpec,
    ProfileRequest,
    ProfileSources,
    Reason,
    Recommendation,
    RecommendationRun,
    RecommendRequest,
    RunStatus,
    RunSummary,
    SharedGene,
    TraceStep,
    Track,
    UserProfile,
)
from ..profile.interview import load_interview, score_interview
from ..recommend import scoring
from ..storage import JsonStore, Kind


def _template(shared: list[SharedGene], mismatch: str | None = None) -> Explanation:
    reasons = [
        Reason(
            gene=s.gene,
            evidence_id=s.evidence_id,
            text=f"你想要的强度是 {s.user_target:.1f} / 4，本作为 {s.game_level} / 4。",
        )
        for s in shared[:3]
    ]
    names = "、".join(GENES[s.gene].label_zh for s in shared[:3]) or "暂无共同基因"
    return Explanation(
        headline=f"共同基因：{names}", reasons=reasons, mismatch=mismatch, generated_by="template"
    )


class DemoService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.store = JsonStore(settings.data_dir / "demo")
        self.catalog = make_catalog(settings, JsonStore(settings.data_dir))
        self.last_warnings: list[str] = []

    # ---------------------------------------------------------------- workflow 1
    def get_interview(self) -> InterviewSpec:
        return load_interview()

    def build_profile(self, request: ProfileRequest) -> UserProfile:
        self.last_warnings = []
        name = request.display_name.strip()
        if not 1 <= len(name) <= 40:
            raise InvalidInput("display_name must be 1-40 characters", problems=["display_name"])
        spec = load_interview()
        prefs, tags = score_interview(spec, request.answers)
        if request.profile_id:
            self.store.get(Kind.PROFILE, request.profile_id)  # NotFound if missing
        if request.steam_id_or_url:
            self.last_warnings.append("演示服务不支持导入 Steam 库，已仅用访谈结果生成画像。")
        profile = UserProfile(
            profile_id=request.profile_id or f"p-{secrets.token_hex(4)}",
            display_name=name,
            genes=prefs,
            familiar_tags=tags,
            filters=request.filters,
            sources=ProfileSources(interview_version=spec.version, answers=request.answers),
        )
        self.store.put(Kind.PROFILE, profile.profile_id, profile)
        return profile

    def get_profile(self, profile_id: str) -> UserProfile:
        return self.store.get(Kind.PROFILE, profile_id)  # type: ignore[return-value]

    def list_profiles(self) -> list[str]:
        return self.store.list_ids(Kind.PROFILE)

    # ---------------------------------------------------------------- workflow 3
    def _recommendation(self, profile: UserProfile, game: GameRecord, mismatch: str | None = None):
        parts = scoring.gene_score(profile, game)
        assert parts is not None
        overlap = scoring.surface_overlap(profile, game)
        shared = scoring.shared_genes(profile, game)
        rec = Recommendation(
            appid=game.appid,
            name=game.name,
            track=scoring.assign_track(overlap),
            score=parts.score,
            similarity=parts.similarity,
            coverage=parts.coverage,
            surface_overlap=overlap,
            confidence=scoring.confidence_for(parts, shared),
            shared_genes=shared,
            explanation=_template(shared, mismatch),
            barriers=scoring.barriers(profile, game, overlap),
            price=game.store.price,
            is_free=game.store.is_free,
            store_url=game.store.store_url,
            header_image=game.store.header_image,
        )
        return rec, scoring.is_recommendable(parts, shared)

    def recommend(self, request: RecommendRequest) -> RecommendationRun:
        record = self.store.get_record(Kind.PROFILE, request.profile_id)
        profile: UserProfile = record.data
        run_id = f"r-{datetime.now(UTC):%Y%m%d%H%M%S}-{secrets.token_hex(2)}"
        trace = [TraceStep(step="validate", branch="ok", detail={"profile_id": profile.profile_id})]
        base = dict(
            run_id=run_id,
            request=request,
            profile_id=profile.profile_id,
            profile_revision=record.revision,
        )

        def save(run: RecommendationRun) -> RecommendationRun:
            run.trace.append(TraceStep(step="save", branch="runs", detail={"run_id": run_id}))
            self.store.put(Kind.RUN, run_id, run)
            return run

        if request.mode not in SUPPORTED_MODES:
            trace.append(
                TraceStep(step="route", branch="no_matching_path", detail={"mode": request.mode})
            )
            return save(
                RecommendationRun(
                    **base,
                    status=RunStatus.NO_MATCH,
                    trace=trace,
                    message=f"不支持的请求模式 {request.mode!r}；可用模式：{', '.join(SUPPORTED_MODES)}。",
                )
            )
        trace.append(TraceStep(step="route", branch=f"mode={request.mode}"))

        games = self.catalog.list_games()
        excluded = profile.exclusion_set()
        pool = [
            g
            for g in games
            if g.status == CatalogStatus.VERIFIED
            and g.appid not in excluded
            and scoring.gene_score(profile, g) is not None
        ]
        trace.append(
            TraceStep(
                step="hard_filters",
                branch="demo_exclusions_only",
                detail={"total": len(games), "kept": len(pool)},
            )
        )
        base.update(
            candidates_total=len(games),
            candidates_after_filters=len(pool),
            filter_drops={"demo_not_itemised": len(games) - len(pool)},
        )
        if not pool:
            return save(
                RecommendationRun(
                    **base,
                    status=RunStatus.NO_MATCH,
                    trace=trace,
                    message="过滤后没有任何候选游戏。",
                )
            )

        scored = sorted(
            (self._recommendation(profile, g) for g in pool),
            key=lambda t: (-t[0].score, t[0].appid),
        )
        wanted = {
            "both": (Track.SAME, Track.CROSS),
            "same_track": (Track.SAME,),
            "cross_track": (Track.CROSS,),
        }[request.mode]
        picks = {t: [r for r, ok in scored if ok and r.track == t][: request.top_k] for t in wanted}
        trace.append(
            TraceStep(
                step="score",
                branch="evidence_gate",
                detail={t.value: len(v) for t, v in picks.items()},
            )
        )
        if any(picks.values()):
            return save(
                RecommendationRun(
                    **base,
                    status=RunStatus.OK,
                    trace=trace,
                    message="已生成推荐（演示服务，模板解释）。",
                    same_track=picks.get(Track.SAME, []),
                    cross_track=picks.get(Track.CROSS, []),
                )
            )
        best = next((r for r, _ in scored if r.track in wanted), None)
        if best is not None and best.score >= scoring.CLOSEST_FLOOR:
            mismatch = (
                "；".join(best.barriers) or "匹配分数未达到推荐阈值，或共同基因缺少 A/B 级证据。"
            )
            best = best.model_copy(
                update={"explanation": _template(best.shared_genes, mismatch[:300])}
            )
            trace.append(
                TraceStep(step="decide", branch="closest_only", detail={"appid": best.appid})
            )
            return save(
                RecommendationRun(
                    **base,
                    status=RunStatus.CLOSEST_ONLY,
                    trace=trace,
                    closest=best,
                    message="没有足够匹配且证据充分的游戏；以下是最接近的候选及差异。",
                )
            )
        trace.append(TraceStep(step="decide", branch="no_match"))
        return save(
            RecommendationRun(
                **base,
                status=RunStatus.NO_MATCH,
                trace=trace,
                message="候选池中没有足够匹配且证据充分的游戏，本次不做推荐。",
            )
        )

    def get_run(self, run_id: str) -> RecommendationRun:
        return self.store.get(Kind.RUN, run_id)  # type: ignore[return-value]

    def list_runs(self, profile_id: str | None = None) -> list[RunSummary]:
        out = []
        for rid in reversed(self.store.list_ids(Kind.RUN)):
            run: RecommendationRun = self.store.get(Kind.RUN, rid)  # type: ignore[assignment]
            if profile_id and run.profile_id != profile_id:
                continue
            recs = run.same_track + run.cross_track + ([run.closest] if run.closest else [])
            out.append(
                RunSummary(
                    run_id=rid,
                    profile_id=run.profile_id,
                    status=run.status,
                    created_at=run.created_at,
                    titles=[r.name for r in recs],
                )
            )
        return out

    def catalog_stats(self) -> CatalogStats:
        return stats_of(self.catalog)
