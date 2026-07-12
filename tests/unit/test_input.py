import unittest
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Kind
from kungfu_chess.input.board_mapper import BoardMapper
from kungfu_chess.input.controller import Controller
from kungfu_chess.factory import build_engine
from tests.conftest import W, board_with


class TestBoardMapper(unittest.TestCase):
    def setUp(self):
        self.mapper = BoardMapper(width=8, height=8)

    def test_top_left(self):
        self.assertEqual(self.mapper.pixel_to_position(0, 0), Position(0, 0))

    def test_center_of_cell(self):
        self.assertEqual(self.mapper.pixel_to_position(50, 50), Position(0, 0))

    def test_second_cell(self):
        self.assertEqual(self.mapper.pixel_to_position(100, 100), Position(1, 1))

    def test_in_bounds(self):
        self.assertTrue(self.mapper.in_bounds_px(50, 50))
        self.assertFalse(self.mapper.in_bounds_px(9999, 9999))


class TestController(unittest.TestCase):
    def _make(self, *pieces):
        b          = board_with(*pieces)
        engine     = build_engine(b)
        mapper     = BoardMapper(b.width, b.height)
        controller = Controller(engine, mapper)
        return engine, controller

    def test_first_click_selects_piece(self):
        p = W(Kind.ROOK, 0, 0)
        _, ctrl = self._make(p)
        ctrl.on_click(50, 50)
        self.assertEqual(ctrl.selected, Position(0, 0))

    def test_first_click_empty_ignored(self):
        _, ctrl = self._make()
        ctrl.on_click(50, 50)
        self.assertIsNone(ctrl.selected)

    def test_second_click_sends_move_and_clears(self):
        p = W(Kind.ROOK, 0, 0)
        engine, ctrl = self._make(p)
        ctrl.on_click(50, 50)
        ctrl.on_click(350, 50)
        self.assertIsNone(ctrl.selected)

    def test_out_of_bounds_with_selection_cancels(self):
        p = W(Kind.ROOK, 0, 0)
        _, ctrl = self._make(p)
        ctrl.on_click(50, 50)
        ctrl.on_click(9999, 9999)
        self.assertIsNone(ctrl.selected)

    def test_out_of_bounds_without_selection_ignored(self):
        _, ctrl = self._make()
        ctrl.on_click(9999, 9999)
        self.assertIsNone(ctrl.selected)


if __name__ == '__main__':
    unittest.main()
