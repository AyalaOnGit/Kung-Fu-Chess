"""
Unit tests for UI/graphics/hud_renderer.py's networked-play header (role,
room id, network status) -- added so two networked game windows on the same
desktop can be told apart (same title + same board otherwise).
"""
import numpy as np

from graphics.hud_renderer import HudRenderer
from state.game_events import GameOverInfo


def _blank_board_frame():
    return np.zeros((800, 800, 4), dtype=np.uint8)


def test_render_without_any_network_state_does_not_crash():
    hud = HudRenderer(800, 800)
    frame = hud.render(_blank_board_frame())
    assert frame is not None


def test_render_with_role_room_and_status_does_not_crash():
    hud = HudRenderer(800, 800)
    hud.set_my_role('white')
    hud.set_room_id('abc123')
    hud.set_network_status('Opponent disconnected -- auto-resign in 12s')
    frame = hud.render(_blank_board_frame())
    assert frame is not None


def test_player_label_appends_elo_when_known():
    hud = HudRenderer(800, 800, player_white='alice', player_black='bob', white_elo=1200, black_elo=1215)
    assert hud._player_label('alice', 1200) == 'alice (1200)'


def test_player_label_omits_elo_when_unknown():
    hud = HudRenderer(800, 800, player_white='alice', player_black='bob')
    assert hud._player_label('bob', None) == 'bob'


def test_render_with_elo_does_not_crash():
    hud = HudRenderer(800, 800, player_white='alice', player_black='bob', white_elo=1200, black_elo=1215)
    frame = hud.render(_blank_board_frame())
    assert frame is not None


def test_render_with_game_over_title_only_does_not_crash():
    hud = HudRenderer(800, 800, player_white='alice', player_black='bob')
    hud.set_game_over(GameOverInfo(title='alice wins!'))
    frame = hud.render(_blank_board_frame())
    assert frame is not None


def test_render_with_game_over_and_rating_lines_does_not_crash():
    hud = HudRenderer(800, 800, player_white='alice', player_black='bob', white_elo=1216, black_elo=1184)
    hud.set_game_over(GameOverInfo(
        title='alice wins!', white_label='alice: 1216 (+16)', black_label='bob: 1184 (-16)',
        white_delta=16, black_delta=-16,
    ))
    frame = hud.render(_blank_board_frame())
    assert frame is not None


def test_set_game_over_none_clears_it():
    hud = HudRenderer(800, 800)
    hud.set_game_over(GameOverInfo(title='White wins!'))
    hud.set_game_over(None)
    # No exception, and the overlay shouldn't be drawn at all once cleared.
    frame = hud.render(_blank_board_frame())
    assert frame is not None


def test_set_my_role_none_clears_it():
    hud = HudRenderer(800, 800)
    hud.set_my_role('black')
    hud.set_my_role(None)
    # No exception, and the network header shouldn't be drawn at all when
    # every field is unset -- covered implicitly by not crashing here too.
    frame = hud.render(_blank_board_frame())
    assert frame is not None


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
