import unittest
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Kind
from kungfu_chess.interaction.board_mapper import BoardMapper
from kungfu_chess.interaction.controller import Controller
from kungfu_chess.engine_builder import build_engine
from kungfu_chess.config import CELL_SIZE_PX
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

    def test_position_to_pixel_uses_offset(self):
        mapper = BoardMapper(width=8, height=8, offset_x=10, offset_y=20)
        self.assertEqual(mapper.position_to_pixel(Position(0, 0)), (10, 20))
        self.assertEqual(
            mapper.position_to_pixel(Position(1, 2)),
            (2 * CELL_SIZE_PX + 10, 1 * CELL_SIZE_PX + 20),
        )

    def test_cell_center_pixel_uses_offset(self):
        self.assertEqual(
            self.mapper.cell_center_pixel(Position(0, 0)),
            (CELL_SIZE_PX // 2, CELL_SIZE_PX // 2),
        )

    def test_cell_size_is_uniform_without_boundaries(self):
        self.assertEqual(self.mapper.cell_size(Position(3, 3)), (CELL_SIZE_PX, CELL_SIZE_PX))

    def test_in_bounds_px_false_when_position_outside_grid(self):
        mapper = BoardMapper(width=2, height=2)
        self.assertFalse(mapper.in_bounds_px(250, 250))


class TestBoardMapperBoundaryMode(unittest.TestCase):
    """Exercises the exact-boundary path (col_boundaries/row_boundaries),
    used when the board image has non-uniform cell sizes or a border offset."""

    def setUp(self):
        self.cols = [2, 104, 206, 260]   # 3 cells: [2,104), [104,206), [206,260)
        self.rows = [6, 108, 211]        # 2 cells: [6,108), [108,211)
        self.mapper = BoardMapper(width=3, height=2,
                                   col_boundaries=self.cols,
                                   row_boundaries=self.rows)

    def test_pixel_to_position_uses_boundaries(self):
        self.assertEqual(self.mapper.pixel_to_position(50, 50), Position(0, 0))
        self.assertEqual(self.mapper.pixel_to_position(150, 150), Position(1, 1))

    def test_pixel_to_position_clamps_to_last_cell_when_out_of_range(self):
        # _boundary_index falls through the loop and clamps to the last
        # valid cell index when px is beyond every boundary bucket.
        self.assertEqual(self.mapper.pixel_to_position(9999, 9999), Position(1, 2))

    def test_position_to_pixel_returns_boundary_top_left(self):
        self.assertEqual(self.mapper.position_to_pixel(Position(0, 0)), (2, 6))
        self.assertEqual(self.mapper.position_to_pixel(Position(1, 2)), (206, 108))

    def test_cell_center_pixel_uses_boundaries(self):
        self.assertEqual(
            self.mapper.cell_center_pixel(Position(0, 0)),
            ((2 + 104) // 2, (6 + 108) // 2),
        )

    def test_cell_size_uses_boundaries(self):
        self.assertEqual(self.mapper.cell_size(Position(0, 0)), (104 - 2, 108 - 6))
        self.assertEqual(self.mapper.cell_size(Position(0, 2)), (260 - 206, 108 - 6))

    def test_in_bounds_px_true_inside_grid(self):
        self.assertTrue(self.mapper.in_bounds_px(50, 50))

    def test_in_bounds_px_false_before_first_boundary(self):
        self.assertFalse(self.mapper.in_bounds_px(1, 50))

    def test_in_bounds_px_false_past_last_col_boundary(self):
        self.assertFalse(self.mapper.in_bounds_px(300, 50))

    def test_in_bounds_px_false_past_last_row_boundary(self):
        self.assertFalse(self.mapper.in_bounds_px(50, 300))


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

    def test_second_click_on_friendly_piece_reselects_instead_of_moving(self):
        p1 = W(Kind.ROOK, 0, 0)
        p2 = W(Kind.ROOK, 0, 3)
        _, ctrl = self._make(p1, p2)
        ctrl.on_click(50, 50)    # select p1 at (0,0)
        ctrl.on_click(350, 50)   # click friendly p2 at (0,3) -> reselect, not move
        self.assertEqual(ctrl.selected, Position(0, 3))

    def test_on_jump_out_of_bounds_returns_none(self):
        _, ctrl = self._make()
        result = ctrl.on_jump(9999, 9999)
        self.assertIsNone(result)

    def test_on_jump_executes_command_and_clears_selection(self):
        p = W(Kind.ROOK, 0, 0)
        _, ctrl = self._make(p)
        ctrl.on_click(50, 50)  # select the piece first
        result = ctrl.on_jump(50, 50)
        self.assertTrue(result.is_accepted)
        self.assertIsNone(ctrl.selected)

    def test_on_jump_rejected_on_empty_cell(self):
        _, ctrl = self._make()
        result = ctrl.on_jump(50, 50)
        self.assertFalse(result.is_accepted)


if __name__ == '__main__':
    unittest.main()
