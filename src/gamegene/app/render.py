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
/* Dark storefront look, forced in both colour modes. Layout is centred and fluid. */
.gradio-container, .gradio-container.dark, .dark {
  --gg-bg:#1b2838; --gg-bg2:#16202d; --gg-panel:#1e2b3c; --gg-panel2:#263a52; --gg-line:#2f445c; --gg-ink:#0e151e;
  --gg-text:#c7d5e0; --gg-dim:#8b9aa9; --gg-blue:#66c0f4; --gg-blue2:#1a9fff;
  --gg-green:#a4d007; --gg-green-bg:#4c6b22; --gg-gold:#e5b143; --gg-red:#e0544c; --gg-violet:#a06bf0;
  --body-background-fill:var(--gg-bg) !important; --background-fill-primary:var(--gg-panel) !important;
  --background-fill-secondary:var(--gg-bg2) !important; --block-background-fill:transparent !important;
  --border-color-primary:var(--gg-line) !important; --border-color-accent:var(--gg-blue) !important;
  --block-border-color:transparent !important; --block-border-width:0px !important; --block-padding:0px !important;
  --body-text-color:var(--gg-text) !important; --body-text-color-subdued:var(--gg-dim) !important;
  --block-label-text-color:var(--gg-dim) !important; --block-title-text-color:var(--gg-text) !important;
  --block-label-background-fill:transparent !important; --block-title-background-fill:transparent !important;
  --block-info-text-color:var(--gg-dim) !important; --block-shadow:none !important;
  --block-title-text-size:13px !important; --block-title-text-weight:500 !important;
  --input-background-fill:var(--gg-ink) !important; --input-background-fill-focus:var(--gg-ink) !important;
  --input-border-color:var(--gg-line) !important; --input-border-color-focus:var(--gg-blue) !important;
  --input-placeholder-color:#566575 !important; --input-shadow:none !important; --input-shadow-focus:0 0 0 2px rgba(102,192,244,.25) !important;
  --input-text-size:15px !important; --input-padding:10px 12px !important; --input-radius:6px !important;
  --button-primary-background-fill:linear-gradient(90deg,#06bfff 0%,#2d73ff 100%) !important;
  --button-primary-background-fill-hover:linear-gradient(90deg,#3fd0ff 0%,#4a88ff 100%) !important;
  --button-primary-text-color:#fff !important; --button-primary-border-color:transparent !important;
  --button-secondary-background-fill:var(--gg-panel2) !important; --button-secondary-background-fill-hover:#30496a !important;
  --button-secondary-text-color:var(--gg-blue) !important; --button-secondary-border-color:transparent !important;
  --checkbox-label-background-fill:var(--gg-ink) !important; --checkbox-label-background-fill-hover:#172330 !important;
  --checkbox-label-background-fill-selected:rgba(26,159,255,.2) !important;
  --checkbox-label-border-color:transparent !important; --checkbox-label-border-color-hover:var(--gg-line) !important;
  --checkbox-label-border-color-selected:var(--gg-blue) !important; --checkbox-label-border-width:1px !important;
  --checkbox-label-text-color:var(--gg-text) !important; --checkbox-label-text-color-selected:#fff !important;
  --checkbox-label-padding:9px 12px !important; --checkbox-label-gap:8px !important; --checkbox-label-shadow:none !important;
  --checkbox-background-color:#1b2838 !important; --checkbox-background-color-selected:var(--gg-blue2) !important;
  --checkbox-border-color:#46607c !important; --checkbox-border-color-selected:var(--gg-blue2) !important;
  --slider-color:var(--gg-blue) !important; --color-accent:var(--gg-blue) !important; --color-accent-soft:rgba(102,192,244,.15) !important;
  --link-text-color:var(--gg-blue) !important; --link-text-color-hover:#fff !important;
  --code-background-fill:var(--gg-ink) !important; --panel-background-fill:transparent !important;
  --layout-gap:14px !important; --form-gap-width:14px !important;
  --neutral-50:#c7d5e0; --neutral-100:#c7d5e0; --neutral-200:#8b9aa9; --neutral-700:#2f445c; --neutral-800:#1e2b3c;
  --neutral-900:#16202d; --neutral-950:#0e151e;
  color:var(--gg-text);
}
body, gradio-app { background:radial-gradient(1400px 520px at 50% -120px,#2a475e 0%,#1b2838 60%) fixed, #1b2838 !important; }
.gradio-container { max-width:1440px !important; width:100% !important; margin:0 auto !important;
  padding:18px clamp(12px,3vw,40px) 32px !important; font-size:15px; line-height:1.6;
  font-family:Inter,"HarmonyOS Sans SC","PingFang SC","Microsoft YaHei UI","Microsoft YaHei","Noto Sans SC",system-ui,-apple-system,"Segoe UI",sans-serif !important; }
.gradio-container .main, .gradio-container .wrap, .gradio-container .contain { max-width:none !important; width:100% !important; }
.gradio-container .form { background:transparent !important; border:0 !important; box-shadow:none !important; gap:14px !important; }
.gradio-container .block { overflow:visible !important; }
footer { opacity:.4 }

/* header */
.gg-hero{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;padding:16px 22px;border-radius:10px;
  background:linear-gradient(110deg,#171a21 0%,#1d3449 55%,#2a5a80 100%);box-shadow:0 8px 28px rgba(0,0,0,.35)}
.gg-brand{display:flex;align-items:center;gap:14px}
.gg-logo{width:42px;height:42px;border-radius:10px;display:grid;place-items:center;font-weight:800;font-size:15px;color:#0e151e;letter-spacing:.5px;
  background:linear-gradient(135deg,#66c0f4,#a4d007)}
.gg-hero .t{font-size:21px;font-weight:700;color:#fff;letter-spacing:.6px;line-height:1.2}
.gg-hero .t b{color:var(--gg-blue)}
.gg-hero .s{color:#a9b8c6;font-size:13.5px;margin-top:3px}
.gg-pills{display:flex;gap:8px;flex-wrap:wrap}
.gg-pill{font-size:12.5px;padding:5px 11px;border-radius:999px;background:rgba(0,0,0,.32);color:var(--gg-text);white-space:nowrap}
.gg-pill b{color:#fff}.gg-pill.warn{background:rgba(229,177,67,.16);color:var(--gg-gold)}

/* tabs as step navigation */
.gradio-container .tab-wrapper{background:transparent !important;border:0 !important;padding:0 !important;margin:16px 0 18px !important;height:auto !important}
.gradio-container .tab-container{gap:8px !important;height:auto !important;overflow:visible !important}
.gradio-container .tab-container::after{display:none !important}
.gradio-container button[role=tab]{font-size:15px !important;font-weight:500;color:var(--gg-dim) !important;padding:10px 20px !important;height:auto !important;
  border:1px solid var(--gg-line) !important;border-radius:999px !important;background:rgba(14,21,30,.45) !important;transition:all .15s}
.gradio-container button[role=tab]:hover{color:#fff !important;border-color:var(--gg-blue) !important}
.gradio-container button[role=tab].selected{color:#fff !important;border-color:transparent !important;
  background:linear-gradient(90deg,#1a9fff,#2d73ff) !important;box-shadow:0 4px 14px rgba(26,159,255,.3)}
.gradio-container button[role=tab].selected::after{display:none !important}
.gradio-container .tabitem{border:0 !important;padding:0 !important;background:transparent !important}

/* panels and forms */
.gg-panel{background:var(--gg-panel) !important;border-radius:10px !important;padding:18px 20px !important;box-shadow:0 2px 10px rgba(0,0,0,.2)}
.gg-h{display:flex;align-items:baseline;gap:10px;margin:0 0 12px;color:#fff;font-size:17px;font-weight:600}
.gg-h small{font-size:13px;font-weight:400;color:var(--gg-dim)}
.gg-h .n{font-size:12.5px;font-weight:600;color:#0e151e;background:var(--gg-blue);border-radius:999px;padding:1px 9px}
.gg-h.cross .n{background:var(--gg-violet);color:#fff}
.gradio-container button.primary{font-size:15.5px !important;font-weight:600;letter-spacing:.5px;border-radius:8px !important;min-height:46px;
  box-shadow:0 4px 16px rgba(6,191,255,.25)}
.gradio-container button.secondary{border-radius:8px !important;min-height:42px;font-size:14.5px !important}
.gradio-container .label-wrap, .gradio-container .label-wrap span, .gradio-container .label-wrap .icon{color:var(--gg-text) !important;opacity:1 !important}
.gradio-container .gg-acc{background:var(--gg-panel) !important;border-radius:10px !important;padding:12px 18px !important}

/* interview: fluid grid of question cards, options stacked for easy scanning */
.gg-qgrid{counter-reset:q}
.gg-qgrid, .gg-qgrid > .form{display:grid !important;grid-template-columns:repeat(auto-fit,minmax(min(100%,330px),1fr));gap:14px !important;
  background:transparent !important;border:0 !important;overflow:visible !important}
.gg-qgrid > .form{grid-column:1/-1}
.gg-q{background:var(--gg-panel) !important;border-radius:10px !important;padding:14px 16px 16px !important;counter-increment:q;
  box-shadow:0 2px 10px rgba(0,0,0,.2);min-width:0 !important}
.gg-q span[data-testid=block-info]{display:flex;gap:10px;align-items:flex-start;color:#fff !important;font-size:15.5px !important;font-weight:600 !important;
  line-height:1.45;margin-bottom:10px !important}
.gg-q span[data-testid=block-info]::before{content:counter(q,decimal-leading-zero);flex:none;font-size:12px;font-weight:700;color:var(--gg-blue);
  background:rgba(102,192,244,.14);border-radius:6px;padding:2px 7px;margin-top:1px}
.gg-q .wrap{display:flex !important;flex-direction:column !important;gap:8px !important}
.gg-q label{width:100%;border-radius:8px !important;font-size:14.5px !important;line-height:1.45;transition:background .12s,border-color .12s}
.gg-q.gg-multi{grid-column:1/-1}
.gg-q.gg-multi .wrap{flex-direction:row !important;flex-wrap:wrap !important}
.gg-q.gg-multi label{width:auto}
.gg-side{position:sticky;top:14px;align-self:flex-start}
.gg-progress{display:flex;align-items:center;gap:12px;font-size:13.5px;color:var(--gg-dim)}
.gg-progress .bar{flex:1;height:6px;border-radius:3px;background:var(--gg-ink);overflow:hidden}
.gg-progress .bar i{display:block;height:100%;background:linear-gradient(90deg,#1a9fff,#a4d007);transition:width .2s}
.gg-progress b{color:#fff}

/* notes */
.gg-note{padding:11px 14px;border-radius:8px;background:rgba(14,21,30,.55);margin:0 0 10px;line-height:1.6;border-left:3px solid var(--gg-line);font-size:14.5px}
.gg-note.ok{border-left-color:var(--gg-green)}.gg-note.warn{border-left-color:var(--gg-gold)}
.gg-note.err{border-left-color:var(--gg-red);background:rgba(224,84,76,.13)}.gg-note.info{border-left-color:var(--gg-blue)}
.gg-note code{background:rgba(0,0,0,.4);padding:1px 7px;border-radius:4px;color:var(--gg-blue);font-size:13px}
.gg-note b{color:#fff}.gg-note ul{margin:6px 0 0;padding-left:1.2em}
.gg-dim{color:var(--gg-dim);font-size:13px}
.gg-empty{text-align:center;padding:44px 20px;border:1px dashed var(--gg-line);border-radius:10px;color:var(--gg-dim)}
.gg-empty .big{font-size:17px;color:#fff;font-weight:600;margin-bottom:6px}

/* profile panel */
.gg-pcard{background:linear-gradient(160deg,#22344a,#16202d);border-radius:10px;padding:18px 20px;box-shadow:0 4px 16px rgba(0,0,0,.3)}
.gg-pcard .who{display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap}
.gg-pcard .who b{color:#fff;font-size:18px}
.gg-radar{width:100%;max-width:360px;height:auto;display:block;margin:4px auto 6px}
.gg-radar .grid{fill:none;stroke:#2f445c;stroke-width:1}.gg-radar .axis{stroke:#2f445c;stroke-width:1}
.gg-radar .area{fill:rgba(102,192,244,.28);stroke:var(--gg-blue);stroke-width:2;stroke-linejoin:round}
.gg-radar .dot{fill:#fff;stroke:var(--gg-blue);stroke-width:2}.gg-radar text{fill:var(--gg-text);font-size:12.5px}
.gg-genes{display:grid;grid-template-columns:auto 1fr auto;gap:8px 12px;align-items:center;font-size:13.5px}
.gg-genes .nm{color:#fff}.gg-genes .v{color:var(--gg-dim);font-variant-numeric:tabular-nums;text-align:right}
.gg-bar{height:7px;border-radius:4px;background:var(--gg-ink);position:relative;overflow:hidden}
.gg-bar>i{position:absolute;left:0;top:0;bottom:0;border-radius:4px;background:linear-gradient(90deg,#1a9fff,#66c0f4)}
.gg-sub{font-size:12.5px;color:var(--gg-dim);margin:14px 0 6px;letter-spacing:.5px}

/* chips */
.gg-chips{display:flex;flex-wrap:wrap;gap:6px}
.gg-chip{font-size:12.5px;padding:2px 9px;border-radius:4px;background:rgba(103,193,245,.16);color:#7cc8f6;white-space:nowrap;line-height:1.7}
.gg-chip.plain{background:rgba(255,255,255,.07);color:var(--gg-text)}
.gg-chip.warn{background:rgba(229,177,67,.14);color:#e8c57c;white-space:normal}
.gg-chip.g-A{background:var(--gg-green-bg);color:#d8f3ae}.gg-chip.g-B{background:#2a5d84;color:#c9e8fc}.gg-chip.g-C{background:#6b5320;color:#f3dba3}
.gg-chip.track-same_track{background:rgba(14,21,30,.75);color:#fff}
.gg-chip.track-cross_track{background:linear-gradient(90deg,#7b3fe4,#c44bd6);color:#fff}

/* run summary strip */
.gg-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin:0 0 12px}
.gg-stat{background:var(--gg-panel);border-radius:10px;padding:12px 14px}
.gg-stat .k{font-size:12.5px;color:var(--gg-dim)}
.gg-stat .v{font-size:24px;font-weight:700;color:#fff;line-height:1.25;font-variant-numeric:tabular-nums}
.gg-stat .v small{font-size:13px;font-weight:400;color:var(--gg-dim);margin-left:4px}
.gg-stat.ok .v{color:var(--gg-green)}.gg-stat.warn .v{color:var(--gg-gold)}.gg-stat.err .v{color:var(--gg-red)}

/* game rows: capsule on the left, reasons spread across the remaining width */
.gg-sec{margin:22px 0 0}
.gg-rows{display:flex;flex-direction:column;gap:14px}
.gg-row{display:grid;grid-template-columns:minmax(240px,320px) 1fr;background:linear-gradient(100deg,#22344a 0%,#182535 70%);border-radius:10px;overflow:hidden;
  box-shadow:0 4px 16px rgba(0,0,0,.3);transition:transform .15s,box-shadow .15s}
.gg-row:hover{transform:translateY(-2px);box-shadow:0 10px 28px rgba(0,0,0,.45),0 0 0 1px rgba(102,192,244,.4)}
@media(max-width:820px){.gg-row{grid-template-columns:1fr}}
.gg-left{display:flex;flex-direction:column;position:relative;background:rgba(14,21,30,.35)}
.gg-cap{position:relative;flex:1;min-height:150px;background:linear-gradient(135deg,#2f5674,#1b2838) center/cover no-repeat}
.gg-cap .ph{position:absolute;inset:0;display:grid;place-items:center;color:rgba(255,255,255,.75);font-weight:700;font-size:18px;text-align:center;padding:0 14px;letter-spacing:.5px}
.gg-cap .img{position:absolute;inset:0;background:center/cover no-repeat}
.gg-cap .gg-track{position:absolute;left:10px;top:10px;z-index:1}
.gg-buy{position:absolute;left:0;right:0;bottom:0;display:flex;align-items:center;justify-content:space-between;gap:10px;padding:26px 12px 10px;
  background:linear-gradient(180deg,rgba(14,21,30,0),rgba(14,21,30,.92) 60%)}
.gg-panel button.primary{align-self:flex-end}
.gg-price{background:var(--gg-green-bg);color:#beee11;font-size:14px;padding:4px 11px;border-radius:4px;white-space:nowrap;font-variant-numeric:tabular-nums}
.gg-price s{color:#8aa55a;margin-right:6px;font-size:.9em}.gg-price.off{background:rgba(0,0,0,.4);color:var(--gg-dim)}
.gg-store{font-size:13.5px;color:var(--gg-blue) !important;text-decoration:none;white-space:nowrap}.gg-store:hover{color:#fff !important}
.gg-main{padding:16px 20px 18px;display:flex;flex-direction:column;gap:11px;min-width:0}
.gg-top{display:flex;justify-content:space-between;gap:14px;align-items:flex-start}
.gg-top h4{margin:0 0 6px;font-size:20px;font-weight:600;color:#fff;line-height:1.25}
.gg-top h4 a{color:#fff !important;text-decoration:none}.gg-top h4 a:hover{color:var(--gg-blue) !important}
.gg-score{flex:none;min-width:62px;padding:7px 8px;border-radius:8px;text-align:center;color:#fff;font-weight:700;font-size:26px;line-height:1.05;font-variant-numeric:tabular-nums}
.gg-score small{display:block;font-size:11.5px;font-weight:500;opacity:.9;letter-spacing:1px;margin-top:3px}
.gg-score.s-high{background:#4c9a2a}.gg-score.s-mid{background:#3a78b1}.gg-score.s-low{background:#7a6a3a}
.gg-headline{color:#e3edf5;font-size:15.5px;line-height:1.55}
.gg-reasons{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,230px),1fr));gap:10px}
.gg-reason{background:rgba(14,21,30,.55);border-radius:8px;padding:11px 13px;font-size:14px;line-height:1.6;display:flex;flex-direction:column;gap:7px}
.gg-reason .g{display:flex;justify-content:space-between;align-items:center;gap:8px}
.gg-reason .g b{color:#fff;font-size:14.5px}
.gg-reason q{display:block;padding-left:10px;border-left:2px solid var(--gg-blue);color:#a9bccd;font-size:13.5px;quotes:"“" "”"}
.gg-reason .src{margin-top:auto;font-size:12.5px;color:var(--gg-dim)}.gg-reason .src a{color:var(--gg-dim) !important}
.gg-meta{font-size:12.5px;color:var(--gg-dim)}

/* help page */
.gg-help{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:14px}
.gg-help .gg-panel h5{margin:0 0 8px;color:#fff;font-size:16px}
.gg-help p{margin:6px 0;font-size:14.5px}
"""

_STATUS = {
    RunStatus.OK: ("ok", "已推荐"),
    RunStatus.CLOSEST_ONLY: ("warn", "仅最接近"),
    RunStatus.NO_MATCH: ("warn", "无匹配"),
    RunStatus.ERROR: ("err", "出错"),
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


def section_title(text: str, hint: str = "", count: int | None = None, kind: str = "") -> str:
    n = f'<span class="n">{count}</span>' if count is not None else ""
    small = f"<small>{esc(hint)}</small>" if hint else ""
    return f'<div class="gg-h {esc(kind)}">{esc(text)}{n}{small}</div>'


def empty_state(title: str, text: str) -> str:
    return f'<div class="gg-empty"><div class="big">{esc(title)}</div>{esc(text)}</div>'


def progress_html(done: int, total: int) -> str:
    pct = 0 if total == 0 else round(done / total * 100)
    return (
        f'<div class="gg-progress"><span>访谈进度 <b>{done}</b> / {total}</span>'
        f'<span class="bar"><i style="width:{pct}%"></i></span></div>'
    )


def radar_svg(profile: UserProfile) -> str:
    """Nine-axis radar of the user's gene targets (0-4)."""
    cx, cy, radius = 180.0, 150.0, 100.0
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
        lx, ly = point(i, radius + 18)
        anchor = "middle" if abs(lx - cx) < 12 else ("start" if lx > cx else "end")
        parts.append(
            f'<text x="{lx:.1f}" y="{ly + 4:.1f}" text-anchor="{anchor}">{esc(GENES[g].label_zh)}</text>'
        )
        px, py = point(i, radius * profile.genes[g].target / 4)
        area.append(f"{px:.1f},{py:.1f}")
        dots.append(f'<circle class="dot" cx="{px:.1f}" cy="{py:.1f}" r="3"/>')
    parts.append(f'<polygon class="area" points="{" ".join(area)}"/>')
    return (
        '<svg class="gg-radar" viewBox="0 0 360 300" role="img" aria-label="九维基因雷达图">'
        + "".join(parts + dots)
        + "</svg>"
    )


def profile_placeholder() -> str:
    return (
        '<div class="gg-pcard">'
        + section_title("你的基因画像")
        + empty_state("还没有画像", "完成左侧访谈后点击“生成画像”，九维雷达图会显示在这里。")
        + "</div>"
    )


def profile_html(
    profile: UserProfile, revision: int | None = None, warnings: list[str] | None = None
) -> str:
    rows = []
    for g in GENE_ORDER:
        pref = profile.genes[g]
        rows.append(
            f'<span class="nm" title="{esc(GENES[g].question, quote=True)}">{esc(GENES[g].label_zh)}</span>'
            f'<span class="gg-bar"><i style="width:{pref.target / 4 * 100:.0f}%;'
            f'opacity:{0.35 + 0.65 * pref.weight:.2f}"></i></span>'
            f'<span class="v" title="权重 {pref.weight:.2f}">{pref.target:.1f}</span>'
        )
    tags = "".join(
        f'<span class="gg-chip">{esc(t)}</span>'
        for t, _ in sorted(profile.familiar_tags.items(), key=lambda kv: (-kv[1], kv[0]))[:14]
    )
    f = profile.filters
    filt = []
    if f.platforms:
        filt.append("平台 " + " / ".join(p.value for p in f.platforms))
    if f.social_modes:
        filt.append("社交 " + " / ".join(m.value for m in f.social_modes))
    if f.max_price_cents is not None:
        filt.append(f"不高于 {f.max_price_cents / 100:.2f}")
    if f.required_language:
        filt.append("语言 " + f.required_language)
    if f.excluded_tags:
        filt.append("排除 " + ", ".join(f.excluded_tags))
    if f.exclude_owned:
        filt.append(f"排除已拥有（{len(profile.owned_appids)} 款）")
    filt_html = "".join(f'<span class="gg-chip plain">{esc(x)}</span>' for x in filt) or "不限"
    rev = f" · 第 {revision} 版" if revision else ""
    warn = "".join(note("warn", esc(w)) for w in (warnings or []))
    return (
        f'{warn}<div class="gg-pcard"><div class="who"><b>{esc(profile.display_name)}</b>'
        f'<span class="gg-dim">画像 ID <code>{esc(profile.profile_id)}</code>{rev}</span></div>'
        f"{radar_svg(profile)}"
        f'<div class="gg-genes">{"".join(rows)}</div>'
        f'<div class="gg-sub">熟悉的类型 · 决定同类轨 / 其他轨</div><div class="gg-chips">{tags or "—"}</div>'
        f'<div class="gg-sub">硬性过滤</div><div class="gg-chips">{filt_html}</div></div>'
    )


def _reason_html(text: str, shared: SharedGene | None) -> str:
    if shared is None:
        return f'<div class="gg-reason">{esc(text)}</div>'
    ref = shared.source_ref
    src = esc(shared.source_type.value.replace("_", " "))
    if ref.startswith(("https://", "http://")):
        src = f'<a href="{esc(ref, quote=True)}" target="_blank" rel="noopener noreferrer">{src} ↗</a>'
    return (
        f'<div class="gg-reason"><div class="g"><b>{esc(GENES[shared.gene].label_zh)}</b>'
        f'<span class="gg-chip g-{shared.grade.value}">证据 {shared.grade.value} 级</span></div>'
        f"<div>{esc(text)}</div><q>{esc(shared.quote)}</q>"
        f'<div class="src">来源：{src}</div></div>'
    )


def card_html(rec: Recommendation) -> str:
    by_gene = {s.gene: s for s in rec.shared_genes}
    reasons = "".join(_reason_html(r.text, by_gene.get(r.gene)) for r in rec.explanation.reasons)
    barriers = "".join(f'<span class="gg-chip warn">{esc(b)}</span>' for b in rec.barriers)
    img = ""
    if rec.header_image and rec.header_image.startswith("https://"):
        url = esc(rec.header_image, quote=True).replace("(", "%28").replace(")", "%29")
        img = f'<div class="img" style="background-image:url(\'{url}\')"></div>'
    level = "high" if rec.score >= 0.82 else ("mid" if rec.score >= 0.72 else "low")
    mismatch = (
        note("warn", "<b>主要差异　</b>" + esc(rec.explanation.mismatch))
        if rec.explanation.mismatch
        else ""
    )
    by = "模型生成" if rec.explanation.generated_by == "llm" else "模板生成"
    link = esc(rec.store_url, quote=True)
    return (
        '<article class="gg-row"><div class="gg-left">'
        f'<div class="gg-cap"><div class="ph">{esc(rec.name)}</div>{img}'
        f'<span class="gg-chip gg-track track-{rec.track.value}">{_TRACK[rec.track.value]}</span></div>'
        f'<div class="gg-buy">{price_html(rec.price, rec.is_free)}'
        f'<a class="gg-store" href="{link}" target="_blank" rel="noopener noreferrer">在 Steam 查看 ↗</a></div></div>'
        f'<div class="gg-main"><div class="gg-top"><div>'
        f'<h4><a href="{link}" target="_blank" rel="noopener noreferrer">{esc(rec.name)}</a></h4>'
        f'<div class="gg-chips"><span class="gg-chip plain">置信度 {_CONF[rec.confidence.value]}</span>'
        f'<span class="gg-chip plain">基因覆盖 {rec.coverage * 100:.0f}%</span>'
        f'<span class="gg-chip plain">类型重合 {rec.surface_overlap * 100:.0f}%</span></div></div>'
        f'<div class="gg-score s-{level}">{rec.score * 100:.0f}<small>匹配度</small></div></div>'
        f'<div class="gg-headline">{esc(rec.explanation.headline)}</div>'
        f'<div class="gg-reasons">{reasons}</div>{mismatch}'
        + (f'<div class="gg-chips">{barriers}</div>' if barriers else "")
        + f'<div class="gg-meta">解释：{by}</div></div></article>'
    )


def cards_html(recs: list[Recommendation], empty: str) -> str:
    if not recs:
        return note("info", esc(empty))
    return f'<div class="gg-rows">{"".join(card_html(r) for r in recs)}</div>'


def _stat(key: str, value: object, unit: str = "", kind: str = "") -> str:
    small = f"<small>{esc(unit)}</small>" if unit else ""
    return (
        f'<div class="gg-stat {kind}"><div class="k">{esc(key)}</div>'
        f'<div class="v">{esc(str(value))}{small}</div></div>'
    )


def run_html(run: RecommendationRun) -> tuple[str, str, str]:
    """-> (summary strip + status, recommendation sections, trace json)."""
    kind, label = _STATUS[run.status]
    dropped = run.candidates_total - run.candidates_after_filters
    stats = [
        _stat("结果", label, kind=kind),
        _stat("候选游戏", run.candidates_total, "款"),
        _stat("通过硬过滤", run.candidates_after_filters, f"剔除 {dropped}"),
        _stat("同类轨", len(run.same_track), "款"),
        _stat("其他轨", len(run.cross_track), "款"),
    ]
    if run.llm:
        stats.append(_stat("模型调用", run.llm.calls, f"回退 {run.llm.fallbacks}"))
    drops = "，".join(f"{esc(k)} {v}" for k, v in run.filter_drops.items())
    detail = (
        f"运行 <code>{esc(run.run_id)}</code>　画像 <code>{esc(run.profile_id)}</code> 第 {run.profile_revision} 版"
        + (f"　剔除原因：{drops}" if drops else "")
        + (f"　模型 {esc(run.llm.provider)}/{esc(run.llm.model)}" if run.llm else "")
    )
    summary = f'<div class="gg-stats">{"".join(stats)}</div>' + note(
        kind, f"{esc(run.message)}<br><span class='gg-dim'>{detail}</span>"
    )
    if run.error:
        summary += error_html(ErrorResponse.model_validate(run.error))
    body = ""
    if run.closest is not None:
        body += (
            '<section class="gg-sec">'
            + section_title("最接近的候选", "未达到推荐门槛，仅供参考")
            + cards_html([run.closest], "")
            + "</section>"
        )
    mode = run.request.mode
    if run.status in (RunStatus.OK, RunStatus.CLOSEST_ONLY):
        if mode in ("both", "same_track"):
            body += (
                '<section class="gg-sec">'
                + section_title("同类轨", "符合你熟悉的类型", len(run.same_track))
                + cards_html(run.same_track, "同类轨没有通过证据门槛的推荐。")
                + "</section>"
            )
        if mode in ("both", "cross_track"):
            body += (
                '<section class="gg-sec">'
                + section_title(
                    "其他轨", "表层类型不同，设计基因相近", len(run.cross_track), "cross"
                )
                + cards_html(run.cross_track, "其他轨没有通过证据门槛的推荐。")
                + "</section>"
            )
    trace = json.dumps([t.model_dump(mode="json") for t in run.trace], ensure_ascii=False, indent=2)
    return summary, body, trace


def help_html() -> str:
    return (
        '<div class="gg-help">'
        '<div class="gg-panel"><h5>证据等级</h5>'
        '<p><span class="gg-chip g-A">A</span> 官方文本（商店描述、官方文档）中逐字可查。</p>'
        '<p><span class="gg-chip g-B">B</span> Wiki 中逐字可查，或至少两条评测佐证。</p>'
        '<p><span class="gg-chip g-C">C</span> 单条评测、模糊匹配，或由标签推断。</p></div>'
        '<div class="gg-panel"><h5>推荐门槛</h5>'
        "<p>匹配度 ≥ 72，并且至少一个共同基因有 A 或 B 级证据。</p>"
        "<p>达不到时只给出“最接近的候选”并说明差异，或明确不推荐。</p></div>"
        '<div class="gg-panel"><h5>同类轨 / 其他轨</h5>'
        "<p>按游戏表层标签与你熟悉类型的重合度划分：≥ 30% 为同类轨，否则为其他轨。</p>"
        "<p>两条轨道使用同一套九维基因计算匹配度。</p></div>"
        '<div class="gg-panel"><h5>九维基因</h5>'
        f'<div class="gg-chips">{"".join(_gene_chip(g) for g in GENE_ORDER)}</div>'
        "<p>每个维度 0–4 级；没有通过核验的证据时记为“未知”，不参与匹配。</p></div>"
        "</div>"
    )


def _gene_chip(gene) -> str:
    return f'<span class="gg-chip" title="{esc(GENES[gene].question, quote=True)}">{esc(GENES[gene].label_zh)}</span>'


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
        '<div class="gg-hero"><div class="gg-brand"><div class="gg-logo">GG</div><div>'
        '<div class="t">Game <b>Gene</b> Agent</div>'
        '<div class="s">按九维“设计基因”推荐 Steam 游戏，每条推荐都附带可核验的证据句</div></div></div>'
        f'<div class="gg-pills">{"".join(pills)}</div></div>'
    )
