"""[UI] Gradio front end. Talks to contracts.GameGeneService only.

Layout: 画像 (Workflow 1) | 推荐 (Workflow 3) | 历史 (later read) | 系统.
Every handler is wrapped by ``_guard``: a GameGeneError becomes a visible error
panel, never a stack trace and never a silent blank.
"""

from __future__ import annotations

import gradio as gr

from ..config import Settings, load_settings
from ..contracts.errors import ErrorResponse, GameGeneError, InvalidInput
from ..contracts.models import (
    HardFilters,
    Platform,
    ProfileRequest,
    RecommendRequest,
    SocialMode,
)
from ..contracts.protocols import GameGeneService
from . import render
from .service import make_service

MODE_LABELS = {"both": "两条轨道", "same_track": "仅同类轨", "cross_track": "仅其他轨"}
PLATFORM_CHOICES = [("Windows", "windows"), ("macOS", "mac"), ("Linux", "linux")]
SOCIAL_CHOICES = [("单人", "single"), ("合作", "coop"), ("对战", "pvp"), ("MMO", "mmo")]
LANG_CHOICES = [
    ("不限", ""),
    ("简体中文", "simplified chinese"),
    ("English", "english"),
    ("繁體中文", "traditional chinese"),
    ("日本語", "japanese"),
]
EMPTY_RUN = ("", "", "[]")


def _error(err: Exception) -> str:
    if isinstance(err, GameGeneError):
        return render.error_html(err.to_response())
    return render.error_html(
        ErrorResponse(
            code="internal_error", message=str(err) or type(err).__name__, http_status=500
        )
    )


def build_ui(service: GameGeneService | None = None, settings: Settings | None = None) -> gr.Blocks:
    settings = settings or load_settings()
    service = service or make_service(settings)
    spec = service.get_interview()

    # ------------------------------------------------------------ handlers
    def on_build(
        name, profile_id, steam, plats, socials, max_price, lang, excl_tags, excl_owned, *answers
    ):
        try:
            if max_price is not None and max_price < 0:
                raise InvalidInput("最高价格不能为负数", problems=["max_price"])
            packed = {}
            for q, a in zip(spec.questions, answers, strict=True):
                packed[q.id] = list(a) if isinstance(a, list) else ([a] if a else [])
            request = ProfileRequest(
                profile_id=(profile_id or "").strip() or None,
                display_name=name or "",
                answers=packed,
                steam_id_or_url=(steam or "").strip() or None,
                filters=HardFilters(
                    platforms=[Platform(p) for p in plats or []],
                    social_modes=[SocialMode(m) for m in socials or []],
                    max_price_cents=None if max_price in (None, 0) else int(round(max_price * 100)),
                    required_language=lang or None,
                    excluded_tags=[
                        t.strip().lower() for t in (excl_tags or "").split(",") if t.strip()
                    ],
                    exclude_owned=bool(excl_owned),
                ),
            )
            profile = service.build_profile(request)
            warnings = list(getattr(service, "last_warnings", []) or [])
            return (
                render.profile_html(profile, warnings=warnings),
                profile.profile_id,
                profile.profile_id,
            )
        except Exception as err:  # noqa: BLE001 - boundary: everything becomes a visible panel
            return _error(err), gr.update(), gr.update()

    def on_load(profile_id):
        try:
            pid = (profile_id or "").strip()
            if not pid:
                raise InvalidInput("请先填写画像 ID", problems=["profile_id"])
            profile = service.get_profile(pid)
            by_q = profile.sources.answers
            values = [
                (by_q.get(q.id, []) if q.max_choices > 1 else (by_q.get(q.id) or [None])[0])
                for q in spec.questions
            ]
            f = profile.filters
            return (
                render.profile_html(profile),
                profile.display_name,
                pid,
                [p.value for p in f.platforms],
                [m.value for m in f.social_modes],
                (f.max_price_cents or 0) / 100,
                f.required_language or "",
                ", ".join(f.excluded_tags),
                f.exclude_owned,
                *values,
            )
        except Exception as err:  # noqa: BLE001
            return (_error(err), *[gr.update()] * (8 + len(spec.questions)))

    def on_recommend(profile_id, mode, top_k):
        try:
            pid = (profile_id or "").strip()
            if not pid:
                raise InvalidInput("请先在“画像”页生成或填写画像 ID", problems=["profile_id"])
            run = service.recommend(
                RecommendRequest(profile_id=pid, mode=(mode or "").strip(), top_k=int(top_k))
            )
            return render.run_html(run)
        except Exception as err:  # noqa: BLE001
            return (_error(err), *EMPTY_RUN[1:])

    def on_history(profile_id):
        try:
            runs = service.list_runs((profile_id or "").strip() or None)
            choices = [
                (
                    f"{r.created_at:%m-%d %H:%M:%S} · {r.status.value} · {'、'.join(r.titles) or '—'} · {r.profile_id}",
                    r.run_id,
                )
                for r in runs
            ]
            msg = render.note(
                "info", f"共 {len(choices)} 条已保存的运行。选择一条即可重新读取它保存的证据。"
            )
            return msg, gr.update(choices=choices, value=None)
        except Exception as err:  # noqa: BLE001
            return _error(err), gr.update(choices=[], value=None)

    def on_open_run(run_id):
        if not run_id:
            return EMPTY_RUN
        try:
            return render.run_html(service.get_run(str(run_id)))
        except Exception as err:  # noqa: BLE001
            return (_error(err), *EMPTY_RUN[1:])

    def on_stats():
        try:
            return render.hero_html(service.catalog_stats(), settings.service)
        except Exception:  # noqa: BLE001 - the header must always render
            return render.hero_html(None, settings.service)

    def on_progress(*answers):
        done = sum(1 for a in answers if a)
        return render.progress_html(done, len(answers))

    def go_recommend():
        return gr.Tabs(selected="rec")

    # ------------------------------------------------------------ layout
    with gr.Blocks(
        title="Game Gene Agent", css=render.CSS, theme=gr.themes.Base(), fill_width=True
    ) as demo:
        system_box = gr.HTML(render.hero_html(None, settings.service))

        with gr.Tabs() as tabs:
            with gr.Tab("① 建立画像", id="profile"):
                with gr.Row(equal_height=False):
                    with gr.Column(scale=7, min_width=420):
                        with gr.Group(elem_classes="gg-panel"):
                            gr.HTML(render.section_title("基本信息"))
                            with gr.Row():
                                name = gr.Textbox(
                                    label="昵称", placeholder="1–40 个字符", min_width=200
                                )
                                steam = gr.Textbox(
                                    label="Steam 资料链接或 64 位 ID（可选，需公开游戏库）",
                                    placeholder="https://steamcommunity.com/id/…",
                                    min_width=280,
                                    scale=2,
                                )
                        gr.HTML(render.section_title("访谈", "凭第一直觉选，每题必答"))
                        progress = gr.HTML(render.progress_html(0, len(spec.questions)))
                        answer_inputs = []
                        with gr.Column(elem_classes="gg-qgrid"):
                            for q in spec.questions:
                                choices = [(o.label_zh, o.id) for o in q.options]
                                if q.max_choices > 1:
                                    answer_inputs.append(
                                        gr.CheckboxGroup(
                                            choices=choices,
                                            label=q.prompt_zh,
                                            elem_classes="gg-q gg-multi",
                                        )
                                    )
                                else:
                                    answer_inputs.append(
                                        gr.Radio(
                                            choices=choices, label=q.prompt_zh, elem_classes="gg-q"
                                        )
                                    )
                        with gr.Accordion(
                            "硬性过滤条件（可选）", open=False, elem_classes="gg-acc"
                        ):
                            with gr.Row():
                                plats = gr.CheckboxGroup(
                                    PLATFORM_CHOICES, label="平台（不选 = 不限）"
                                )
                                socials = gr.CheckboxGroup(
                                    SOCIAL_CHOICES, label="社交模式（不选 = 不限）"
                                )
                            with gr.Row():
                                max_price = gr.Number(
                                    label="最高价格（0 = 不限）", value=0, minimum=0
                                )
                                lang = gr.Dropdown(LANG_CHOICES, value="", label="必须支持的语言")
                                excl_tags = gr.Textbox(
                                    label="排除的标签（英文，逗号分隔）", placeholder="horror, pvp"
                                )
                            excl_owned = gr.Checkbox(value=True, label="排除已拥有的游戏")
                    with gr.Column(scale=4, min_width=320, elem_classes="gg-side"):
                        profile_out = gr.HTML(render.profile_placeholder())
                        build_btn = gr.Button("生成 / 更新画像", variant="primary")
                        goto_btn = gr.Button("用这个画像获取推荐 →")
                        with gr.Accordion("修改已有画像", open=False, elem_classes="gg-acc"):
                            pid_in = gr.Textbox(
                                label="画像 ID（留空 = 新建）", placeholder="p-1a2b3c4d"
                            )
                            load_btn = gr.Button("读取这个画像")

            with gr.Tab("② 获取推荐", id="rec"):
                with gr.Group(elem_classes="gg-panel"), gr.Row(equal_height=True):
                    pid_rec = gr.Textbox(
                        label="画像 ID", placeholder="先在“建立画像”页生成", scale=3, min_width=200
                    )
                    mode = gr.Dropdown(
                        [(v, k) for k, v in MODE_LABELS.items()],
                        value="both",
                        label="模式（可手动输入其他值）",
                        allow_custom_value=True,
                        scale=2,
                        min_width=180,
                    )
                    top_k = gr.Slider(
                        1, 10, value=3, step=1, label="每条轨道最多几款", scale=2, min_width=200
                    )
                    rec_btn = gr.Button("获取推荐", variant="primary", scale=2, min_width=160)
                rec_summary = gr.HTML()
                rec_body = gr.HTML(
                    render.empty_state(
                        "还没有推荐结果",
                        "填写画像 ID 后点击“获取推荐”，两条轨道的结果会显示在这里。",
                    )
                )
                with gr.Accordion(
                    "执行轨迹（请求 → 分支 → 中间数据 → 保存结果）",
                    open=False,
                    elem_classes="gg-acc",
                ):
                    rec_trace = gr.Code(language="json", value="[]")

            with gr.Tab("③ 历史记录", id="history"):
                with gr.Group(elem_classes="gg-panel"):
                    with gr.Row(equal_height=True):
                        pid_hist = gr.Textbox(
                            label="按画像 ID 筛选（留空 = 全部）", scale=2, min_width=200
                        )
                        hist_pick = gr.Dropdown(
                            choices=[],
                            label="已保存的运行（时间为 UTC，新的在前）",
                            scale=5,
                            min_width=280,
                        )
                        hist_btn = gr.Button("刷新列表", scale=1, min_width=120)
                hist_msg = gr.HTML()
                hist_summary = gr.HTML()
                hist_body = gr.HTML(
                    render.empty_state(
                        "选择一条运行", "点击“刷新列表”，再从下拉框中选择要回看的运行。"
                    )
                )
                with gr.Accordion("执行轨迹", open=False, elem_classes="gg-acc"):
                    hist_trace = gr.Code(language="json", value="[]")

            with gr.Tab("④ 说明", id="help"):
                gr.HTML(render.help_html())

        profile_form = [name, pid_in, steam, plats, socials, max_price, lang, excl_tags, excl_owned]
        build_btn.click(on_build, profile_form + answer_inputs, [profile_out, pid_in, pid_rec])
        load_btn.click(
            on_load,
            [pid_in],
            [profile_out, name, pid_rec, plats, socials, max_price, lang, excl_tags, excl_owned]
            + answer_inputs,
        ).then(on_progress, answer_inputs, [progress])
        for box in answer_inputs:
            box.change(on_progress, answer_inputs, [progress], show_progress="hidden")
        goto_btn.click(go_recommend, None, [tabs])
        rec_btn.click(on_recommend, [pid_rec, mode, top_k], [rec_summary, rec_body, rec_trace])
        hist_btn.click(on_history, [pid_hist], [hist_msg, hist_pick])
        hist_pick.change(on_open_run, [hist_pick], [hist_summary, hist_body, hist_trace])
        demo.load(on_stats, None, [system_box])
    return demo
