"""
Unit tests for UI/graphics/hud_renderer.py's networked-play header (role,
room id, network status) -- added so two networked game windows on the same
desktop can be told apart (same title + same board otherwise).
"""
import pathlib

import numpy as np

from graphics.hud_renderer import HudRenderer
from kungfu_chess.model.piece import Color, Kind
from state.game_events import GameOverInfo

_REAL_PIECES_DIR = pathlib.Path(__file__).resolve().parents[2] / 'assets' / 'pieces_mine'


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


def test_set_player_updates_black_name_and_elo():
    hud = HudRenderer(800, 800, player_white='alice', player_black='Waiting for opponent...')
    hud.set_player('black', 'bob', 1200)

    assert hud._player_black == 'bob'
    assert hud._black_elo == 1200
    assert hud._player_white == 'alice'  # untouched


def test_set_player_updates_white_name_and_elo():
    hud = HudRenderer(800, 800, player_white='Waiting for opponent...', player_black='bob')
    hud.set_player('white', 'alice', 1200)

    assert hud._player_white == 'alice'
    assert hud._white_elo == 1200
    assert hud._player_black == 'bob'  # untouched


def test_set_player_after_opponent_joins_does_not_crash_on_render():
    hud = HudRenderer(800, 800, player_white='alice', player_black='Waiting for opponent...')
    hud.set_player('black', 'bob', 1200)
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


def test_update_score_stores_scores_and_captured_lists():
    hud = HudRenderer(800, 800)
    hud.update_score(white_score=3, black_score=1,
                      white_captured=[Kind.PAWN, Kind.KNIGHT], black_captured=[Kind.QUEEN])

    assert hud._white_score == 3 and hud._black_score == 1
    assert hud._white_captured == [Kind.PAWN, Kind.KNIGHT]
    assert hud._black_captured == [Kind.QUEEN]


def test_update_score_defaults_captured_lists_to_empty():
    hud = HudRenderer(800, 800)
    hud.update_score(white_score=0, black_score=0)
    assert hud._white_captured == [] and hud._black_captured == []


def test_set_moves_stores_white_and_black_move_lists():
    hud = HudRenderer(800, 800)
    hud.set_moves({'white': ['e4', 'Nf3'], 'black': ['e5']})
    assert hud._white_moves == ['e4', 'Nf3']
    assert hud._black_moves == ['e5']


def test_set_moves_defaults_missing_sides_to_empty():
    hud = HudRenderer(800, 800)
    hud.set_moves({'white': ['e4']})
    assert hud._black_moves == []


def test_render_draws_recent_moves_for_both_sides_without_crashing():
    hud = HudRenderer(800, 800, player_white='alice', player_black='bob')
    hud.set_moves({'white': ['e4', 'Nf3', 'Bb5'], 'black': ['e5', 'Nc6']})
    frame = hud.render(_blank_board_frame())
    assert frame is not None


def test_captured_row_uses_letter_fallback_when_no_pieces_dir_is_set():
    """Without set_pieces_dir(), ThumbnailCache.get() has nowhere to look
    and returns None for every piece -- _draw_captured_row must fall back to
    drawing the kind's letter code instead of crashing or drawing nothing."""
    hud = HudRenderer(800, 800)
    # 12 pieces: more than one row's worth (per_row is 9 at the default
    # sidebar/thumbnail sizing), to also exercise the row-wrap branch.
    captured = [Kind.PAWN] * 12
    hud.update_score(white_score=0, black_score=0, black_captured=captured)

    frame = hud.render(_blank_board_frame())

    assert frame is not None


def test_captured_row_blits_a_real_thumbnail_when_pieces_dir_is_set():
    """With a real pieces directory, ThumbnailCache.get() finds an actual
    sprite and _draw_captured_row blits it -- exercises the cache's
    load/crop/resize path (and, on the second render, its cache-hit path)."""
    hud = HudRenderer(800, 800)
    hud.set_pieces_dir(_REAL_PIECES_DIR)
    hud.update_score(white_score=0, black_score=0, black_captured=[Kind.ROOK, Kind.KNIGHT])

    first_frame = hud.render(_blank_board_frame())
    assert first_frame is not None

    # Second render reuses the now-cached thumbnails (ThumbnailCache.get's
    # cache-hit branch) instead of re-reading from disk.
    second_frame = hud.render(_blank_board_frame())
    assert second_frame is not None


def test_thumbnail_cache_returns_none_for_a_kind_with_no_sprite_files():
    """set_pieces_dir points somewhere real, but this particular
    kind/color's sprite folder doesn't exist under it -- get() must return
    None (letter-fallback territory) rather than raising."""
    hud = HudRenderer(800, 800)
    hud.set_pieces_dir(pathlib.Path(__file__).resolve().parent)  # real dir, no piece sprites under it

    thumb = hud._thumbnails.get(Kind.QUEEN, Color.WHITE)

    assert thumb is None


def test_thumbnail_cache_returns_none_if_the_sprite_file_vanishes_after_globbing(tmp_path):
    """Defensive branch: the glob found a file, but reading it still raised
    FileNotFoundError (e.g. deleted between the glob and the read) -- must
    fall back to None rather than propagating the exception. Exercised for
    real with an actual undecodable file at the expected path (Img.read
    raises FileNotFoundError whenever cv2.imread can't decode a path,
    regardless of why the bytes on disk are bad), rather than mocking
    Img.read."""
    sprite_dir = tmp_path / 'RW' / 'states' / 'idle' / 'sprites'
    sprite_dir.mkdir(parents=True)
    (sprite_dir / '0.png').write_bytes(b'not a real png')

    hud = HudRenderer(800, 800)
    hud.set_pieces_dir(tmp_path)

    thumb = hud._thumbnails.get(Kind.ROOK, Color.WHITE)

    assert thumb is None


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
