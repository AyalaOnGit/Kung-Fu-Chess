"""
Unit tests for UI/ui_components/game_over_banner.py's GameOverBanner --
composes the end-of-game dialog's title (winner) and, once a RatingUpdate
arrives, each player's new rating and signed ELO change.
"""
from kungfu_chess.model.piece import Color
from state.game_events import GameOver, RatingUpdate
from ui_components.game_over_banner import GameOverBanner


def test_get_info_returns_none_before_game_over():
    banner = GameOverBanner(white_name='alice', black_name='bob')
    assert banner.get_info() is None


def test_game_over_alone_produces_a_title_with_no_rating_lines():
    banner = GameOverBanner(white_name='alice', black_name='bob')
    banner.on_event(GameOver(winner=Color.WHITE, loser=Color.BLACK))

    info = banner.get_info()

    assert info.title == 'alice wins!'
    assert info.white_label is None and info.black_label is None


def test_black_win_names_black_as_the_winner():
    banner = GameOverBanner(white_name='alice', black_name='bob')
    banner.on_event(GameOver(winner=Color.BLACK, loser=Color.WHITE))

    assert banner.get_info().title == 'bob wins!'


def test_rating_update_after_game_over_fills_in_the_rating_lines():
    banner = GameOverBanner(white_name='alice', black_name='bob')
    banner.on_event(GameOver(winner=Color.WHITE, loser=Color.BLACK))
    banner.on_event(RatingUpdate(white_elo_before=1200, white_elo_after=1216,
                                  black_elo_before=1200, black_elo_after=1184))

    info = banner.get_info()

    assert info.white_label == 'alice: 1216 (+16)'
    assert info.black_label == 'bob: 1184 (-16)'
    assert info.white_delta == 16 and info.black_delta == -16


def test_rating_update_before_game_over_is_not_lost():
    """No ordering guarantee between GameOver and RatingUpdate (see
    MultiplayerServer/main.py's on_game_over) -- whichever arrives first
    must still be reflected once both have."""
    banner = GameOverBanner(white_name='alice', black_name='bob')
    banner.on_event(RatingUpdate(white_elo_before=1200, white_elo_after=1184,
                                  black_elo_before=1200, black_elo_after=1216))
    banner.on_event(GameOver(winner=Color.BLACK, loser=Color.WHITE))

    info = banner.get_info()

    assert info.title == 'bob wins!'
    assert info.white_label == 'alice: 1184 (-16)'
    assert info.black_label == 'bob: 1216 (+16)'


def test_default_names_are_generic_white_and_black():
    banner = GameOverBanner()
    banner.on_event(GameOver(winner=Color.WHITE, loser=Color.BLACK))

    assert banner.get_info().title == 'White wins!'


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
