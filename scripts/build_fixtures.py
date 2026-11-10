"""Regenerate src/gamegene/resources/{fixture_catalog,interview_v1}.json.

Everything produced here is SYNTHETIC development data: gene levels are rough
hand estimates, evidence quotes are placeholders marked "[synthetic fixture]",
prices are made up. Real records come only from Workflow 2.

    uv run python scripts/build_fixtures.py
"""

from __future__ import annotations

import json
from pathlib import Path

from gamegene.contracts import GENE_ORDER, GENES, GameRecord, InterviewSpec

OUT = Path(__file__).resolve().parents[1] / "src" / "gamegene" / "resources"
NOW = "2026-11-10T00:00:00Z"
W, M, L = "windows", "mac", "linux"
ALL = [W, M, L]

# appid, name, levels (gene order; None = unknown), genres, tags, platforms, social, cents
GAMES = [
    (
        1145360,
        "Hades",
        [3, 2, 4, 3, 1, 1, 3, 3, 0],
        ["action", "indie", "rpg"],
        ["action roguelike", "roguelike", "hack and slash", "story rich", "great soundtrack"],
        [W, M],
        ["single"],
        2499,
    ),
    (
        646570,
        "Slay the Spire",
        [3, 4, 0, 3, 1, 1, 0, 1, 0],
        ["indie", "strategy"],
        ["roguelike deckbuilder", "card game", "turn-based", "roguelike", "deckbuilding"],
        ALL,
        ["single"],
        2499,
    ),
    (
        413150,
        "Stardew Valley",
        [1, 2, 1, 3, 2, 3, 2, 3, 2],
        ["indie", "rpg", "simulation"],
        ["farming sim", "life sim", "pixel graphics", "relaxing", "multiplayer"],
        ALL,
        ["single", "coop"],
        1499,
    ),
    (
        427520,
        "Factorio",
        [2, 4, 2, 3, 1, 4, 0, 1, 2],
        ["casual", "indie", "simulation", "strategy"],
        ["automation", "base building", "resource management", "sandbox", "crafting"],
        ALL,
        ["single", "coop"],
        3500,
    ),
    (
        367520,
        "Hollow Knight",
        [4, 1, 3, 2, 4, 0, 2, 4, 0],
        ["action", "adventure", "indie"],
        ["metroidvania", "souls-like", "platformer", "difficult", "atmospheric"],
        ALL,
        ["single"],
        1499,
    ),
    (
        504230,
        "Celeste",
        [4, 1, 3, 1, 1, 0, 3, 2, 0],
        ["action", "adventure", "indie"],
        ["precision platformer", "difficult", "pixel graphics", "great soundtrack", "platformer"],
        ALL,
        ["single"],
        1999,
    ),
    (
        753640,
        "Outer Wilds",
        [1, 2, 1, 0, 4, 0, 3, 4, 0],
        ["action", "adventure"],
        ["exploration", "space", "mystery", "open world", "atmospheric"],
        [W],
        ["single"],
        2499,
    ),
    (
        632470,
        "Disco Elysium",
        [0, 2, 0, 2, 2, 1, 4, 4, 0],
        ["rpg"],
        ["story rich", "choices matter", "detective", "crpg", "great writing"],
        [W, M],
        ["single"],
        3999,
    ),
    (
        620,
        "Portal 2",
        [2, 3, 1, 0, 1, None, 3, 3, 2],
        ["action", "adventure"],
        ["puzzle", "co-op", "first-person", "funny", "sci-fi"],
        ALL,
        ["single", "coop"],
        999,
    ),
    (
        105600,
        "Terraria",
        [3, 1, 3, 4, 4, 4, 0, 2, 2],
        ["action", "adventure", "indie", "rpg"],
        ["sandbox", "survival", "crafting", "open world survival craft", "2d"],
        ALL,
        ["single", "coop", "pvp"],
        999,
    ),
    (
        289070,
        "Sid Meier's Civilization VI",
        [1, 4, 0, 3, 2, 2, None, 2, 2],
        ["strategy"],
        ["turn-based strategy", "4x", "historical", "grand strategy", "multiplayer"],
        ALL,
        ["single", "coop", "pvp"],
        5999,
    ),
    (
        588650,
        "Dead Cells",
        [4, 1, 4, 3, 2, 0, 0, 2, 0],
        ["action", "indie"],
        ["roguelite", "metroidvania", "souls-like", "pixel graphics", "action roguelike"],
        ALL,
        ["single"],
        2499,
    ),
    (
        590380,
        "Into the Breach",
        [3, 4, 0, 2, 0, 0, 1, 1, 0],
        ["indie", "rpg", "simulation", "strategy"],
        ["turn-based tactics", "mechs", "roguelike", "tactical", "pixel graphics"],
        ALL,
        ["single"],
        1499,
    ),
    (
        548430,
        "Deep Rock Galactic",
        [2, 1, 3, 3, 3, 1, 0, 3, 4],
        ["action"],
        ["co-op", "fps", "class-based", "mining", "procedural generation"],
        [W],
        ["single", "coop"],
        2999,
    ),
    (
        294100,
        "RimWorld",
        [2, 4, 1, 2, 1, 4, 3, 2, 0],
        ["indie", "simulation", "strategy"],
        ["colony sim", "base building", "survival", "management", "sandbox"],
        ALL,
        ["single"],
        3499,
    ),
    (
        264710,
        "Subnautica",
        [1, 1, 1, 3, 4, 3, 2, 4, 0],
        ["adventure", "indie"],
        ["survival", "open world", "underwater", "exploration", "crafting"],
        [W, M],
        ["single"],
        2999,
    ),
    (
        999001,
        "Fixture Obscure Game",
        [None, 3, None, None, None, None, 2, None, 0],
        ["indie"],
        ["experimental"],
        [W],
        ["single"],
        499,
    ),
]
GRADES = ["A", "B", "C"]
SOURCE = {"A": "store_description", "B": "wiki", "C": "store_review"}


def game(appid, name, levels, genres, tags, platforms, social, cents) -> dict:
    genes, evidence = {}, []
    for i, (gene, level) in enumerate(zip(GENE_ORDER, levels, strict=True)):
        if level is None:
            genes[gene.value] = {"level": None, "unknown_reason": "no_evidence"}
            continue
        grade = GRADES[(i + appid) % 3]
        eid = f"ev-{gene.value}-1"
        evidence.append(
            {
                "evidence_id": eid,
                "gene": gene.value,
                "quote": f"[synthetic fixture] {name}: {GENES[gene].label_en.lower()} is at level {level} of 4.",
                "source_type": SOURCE[grade],
                "source_ref": f"fixture://{appid}/{gene.value}",
                "grade": grade,
                "match_score": 1.0,
                "verified_at": NOW,
            }
        )
        genes[gene.value] = {"level": level, "confidence": "high", "evidence_ids": [eid]}
    known = sum(v is not None for v in levels)
    return {
        "appid": appid,
        "name": name,
        "status": "verified" if known >= 5 else "partial",
        "review_note": None if known >= 5 else "fewer than 5 genes have verified evidence",
        "store": {
            "short_description": f"[synthetic fixture] placeholder description of {name}.",
            "header_image": f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg",
            "store_url": f"https://store.steampowered.com/app/{appid}/",
            "genres": genres,
            "tags": tags,
            "platforms": platforms,
            "social_modes": social,
            "languages": ["english", "simplified chinese"],
            "is_free": False,
            "price": {
                "currency": "USD",
                "final_cents": cents,
                "initial_cents": cents,
                "discount_percent": 0,
                "fetched_at": NOW,
            },
            "review_score_desc": None,
            "total_reviews": None,
            "fetched_at": NOW,
        },
        "genes": genes,
        "evidence": evidence,
        "annotation": {
            "provider": "fixture",
            "model": "hand-written",
            "prompt_version": "fixture",
            "annotated_at": NOW,
        },
    }


def opt(oid, zh, en, **deltas):
    return {"id": oid, "label_zh": zh, "label_en": en, "gene_deltas": deltas}


def tag_opt(oid, zh, en, *tags):
    return {"id": oid, "label_zh": zh, "label_en": en, "tags": list(tags)}


def q(qid, zh, en, *options):
    return {"id": qid, "kind": "gene", "prompt_zh": zh, "prompt_en": en, "options": list(options)}


INTERVIEW = {
    "version": "interview-v1",
    "questions": [
        q(
            "q01_failure",
            "同一个地方连续失败五次，你会？",
            "You fail the same spot five times. You…",
            opt("a", "再来，直到练会为止", "retry until I master it", challenge=1.5, pace=0.5),
            opt("b", "停下来换个思路或打法", "stop and rethink my approach", strategy=1.0),
            opt("c", "希望游戏别这样卡我", "wish the game would not block me", challenge=-1.5),
        ),
        q(
            "q02_evening",
            "理想的一晚游戏时间更像？",
            "Your ideal evening of play is…",
            opt(
                "a",
                "慢慢推演一个长远的大计划",
                "slowly working out a long plan",
                strategy=1.5,
                pace=-1.0,
            ),
            opt("b", "手心出汗、节奏紧凑的连续战斗", "sweaty, fast, back-to-back fights", pace=1.5),
            opt(
                "c",
                "不赶时间，四处走走看看",
                "unhurried wandering",
                pace=-1.5,
                immersion=0.5,
                exploration=0.5,
            ),
        ),
        q(
            "q03_satisfaction",
            "哪一刻最让你满足？",
            "Which moment satisfies you most?",
            opt(
                "a",
                "角色或装备终于成型，数值碾压",
                "my build finally comes together",
                progression=1.5,
            ),
            opt(
                "b",
                "发现一个没人提示过的隐藏区域",
                "finding a hidden area nobody pointed to",
                exploration=1.5,
            ),
            opt("c", "自己搭的东西运转起来了", "something I built starts working", creation=1.5),
        ),
        q(
            "q04_story",
            "你怎么看游戏里的剧情？",
            "How do you feel about story in games?",
            opt(
                "a",
                "我就是为了故事和角色来的",
                "story and characters are why I play",
                narrative=2.0,
            ),
            opt("b", "有点背景交代就够了", "a bit of context is enough"),
            opt("c", "最好别打断我玩", "please do not interrupt my play", narrative=-1.5),
        ),
        q(
            "q05_people",
            "你更喜欢和谁一起玩？",
            "Who do you prefer to play with?",
            opt("a", "一个人", "alone", social=-2.0),
            opt("b", "和朋友合作", "co-operating with friends", social=1.5),
            opt("c", "和别人一较高下", "competing against others", social=2.0, challenge=0.5),
        ),
        q(
            "q06_world",
            "氛围、美术和音乐对你有多重要？",
            "How much do atmosphere, art and music matter?",
            opt(
                "a",
                "最重要，我想沉进那个世界",
                "most of all; I want to sink into the world",
                immersion=2.0,
            ),
            opt("b", "有当然好，但不是重点", "nice to have, not the point", immersion=0.5),
            opt("c", "玩法好就行，画面无所谓", "mechanics are all I need", immersion=-1.0),
        ),
        q(
            "q07_question_mark",
            "地图边缘有个没标记的山洞，你会？",
            "There is an unmarked cave at the map edge. You…",
            opt("a", "马上去，主线可以等", "go now; the main quest can wait", exploration=1.5),
            opt("b", "顺路的话看一眼", "look if it is on my way"),
            opt(
                "c", "告诉我主线往哪走就行", "just tell me where the main path is", exploration=-1.5
            ),
        ),
        q(
            "q08_freedom",
            "你想要多少自由度？",
            "How much freedom do you want?",
            opt("a", "给我工具，我自己造", "give me tools and let me build", creation=2.0),
            opt(
                "b",
                "能搭配自己的流派和配装就好",
                "enough to craft my own build",
                creation=0.5,
                progression=0.5,
                strategy=0.5,
            ),
            opt(
                "c",
                "我想要设计师打磨好的体验",
                "I want a crafted, authored experience",
                creation=-1.5,
            ),
        ),
        q(
            "q09_long_term",
            "什么让你长期玩下去？",
            "What keeps you playing for months?",
            opt("a", "解锁、收集、全成就", "unlocks, collections, completion", progression=1.5),
            opt(
                "b",
                "我自己的技术在变强",
                "my own skill getting better",
                challenge=1.0,
                progression=-0.5,
            ),
            opt(
                "c",
                "每局从头开始也没关系，好玩就行",
                "starting fresh each time is fine",
                progression=-1.5,
            ),
        ),
        q(
            "q10_problem",
            "你更享受哪种难题？",
            "Which kind of problem do you enjoy?",
            opt("a", "多个系统之间的权衡与优化", "trade-offs across many systems", strategy=1.5),
            opt(
                "b", "考验反应和手感的", "reflexes and feel", pace=1.0, challenge=0.5, strategy=-1.0
            ),
            opt("c", "轻松一点，别太费脑", "something light", strategy=-1.5, challenge=-0.5),
        ),
        {
            "id": "q11_familiar",
            "kind": "tags",
            "min_choices": 1,
            "max_choices": 4,
            "prompt_zh": "你平时最常玩哪几类游戏？（选 1–4 项，用来区分“同类轨”和“其他轨”）",
            "prompt_en": "Which kinds of games do you play most? (pick 1-4; separates same-track from cross-track)",
            "options": [
                tag_opt(
                    "roguelike",
                    "肉鸽 / 动作肉鸽",
                    "Roguelike / action roguelike",
                    "roguelike",
                    "action roguelike",
                    "roguelite",
                    "hack and slash",
                ),
                tag_opt(
                    "strategy",
                    "策略 / 战棋 / 卡牌",
                    "Strategy / tactics / card",
                    "strategy",
                    "turn-based strategy",
                    "turn-based tactics",
                    "4x",
                    "card game",
                    "deckbuilding",
                    "roguelike deckbuilder",
                ),
                tag_opt("rpg", "角色扮演", "RPG", "rpg", "crpg", "jrpg", "action rpg"),
                tag_opt(
                    "sim",
                    "模拟 / 建造 / 经营",
                    "Simulation / building / management",
                    "simulation",
                    "base building",
                    "management",
                    "automation",
                    "colony sim",
                    "farming sim",
                    "life sim",
                ),
                tag_opt(
                    "platformer",
                    "平台跳跃 / 银河城",
                    "Platformer / metroidvania",
                    "platformer",
                    "metroidvania",
                    "precision platformer",
                    "souls-like",
                ),
                tag_opt(
                    "story",
                    "剧情 / 冒险 / 解谜",
                    "Story / adventure / puzzle",
                    "story rich",
                    "adventure",
                    "puzzle",
                    "visual novel",
                    "choices matter",
                    "mystery",
                ),
                tag_opt(
                    "survival",
                    "生存 / 沙盒 / 开放世界",
                    "Survival / sandbox / open world",
                    "survival",
                    "sandbox",
                    "crafting",
                    "open world",
                    "open world survival craft",
                    "exploration",
                ),
                tag_opt(
                    "shooter",
                    "射击 / 多人合作",
                    "Shooter / co-op",
                    "fps",
                    "shooter",
                    "co-op",
                    "multiplayer",
                    "action",
                ),
            ],
        },
    ],
}


def main() -> None:
    games = [game(*row) for row in GAMES]
    for g in games:
        GameRecord.model_validate(g)
    InterviewSpec.model_validate(INTERVIEW)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "fixture_catalog.json").write_text(
        json.dumps(
            {"note": "SYNTHETIC development data, not real evidence", "games": games},
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    (OUT / "interview_v1.json").write_text(
        json.dumps(INTERVIEW, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(games)} games and {len(INTERVIEW['questions'])} questions to {OUT}")


if __name__ == "__main__":
    main()
