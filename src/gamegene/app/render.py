"""[UI] Pure HTML renderers. Every dynamic string goes through ``esc`` (Steam text and
model text are untrusted input)."""

from __future__ import annotations

import html
import json
import math

from ..contracts.errors import ErrorResponse
from ..contracts.genes import GENE_ORDER, GENES
from ..contracts.models import (
    CatalogStats,
    PriceInfo,
    Recommendation,
    RecommendationRun,
    RunStatus,
    SharedGene,
    UserProfile,
)

esc = html.escape

CSS = """
/* Dark storefront look (deep navy, light-blue accent, green price), forced in both colour modes. */
.gradio-container, .gradio-container.dark, .dark {
  --gg-bg:#1b2838; --gg-bg2:#16202d; --gg-panel:#1f2c3d; --gg-panel2:#24364b; --gg-line:#2f445c;
  --gg-text:#c7d5e0; --gg-dim:#8f98a0; --gg-white:#ffffff; --gg-blue:#66c0f4; --gg-blue2:#1a9fff;
  --gg-green:#a4d007; --gg-green-bg:#4c6b22; --gg-gold:#e5b143; --gg-red:#e0544c;
  --body-background-fill:var(--gg-bg) !important; --background-fill-primary:var(--gg-panel) !important;
  --background-fill-secondary:var(--gg-bg2) !important; --block-background-fill:var(--gg-panel) !important;
  --border-color-primary:var(--gg-line) !important; --border-color-accent:var(--gg-blue) !important;
  --block-border-color:transparent !important; --block-border-width:0px !important;
  --body-text-color:var(--gg-text) !important; --body-text-color-subdued:var(--gg-dim) !important;
  --block-label-text-color:var(--gg-dim) !important; --block-title-text-color:var(--gg-white) !important;
  --block-label-background-fill:transparent !important; --block-title-background-fill:transparent !important;
  --block-info-text-color:var(--gg-dim) !important; --block-shadow:none !important;
  --input-background-fill:#0f1822 !important; --input-background-fill-focus:#0f1822 !important;
  --input-border-color:var(--gg-line) !important; --input-border-color-focus:var(--gg-blue) !important;
  --input-placeholder-color:#5c6b7a !important; --input-shadow:none !important; --input-shadow-focus:none !important;
  --button-primary-background-fill:linear-gradient(90deg,#06bfff 0%,#2d73ff 100%) !important;
  --button-primary-background-fill-hover:linear-gradient(90deg,#3fd0ff 0%,#4a88ff 100%) !important;
  --button-primary-text-color:#fff !important; --button-primary-border-color:transparent !important;
  --button-secondary-background-fill:var(--gg-panel2) !important;
  --button-secondary-background-fill-hover:#2f4764 !important;
  --button-secondary-text-color:var(--gg-blue) !important; --button-secondary-border-color:transparent !important;
  --checkbox-label-background-fill:var(--gg-bg2) !important; --checkbox-label-background-fill-hover:var(--gg-panel2) !important;
  --checkbox-label-background-fill-selected:rgba(102,192,244,.18) !important;
  --checkbox-label-border-color:var(--gg-line) !important; --checkbox-label-border-color-selected:var(--gg-blue) !important;
  --checkbox-label-text-color:var(--gg-text) !important; --checkbox-label-text-color-selected:var(--gg-white) !important;
  --checkbox-background-color:#0f1822 !important; --checkbox-background-color-selected:var(--gg-blue2) !important;
  --checkbox-border-color:#41566e !important; --checkbox-border-color-selected:var(--gg-blue2) !important;
  --checkbox-label-shadow:none !important; --slider-color:var(--gg-blue) !important;
  --color-accent:var(--gg-blue) !important; --color-accent-soft:rgba(102,192,244,.15) !important;
  --link-text-color:var(--gg-blue) !important; --link-text-color-hover:#fff !important;
  --table-even-background-fill:var(--gg-panel) !important; --table-odd-background-fill:var(--gg-bg2) !important;
  --code-background-fill:#0f1822 !important; --panel-background-fill:var(--gg-bg2) !important;
  --neutral-50:#c7d5e0; --neutral-100:#c7d5e0; --neutral-200:#8f98a0; --neutral-700:#2f445c; --neutral-800:#1f2c3d;
  --neutral-900:#16202d; --neutral-950:#0f1822;
  color:var(--gg-text);
}
body, gradio-app { background:radial-gradient(1200px 500px at 20% -10%,#2a475e 0%,#1b2838 55%) fixed, #1b2838 !important; }
.gradio-container { max-width:1180px !important; font-family:"Motiva Sans","Noto Sans SC","PingFang SC","Microsoft YaHei",Arial,sans-serif !important; }
.gradio-container h3 { color:#fff; font-weight:500; letter-spacing:.5px; margin:18px 0 8px;
  padding-left:10px; border-left:3px solid var(--gg-blue); font-size:1.02em }
footer { opacity:.45 }

/* hero */
.gg-hero{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;padding:18px 22px;
  border-radius:6px;background:linear-gradient(120deg,#171a21 0%,#1f3a52 60%,#27567a 100%);
  box-shadow:0 6px 24px rgba(0,0,0,.35)}
.gg-hero .t{font-size:1.55em;font-weight:700;color:#fff;letter-spacing:1px}
.gg-hero .t b{color:var(--gg-blue);font-weight:700}
.gg-hero .s{color:var(--gg-dim);font-size:.9em;margin-top:2px}
.gg-pills{display:flex;gap:8px;flex-wrap:wrap}
.gg-pill{font-size:.78em;padding:4px 10px;border-radius:3px;background:rgba(0,0,0,.3);color:var(--gg-text);white-space:nowrap}
.gg-pill b{color:#fff}.gg-pill.warn{background:rgba(229,177,67,.16);color:var(--gg-gold)}

/* tabs: storefront nav bar */
.gradio-container .tab-wrapper, .gradio-container .tab-nav{background:linear-gradient(90deg,rgba(62,103,150,.9),rgba(58,120,177,.75));
  border-radius:4px;border:0 !important;padding:0 6px;margin-bottom:14px}
.gradio-container .tab-wrapper::after, .gradio-container .tab-container::after{display:none !important}
.gradio-container button[role=tab]{color:#e5e5e5 !important;font-weight:500;padding:10px 16px !important;border:0 !important;background:transparent !important}
.gradio-container button[role=tab]:hover{color:#fff !important;background:rgba(255,255,255,.12) !important}
.gradio-container button[role=tab].selected{color:#fff !important;background:rgba(0,0,0,.28) !important;border-radius:3px}
.gradio-container button[role=tab].selected::after{background:var(--gg-blue) !important}
.gradio-container .tabitem{border:0 !important;padding:0 !important;background:transparent !important}

/* forms */
.gradio-container .block{border-radius:4px !important}
.gradio-container button.primary{font-weight:600;letter-spacing:1px;border-radius:3px !important;box-shadow:0 2px 10px rgba(6,191,255,.25)}
.gradio-container button.secondary{border-radius:3px !important}
.gg-q{background:var(--gg-panel) !important;padding:12px 14px !important;margin-bottom:2px}
.gg-q span[data-testid=block-info]{color:#fff !important;font-size:.98em;font-weight:500}
.gg-q label{border-radius:3px !important;transition:background .12s,border-color .12s}
.gg-q label.selected{box-shadow:inset 0 0 0 1px var(--gg-blue)}

.gradio-container .label-wrap, .gradio-container .label-wrap span, .gradio-container .label-wrap .icon{color:var(--gg-text) !important;opacity:1 !important}
.gradio-container .label-wrap:hover span{color:#fff !important}

/* notes */
.gg-note{padding:10px 14px;border-radius:4px;background:rgba(0,0,0,.22);margin:6px 0;line-height:1.55;border-left:3px solid var(--gg-line);color:var(--gg-text)}
.gg-note.ok{border-left-color:var(--gg-green)}.gg-note.warn{border-left-color:var(--gg-gold)}
.gg-note.err{border-left-color:var(--gg-red);background:rgba(224,84,76,.12)}.gg-note.info{border-left-color:var(--gg-blue)}
.gg-note code{background:rgba(0,0,0,.35);padding:1px 6px;border-radius:3px;color:var(--gg-blue)}
.gg-note b{color:#fff}.gg-kv{font-size:.85em;color:var(--gg-dim)}.gg-dim{color:var(--gg-dim);font-size:.82em}

/* profile */
.gg-profile{display:grid;grid-template-columns:minmax(260px,340px) 1fr;gap:22px;align-items:center;
  background:linear-gradient(135deg,#1f2c3d,#16202d);border-radius:6px;padding:18px 20px;margin-top:8px}
@media(max-width:760px){.gg-profile{grid-template-columns:1fr}}
.gg-radar{width:100%;height:auto;display:block}
.gg-radar .grid{fill:none;stroke:#2f445c;stroke-width:1}.gg-radar .axis{stroke:#2f445c;stroke-width:1}
.gg-radar .area{fill:rgba(102,192,244,.28);stroke:var(--gg-blue);stroke-width:2;stroke-linejoin:round}
.gg-radar .dot{fill:#fff;stroke:var(--gg-blue);stroke-width:2}.gg-radar text{fill:var(--gg-text);font-size:12px}
.gg-genes{display:grid;grid-template-columns:5.2em 1fr 7.2em;gap:9px 12px;align-items:center}
.gg-genes>span:first-child,.gg-genes>span:nth-child(3n+1){color:#fff;font-size:.9em}
.gg-bar{height:8px;border-radius:2px;background:#0f1822;position:relative;overflow:hidden}
.gg-bar>i{position:absolute;left:0;top:0;bottom:0;background:linear-gradient(90deg,#1a9fff,#66c0f4)}

/* chips */
.gg-chips{display:flex;flex-wrap:wrap;gap:5px}
.gg-chip{font-size:.74em;padding:2px 8px;border-radius:2px;background:rgba(103,193,245,.16);color:#67c1f5;white-space:nowrap;line-height:1.7}
.gg-chip.plain{background:rgba(255,255,255,.08);color:var(--gg-text)}
.gg-chip.g-A{background:var(--gg-green-bg);color:#d2efa9}
.gg-chip.g-B{background:#2a5d84;color:#bfe3fb}
.gg-chip.g-C{background:#6b5320;color:#f1d596}
.gg-chip.track-same_track{background:rgba(255,255,255,.1);color:#fff}
.gg-chip.track-cross_track{background:linear-gradient(90deg,#7b3fe4,#c44bd6);color:#fff}

/* game cards */
.gg-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:16px}
.gg-card{background:linear-gradient(180deg,#22344a 0%,#16202d 100%);border-radius:5px;overflow:hidden;display:flex;flex-direction:column;
  box-shadow:0 4px 14px rgba(0,0,0,.35);transition:transform .15s,box-shadow .15s}
.gg-card:hover{transform:translateY(-3px);box-shadow:0 10px 26px rgba(0,0,0,.5),0 0 0 1px rgba(102,192,244,.45)}
.gg-cap{position:relative;aspect-ratio:460/215;background:linear-gradient(135deg,#2a475e,#1b2838) center/cover no-repeat}
.gg-cap::after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,0) 55%,rgba(22,32,45,.95) 100%)}
.gg-score{position:absolute;right:10px;top:10px;z-index:1;min-width:46px;padding:5px 6px;border-radius:4px;text-align:center;
  color:#fff;font-weight:700;font-size:1.25em;line-height:1.05;box-shadow:0 2px 8px rgba(0,0,0,.5)}
.gg-score small{display:block;font-size:.5em;font-weight:500;opacity:.9;letter-spacing:1px}
.gg-score.s-high{background:#4c9a2a}.gg-score.s-mid{background:#3a78b1}.gg-score.s-low{background:#7a6a3a}
.gg-cap .gg-track{position:absolute;left:10px;top:10px;z-index:1}
.gg-card .b{padding:12px 14px 14px;display:flex;flex-direction:column;gap:9px;flex:1}
.gg-card h4{margin:0;font-size:1.12em;font-weight:500;color:#fff}
.gg-card h4 a{color:#fff !important;text-decoration:none}.gg-card h4 a:hover{color:var(--gg-blue) !important}
.gg-headline{color:var(--gg-text);font-size:.93em;line-height:1.5}
.gg-reason{background:rgba(0,0,0,.22);border-radius:3px;padding:8px 10px;font-size:.88em;line-height:1.55}
.gg-reason q{display:block;margin:5px 0 6px;padding-left:8px;border-left:2px solid var(--gg-blue);color:#9fb4c7;font-style:italic;quotes:"“" "”"}
.gg-reason .src{display:flex;gap:6px;align-items:center}
.gg-reason .src a{color:var(--gg-dim) !important}
.gg-barrier{margin:0;padding-left:1.1em;font-size:.84em;color:#c9a96a;line-height:1.5}
.gg-foot{margin-top:auto;display:flex;justify-content:space-between;align-items:center;gap:8px;padding-top:6px}
.gg-price{background:var(--gg-green-bg);color:#beee11;font-size:.86em;padding:3px 10px;border-radius:2px;white-space:nowrap}
.gg-price s{color:#8aa55a;margin-right:6px;font-size:.9em}
.gg-price.off{background:#000;color:var(--gg-dim)}
"""

_STATUS = {
    RunStatus.OK: ("ok", "已生成推荐"),
    RunStatus.CLOSEST_ONLY: ("warn", "没有足够强的匹配，仅给出最接近的候选"),
    RunStatus.NO_MATCH: ("warn", "无匹配，本次不做推荐"),
    RunStatus.ERROR: ("err", "运行出错（已保存的数据未受影响）"),
}
_CONF = {"high": "高", "medium": "中", "low": "低"}
_TRACK = {"same_track": "同类轨", "cross_track": "其他轨"}


def note(kind: str, text: str) -> str:
    return f'<div class="gg-note {esc(kind)}">{text}</div>'


def error_html(err: ErrorResponse) -> str:
    problems = err.details.get("problems") or []
    extra = "".join(f"<li>{esc(str(p))}</li>" for p in problems)
    retry = "　可稍后重试。" if err.retryable else ""
    return note(
        "err",
        f"<b>{esc(err.code)}</b>（HTTP {err.http_status}）：{esc(err.message)}{retry}"
        + (f"<ul>{extra}</ul>" if extra else ""),
    )


def price_html(price: PriceInfo | None, is_free: bool) -> str:
    if is_free:
        return '<span class="gg-price">免费开玩</span>'
    if price is None:
        return '<span class="gg-price off">价格未知</span>'
    now = f"{esc(price.currency)} {price.final_cents / 100:.2f}"
    if price.discount_percent:
        return (
            f'<span class="gg-price">-{price.discount_percent}%　'
            f"<s>{price.initial_cents / 100:.2f}</s>{now}</span>"
        )
    return f'<span class="gg-price">{now}</span>'


def radar_svg(profile: UserProfile) -> str:
    """Nine-axis radar of the user's gene targets (0-4)."""
    cx, cy, radius = 170.0, 150.0, 100.0
    n = len(GENE_ORDER)

    def point(i: int, r: float) -> tuple[float, float]:
        angle = -math.pi / 2 + 2 * math.pi * i / n
        return cx + r * math.cos(angle), cy + r * math.sin(angle)

    def ring(r: float) -> str:
        return " ".join(f"{x:.1f},{y:.1f}" for x, y in (point(i, r) for i in range(n)))

    parts = [f'<polygon class="grid" points="{ring(radius * k / 4)}"/>' for k in range(1, 5)]
    area, dots = [], []
    for i, g in enumerate(GENE_ORDER):
        ex, ey = point(i, radius)
        parts.append(f'<line class="axis" x1="{cx}" y1="{cy}" x2="{ex:.1f}" y2="{ey:.1f}"/>')
        lx, ly = point(i, radius + 20)
        anchor = "middle" if abs(lx - cx) < 12 else ("start" if lx > cx else "end")
        parts.append(
            f'<text x="{lx:.1f}" y="{ly + 4:.1f}" text-anchor="{anchor}">{esc(GENES[g].label_zh)}</text>'
        )
        px, py = point(i, radius * profile.genes[g].target / 4)
        area.append(f"{px:.1f},{py:.1f}")
        dots.append(f'<circle class="dot" cx="{px:.1f}" cy="{py:.1f}" r="3"/>')
    parts.append(f'<polygon class="area" points="{" ".join(area)}"/>')
    return (
        '<svg class="gg-radar" viewBox="0 0 340 300" role="img" aria-label="九维基因雷达图">'
        + "".join(parts + dots)
        + "</svg>"
    )


def profile_html(
    profile: UserProfile, revision: int | None = None, warnings: list[str] | None = None
) -> str:
    rows = []
    for g in GENE_ORDER:
        pref = profile.genes[g]
        rows.append(
            f'<span title="{esc(GENES[g].question, quote=True)}">{esc(GENES[g].label_zh)}</span>'
            f'<span class="gg-bar"><i style="width:{pref.target / 4 * 100:.0f}%;'
            f'opacity:{0.35 + 0.65 * pref.weight:.2f}"></i></span>'
            f'<span class="gg-dim">{pref.target:.1f} / 4 · 权重 {pref.weight:.2f}</span>'
        )
    tags = "".join(
        f'<span class="gg-chip">{esc(t)}</span>'
        for t, _ in sorted(profile.familiar_tags.items(), key=lambda kv: (-kv[1], kv[0]))[:16]
    )
    f = profile.filters
    filt = [
        f"平台 {', '.join(p.value for p in f.platforms) or '不限'}",
        f"社交 {', '.join(m.value for m in f.social_modes) or '不限'}",
        f"最高价格 {'不限' if f.max_price_cents is None else f'{f.max_price_cents / 100:.2f}'}",
        f"语言 {f.required_language or '不限'}",
        f"排除标签 {', '.join(f.excluded_tags) or '无'}",
        f"排除已拥有 {'是' if f.exclude_owned else '否'}（已拥有 {len(profile.owned_appids)} 款）",
    ]
    filt_html = "".join(f'<span class="gg-chip plain">{esc(x)}</span>' for x in filt)
    rev = f" · 第 {revision} 版" if revision else ""
    head = note(
        "ok",
        f"画像已保存：<b>{esc(profile.display_name)}</b>　ID <code>{esc(profile.profile_id)}</code>{rev}",
    )
    warn = "".join(note("warn", esc(w)) for w in (warnings or []))
    return (
        f"{head}{warn}"
        f'<div class="gg-profile"><div>{radar_svg(profile)}</div><div>'
        f'<div class="gg-genes">{"".join(rows)}</div>'
        f'<p class="gg-kv" style="margin:14px 0 6px">熟悉的类型（决定同类轨 / 其他轨）</p>'
        f'<div class="gg-chips">{tags or "—"}</div>'
        f'<p class="gg-kv" style="margin:12px 0 6px">硬性过滤</p><div class="gg-chips">{filt_html}</div>'
        "</div></div>"
    )


def _reason_html(text: str, shared: SharedGene | None) -> str:
    if shared is None:
        return f'<div class="gg-reason">{esc(text)}</div>'
    ref = shared.source_ref
    src = esc(shared.source_type.value.replace("_", " "))
    if ref.startswith(("https://", "http://")):
        src = f'<a href="{esc(ref, quote=True)}" target="_blank" rel="noopener noreferrer">{src} ↗</a>'
    return (
        f'<div class="gg-reason"><span class="gg-chip">{esc(GENES[shared.gene].label_zh)}</span> '
        f"{esc(text)}<q>{esc(shared.quote)}</q>"
        f'<div class="src"><span class="gg-chip g-{shared.grade.value}">证据 {shared.grade.value}</span>'
        f'<span class="gg-dim">{src}</span></div></div>'
    )


def card_html(rec: Recommendation) -> str:
    by_gene = {s.gene: s for s in rec.shared_genes}
    reasons = "".join(_reason_html(r.text, by_gene.get(r.gene)) for r in rec.explanation.reasons)
    barriers = "".join(f"<li>{esc(b)}</li>" for b in rec.barriers)
    bg = ""
    if rec.header_image and rec.header_image.startswith("https://"):
        url = esc(rec.header_image, quote=True).replace("(", "%28").replace(")", "%29")
        bg = f" style=\"background-image:url('{url}'),linear-gradient(135deg,#2a475e,#1b2838)\""
    level = "high" if rec.score >= 0.82 else ("mid" if rec.score >= 0.72 else "low")
    mismatch = (
        note("warn", "<b>主要差异　</b>" + esc(rec.explanation.mismatch))
        if rec.explanation.mismatch
        else ""
    )
    by = "模型" if rec.explanation.generated_by == "llm" else "模板"
    link = esc(rec.store_url, quote=True)
    return (
        f'<div class="gg-card"><div class="gg-cap"{bg}>'
        f'<span class="gg-chip gg-track track-{rec.track.value}">{_TRACK[rec.track.value]}</span>'
        f'<div class="gg-score s-{level}">{rec.score * 100:.0f}<small>匹配</small></div></div>'
        f'<div class="b"><h4><a href="{link}" target="_blank" rel="noopener noreferrer">{esc(rec.name)}</a></h4>'
        f'<div class="gg-chips"><span class="gg-chip plain">置信度 {_CONF[rec.confidence.value]}</span>'
        f'<span class="gg-chip plain">基因覆盖 {rec.coverage * 100:.0f}%</span>'
        f'<span class="gg-chip plain">类型重合 {rec.surface_overlap * 100:.0f}%</span></div>'
        f'<div class="gg-headline">{esc(rec.explanation.headline)}</div>{reasons}{mismatch}'
        + (f'<ul class="gg-barrier">{barriers}</ul>' if barriers else "")
        + f'<div class="gg-foot"><span class="gg-dim">解释来源：{by}</span>{price_html(rec.price, rec.is_free)}</div>'
        "</div></div>"
    )


def cards_html(recs: list[Recommendation], empty: str) -> str:
    if not recs:
        return note("info", esc(empty))
    return f'<div class="gg-cards">{"".join(card_html(r) for r in recs)}</div>'


def run_html(run: RecommendationRun) -> tuple[str, str, str, str]:
    """-> (status banner, same-track html, cross-track html, trace json)."""
    kind, label = _STATUS[run.status]
    drops = "，".join(f"{esc(k)} {v}" for k, v in run.filter_drops.items()) or "无"
    llm = ""
    if run.llm:
        llm = (
            f"　模型 {esc(run.llm.provider)}/{esc(run.llm.model)}：调用 {run.llm.calls}，"
            f"重试 {run.llm.retries}，回退 {run.llm.fallbacks}"
        )
    banner = note(
        kind,
        f"<b>{label}</b>　{esc(run.message)}<br><span class='gg-kv'>运行 <code>{esc(run.run_id)}</code>"
        f" · 画像 <code>{esc(run.profile_id)}</code> 第 {run.profile_revision} 版"
        f" · 候选 {run.candidates_total} → 过滤后 {run.candidates_after_filters}（剔除：{drops}）{llm}</span>",
    )
    if run.error:
        banner += error_html(ErrorResponse.model_validate(run.error))
    if run.closest is not None:
        banner += cards_html([run.closest], "")
    same = cards_html(run.same_track, "同类轨没有通过证据门槛的推荐。")
    cross = cards_html(run.cross_track, "其他轨没有通过证据门槛的推荐。")
    trace = json.dumps([t.model_dump(mode="json") for t in run.trace], ensure_ascii=False, indent=2)
    return banner, same, cross, trace


def hero_html(stats: CatalogStats | None, service: str) -> str:
    pills = []
    if stats is not None:
        verified = stats.by_status.get("verified", 0)
        pills.append(
            f'<span class="gg-pill">目录 <b>{verified}</b> / {stats.total} 款已核验</span>'
        )
        if stats.source == "fixture":
            pills.append(
                '<span class="gg-pill warn" title="基因等级、证据句、价格均为占位数据，不可用于最终演示">合成样例目录</span>'
            )
    if service == "demo":
        pills.append(
            '<span class="gg-pill warn" title="简化实现：无 Steam 库导入、无完整硬过滤、无模型解释">演示服务</span>'
        )
    return (
        '<div class="gg-hero"><div><div class="t">GAME <b>GENE</b> AGENT</div>'
        '<div class="s">按九维“设计基因”而不是类型标签推荐 Steam 游戏 · 每条推荐都附带可核验的证据句</div></div>'
        f'<div class="gg-pills">{"".join(pills)}</div></div>'
    )
