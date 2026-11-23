import pytest

from app.algorithms.hard_filters import DropReason, apply_hard_filters
from app.algorithms.profile_fusion import LibraryGeneSignal, fuse_profile
from app.algorithms.questionnaire import build_questionnaire_preferences
from app.algorithms.retrieval import TrackResultKind, retrieve_candidates
from app.algorithms.similarity import calculate_similarity, is_recommendation_eligible
from app.algorithms.tracks import assign_track, calculate_surface_overlap
from app.domain.enums import CanonicalGenre, GeneId, RecommendationStatus, Track
from app.domain.profiles import FamiliarGenre, HardFilters, PreferenceParseResult
from tests.factories import make_game, make_profile, make_submission


def test_questionnaire_assigns_weight_two_only_to_selected_genes() -> None:
    submission = make_submission(
        important=[GeneId.STRATEGY, GeneId.EXPLORATION, GeneId.NARRATIVE]
    )
    preferences = build_questionnaire_preferences(submission)
    by_id = {item.gene_id: item for item in preferences}

    assert by_id[GeneId.STRATEGY].weight == 2
    assert by_id[GeneId.EXPLORATION].weight == 2
    assert by_id[GeneId.NARRATIVE].weight == 2
    assert by_id[GeneId.CHALLENGE].weight == 1


def test_profile_fusion_applies_library_then_text_with_one_level_caps() -> None:
    submission = make_submission(target=2, important=[GeneId.CHALLENGE])
    submission.additional_preferences = "I want something easier right now."
    profile = fuse_profile(
        profile_id="p_1",
        submission=submission,
        library_signal=LibraryGeneSignal(
            directions={GeneId.CHALLENGE: 9},
            source_appids={GeneId.CHALLENGE: [100]},
        ),
        parsed_preferences=PreferenceParseResult(
            gene_adjustments={GeneId.CHALLENGE: -1}
        ),
        owned_appids={100},
    )
    challenge = next(
        item for item in profile.gene_contributions if item.gene_id == GeneId.CHALLENGE
    )

    assert challenge.questionnaire_target == 2
    assert challenge.library_adjustment == 1
    assert challenge.text_adjustment == -1
    assert challenge.final_target == 2
    assert challenge.sources == ["questionnaire", "owned_game:100", "free_text"]
    assert profile.owned_appids == {100}


def test_hard_filter_excludes_owned_game_first() -> None:
    game = make_game(10)
    profile = make_profile()
    profile.owned_appids = {10}

    decision = apply_hard_filters(game, profile)

    assert decision.passed is False
    assert decision.reason == DropReason.OWNED_OR_EXCLUDED


def test_hard_filter_fails_closed_for_unknown_price() -> None:
    game = make_game(10, price=None)
    profile = make_profile(
        hard_filters=HardFilters(platforms=["windows"], max_price_usd_cents=2_000)
    )

    decision = apply_hard_filters(game, profile)

    assert decision.reason == DropReason.PRICE_UNVERIFIABLE


def test_similarity_penalizes_missing_weighted_coverage() -> None:
    profile = make_profile(
        important=[GeneId.CHALLENGE, GeneId.STRATEGY, GeneId.PACE]
    )
    levels = {
        GeneId.CHALLENGE: 2,
        GeneId.STRATEGY: 2,
        GeneId.PROGRESSION: 2,
        GeneId.EXPLORATION: 2,
        GeneId.CREATION: 2,
    }
    game = make_game(10, levels=levels)

    result = calculate_similarity(game, profile)

    assert result.similarity == 1.0
    assert result.weighted_coverage == pytest.approx(7 / 12)
    assert result.compatibility_score < 0.90
    assert not is_recommendation_eligible(game, profile, result)


def test_recommendation_eligibility_requires_two_priority_genes_known() -> None:
    profile = make_profile(
        important=[GeneId.CHALLENGE, GeneId.STRATEGY, GeneId.PACE]
    )
    levels = {
        GeneId.CHALLENGE: 2,
        GeneId.PROGRESSION: 2,
        GeneId.EXPLORATION: 2,
        GeneId.CREATION: 2,
        GeneId.NARRATIVE: 2,
        GeneId.IMMERSION: 2,
        GeneId.SOCIAL: 2,
        GeneId.STRATEGY: 2,
    }
    eligible_game = make_game(10, levels=levels)
    eligible_result = calculate_similarity(eligible_game, profile)
    assert is_recommendation_eligible(eligible_game, profile, eligible_result)

    levels.pop(GeneId.STRATEGY)
    levels[GeneId.PACE] = 2
    # Remove challenge so only one of the three elevated genes remains known.
    levels.pop(GeneId.CHALLENGE)
    ineligible_game = make_game(11, levels=levels)
    ineligible_result = calculate_similarity(ineligible_game, profile)
    assert ineligible_result.weighted_coverage >= 0.60
    assert not is_recommendation_eligible(
        ineligible_game,
        profile,
        ineligible_result,
        minimum_coverage=0.60,
    )


def test_surface_overlap_uses_ranked_user_weights() -> None:
    profile = make_profile(
        familiar_genres=[
            FamiliarGenre(genre=CanonicalGenre.RPG, rank=1, weight=3),
            FamiliarGenre(genre=CanonicalGenre.STRATEGY, rank=2, weight=2),
            FamiliarGenre(genre=CanonicalGenre.ADVENTURE, rank=3, weight=1),
        ]
    )
    same = make_game(10, genre=CanonicalGenre.RPG)
    cross = make_game(11, genre=CanonicalGenre.CASUAL)

    assert calculate_surface_overlap(same, profile) == pytest.approx(0.5)
    assert assign_track(same, profile) == Track.SAME
    assert assign_track(cross, profile) == Track.CROSS


def test_retrieval_returns_top_five_per_track_with_stable_ties() -> None:
    profile = make_profile()
    games = [make_game(appid) for appid in [9, 3, 8, 2, 7, 1]]
    games += [
        make_game(100 + index, genre=CanonicalGenre.CASUAL) for index in range(6)
    ]

    result = retrieve_candidates(games, profile)

    assert result.status == RecommendationStatus.OK
    assert result.same_track.kind == TrackResultKind.FORMAL
    assert [item.appid for item in result.same_track.candidates] == [1, 2, 3, 7, 8]
    assert [item.appid for item in result.cross_track.candidates] == [100, 101, 102, 103, 104]
    assert all(item.matching_genes for item in result.same_track.candidates)


def test_formal_closest_and_no_match_boundaries_are_inclusive() -> None:
    profile = make_profile(target=2)
    game = make_game(10, levels={gene_id: 3 for gene_id in GeneId})
    score = calculate_similarity(game, profile).compatibility_score

    formal = retrieve_candidates(
        [game], profile, formal_threshold=score, closest_floor=score - 0.1
    )
    assert formal.same_track.kind == TrackResultKind.FORMAL

    closest = retrieve_candidates(
        [game], profile, formal_threshold=score + 0.01, closest_floor=score
    )
    assert closest.status == RecommendationStatus.CLOSEST_ONLY
    assert closest.same_track.kind == TrackResultKind.CLOSEST

    no_match = retrieve_candidates(
        [game], profile, formal_threshold=score + 0.02, closest_floor=score + 0.01
    )
    assert no_match.status == RecommendationStatus.NO_MATCH
    assert no_match.same_track.kind == TrackResultKind.NO_MATCH


def test_missing_surface_genres_never_becomes_cross_track() -> None:
    profile = make_profile()
    game = make_game(10)
    game.sampling_bucket = None
    game.genres = []

    result = retrieve_candidates([game], profile)

    assert result.status == RecommendationStatus.NO_MATCH
    assert result.drop_counts[DropReason.MISSING_SURFACE_LABELS.value] == 1
