"""The frozen nine-dimension game gene schema (GENE_SCHEMA_VERSION).

This file is the single source of truth for gene ids, labels and level anchors.
Prompts, the UI and docs/02-gene-schema.md are all derived from it.
Changing anything here requires an ADR (see docs/adr/) and a schema version bump.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

GENE_SCHEMA_VERSION = "1.0"

MIN_LEVEL = 0
MAX_LEVEL = 4


class GeneId(StrEnum):
    CHALLENGE = "challenge"
    STRATEGY = "strategy"
    PACE = "pace"
    PROGRESSION = "progression"
    EXPLORATION = "exploration"
    CREATION = "creation"
    NARRATIVE = "narrative"
    IMMERSION = "immersion"
    SOCIAL = "social"


GENE_ORDER: tuple[GeneId, ...] = tuple(GeneId)

LEVEL_MEANING: dict[int, str] = {
    0: "absent: the game does not contain this at all",
    1: "minor: present but incidental, players rarely mention it",
    2: "supporting: a real part of the game, but not why people play it",
    3: "major: one of the main reasons people play it",
    4: "defining: the game is built around it; removing it removes the game",
}


@dataclass(frozen=True)
class GeneSpec:
    id: GeneId
    label_en: str
    label_zh: str
    question: str  # the one question an annotator answers for this gene
    low_anchor: str  # what level 0-1 looks like
    high_anchor: str  # what level 4 looks like
    grounding: str  # which published framework the dimension comes from
    typical_signals: tuple[str, ...]  # words/tags that often (not always) indicate it


GENES: dict[GeneId, GeneSpec] = {
    GeneId.CHALLENGE: GeneSpec(
        GeneId.CHALLENGE,
        "Execution challenge",
        "操作挑战",
        "How much does success depend on practiced skill, precision and overcoming failure?",
        "Cannot really fail; no skill ceiling (walking sim, idle game).",
        "Demanding execution, repeated failure is the core loop (precision platformer, soulslike).",
        "Quantic Foundry: Mastery/Challenge; MDA aesthetic: Challenge",
        ("difficult", "souls-like", "precision platformer", "bullet hell", "skill ceiling"),
    ),
    GeneId.STRATEGY: GeneSpec(
        GeneId.STRATEGY,
        "Strategic depth",
        "策略深度",
        "How much does success depend on planning, optimisation and weighing trade-offs?",
        "Decisions are obvious or purely reactive.",
        "Long-horizon planning with many interacting systems (4X, deckbuilder, factory builder).",
        "Quantic Foundry: Mastery/Strategy",
        ("strategy", "tactical", "deckbuilding", "resource management", "turn-based"),
    ),
    GeneId.PACE: GeneSpec(
        GeneId.PACE,
        "Pace and intensity",
        "节奏强度",
        "How fast and intense is moment-to-moment play (time pressure, action density)?",
        "Untimed, contemplative, the game waits for the player.",
        "Constant real-time pressure and high action density (arena shooter, action roguelike).",
        "Quantic Foundry: Action/Excitement + Destruction; MDA aesthetic: Sensation",
        ("fast-paced", "action", "hack and slash", "shooter", "relaxing (inverse)"),
    ),
    GeneId.PROGRESSION: GeneSpec(
        GeneId.PROGRESSION,
        "Progression and accumulation",
        "成长积累",
        "How much of the appeal is getting stronger, unlocking, collecting and completing over time?",
        "Nothing persists or grows; every session starts equal.",
        "Long unlock trees, loot, levels, meta-progression or completion lists drive play.",
        "Quantic Foundry: Achievement/Power + Completion",
        ("rpg", "loot", "unlocks", "meta-progression", "collectathon", "grind"),
    ),
    GeneId.EXPLORATION: GeneSpec(
        GeneId.EXPLORATION,
        "Exploration and discovery",
        "探索发现",
        "How much is play driven by finding unknown places, secrets and mechanics on your own?",
        "Linear, fully signposted, nothing to find off the path.",
        "Curiosity is the main drive; knowledge of the world is the reward (metroidvania, open world).",
        "Quantic Foundry: Creativity/Discovery; MDA aesthetic: Discovery",
        ("exploration", "open world", "metroidvania", "secrets", "mystery"),
    ),
    GeneId.CREATION: GeneSpec(
        GeneId.CREATION,
        "Creation and expression",
        "创造表达",
        "How much can players build, design or express something that is their own?",
        "No customisation; every player ends with the same result.",
        "The player's own constructions are the content (sandbox, builder, automation).",
        "Quantic Foundry: Creativity/Design; MDA aesthetic: Expression",
        (
            "building",
            "sandbox",
            "crafting",
            "base building",
            "automation",
            "character customization",
        ),
    ),
    GeneId.NARRATIVE: GeneSpec(
        GeneId.NARRATIVE,
        "Narrative",
        "叙事",
        "How much is play driven by authored story, characters and dialogue?",
        "No story beyond a premise.",
        "Story and characters are the reason to play; mechanics serve them (narrative RPG, visual novel).",
        "Quantic Foundry: Immersion/Story; MDA aesthetic: Narrative",
        ("story rich", "choices matter", "visual novel", "great writing", "dialogue"),
    ),
    GeneId.IMMERSION: GeneSpec(
        GeneId.IMMERSION,
        "World and atmosphere",
        "世界沉浸",
        "How much does the game rely on atmosphere, sense of place and being someone/somewhere else?",
        "Abstract presentation; theme is interchangeable.",
        "Atmosphere and world are central to the experience, independent of plot.",
        "Quantic Foundry: Immersion/Fantasy; MDA aesthetic: Fantasy + Sensation",
        ("atmospheric", "immersive", "great soundtrack", "lore-rich", "beautiful"),
    ),
    GeneId.SOCIAL: GeneSpec(
        GeneId.SOCIAL,
        "Social dependence",
        "社交依赖",
        "How much does the core experience depend on playing with or against other people?",
        "Strictly single-player.",
        "The game barely works alone; co-operation or competition is the content.",
        "Quantic Foundry: Social/Competition + Community; MDA aesthetic: Fellowship",
        ("co-op", "multiplayer", "pvp", "mmo", "party game"),
    ),
}

assert set(GENES) == set(GENE_ORDER), "every gene needs a spec"
