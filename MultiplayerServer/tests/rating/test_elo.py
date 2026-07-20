import pytest

from rating.elo import expected_score, update_ratings


def test_expected_score_is_half_for_equal_ratings():
    assert expected_score(1200, 1200) == pytest.approx(0.5)


def test_expected_score_favors_higher_rating():
    assert expected_score(1400, 1200) > 0.5
    assert expected_score(1200, 1400) < 0.5


def test_update_ratings_equal_players_white_wins():
    new_white, new_black = update_ratings(1200, 1200, white_score=1.0)
    assert new_white == 1216  # 1200 + 32 * (1.0 - 0.5)
    assert new_black == 1184


def test_update_ratings_equal_players_black_wins():
    new_white, new_black = update_ratings(1200, 1200, white_score=0.0)
    assert new_white == 1184
    assert new_black == 1216


def test_update_ratings_draw_leaves_equal_ratings_unchanged():
    new_white, new_black = update_ratings(1200, 1200, white_score=0.5)
    assert new_white == 1200
    assert new_black == 1200


def test_favorite_winning_gains_less_than_an_underdog_upset_would():
    new_white_favorite, _ = update_ratings(1600, 1000, white_score=1.0)  # favorite wins as expected
    new_white_underdog, _ = update_ratings(1000, 1600, white_score=1.0)  # underdog pulls off an upset

    favorite_gain = new_white_favorite - 1600
    underdog_gain = new_white_underdog - 1000
    assert 0 < favorite_gain < underdog_gain
