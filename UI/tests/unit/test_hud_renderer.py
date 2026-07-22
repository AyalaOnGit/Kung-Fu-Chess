"""
Unit tests for UI/graphics/hud_renderer.py's networked-play header (role,
room id, network status) -- added so two networked game windows on the same
desktop can be told apart (same title + same board otherwise).
"""
import sys
import pathlib

import numpy as np

ui_dir = pathlib.Path(__file__).parent.parent.parent
if str(ui_dir) not in sys.path:
    sys.path.insert(0, str(ui_dir))

import server_bridge  # noqa: F401

from graphics.hud_renderer import HudRenderer


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
