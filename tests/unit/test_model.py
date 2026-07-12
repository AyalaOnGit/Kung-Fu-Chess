import unittest
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece, Color, Kind, PieceState
from kungfu_chess.model.board import Board, BoardError
from tests.conftest import W, B, empty_board, board_with


class TestPosition(unittest.TestCase):
    def test_equality(self):
        self.assertEqual(Position(2, 3), Position(2, 3))

    def test_inequality_row(self):
        self.assertNotEqual(Position(1, 3), Position(2, 3))

    def test_inequality_col(self):
        self.assertNotEqual(Position(2, 2), Position(2, 3))

    def test_repr(self):
        self.assertIn('2', repr(Position(2, 3)))
        self.assertIn('3', repr(Position(2, 3)))

    def test_hashable(self):
        s = {Position(0, 0), Position(0, 0)}
        self.assertEqual(len(s), 1)


class TestPiece(unittest.TestCase):
    def test_token(self):
        self.assertEqual(W(Kind.ROOK, 0, 0).token(), 'wR')
        self.assertEqual(B(Kind.KING, 0, 0).token(), 'bK')

    def test_is_royal(self):
        self.assertTrue(Piece.is_royal(Kind.KING))
        self.assertFalse(Piece.is_royal(Kind.ROOK))

    def test_default_state_idle(self):
        self.assertEqual(W(Kind.PAWN, 0, 0).state, PieceState.IDLE)

    def test_color_opponent(self):
        self.assertEqual(Color.WHITE.opponent(), Color.BLACK)
        self.assertEqual(Color.BLACK.opponent(), Color.WHITE)


class TestBoard(unittest.TestCase):
    def test_dimensions_inferred(self):
        b = Board(width=4, height=3)
        self.assertEqual(b.width, 4)
        self.assertEqual(b.height, 3)

    def test_empty_cell_returns_none(self):
        b = empty_board()
        self.assertIsNone(b.piece_at(Position(3, 3)))

    def test_occupied_cell_returns_piece(self):
        p = W(Kind.ROOK, 0, 0)
        b = board_with(p)
        self.assertEqual(b.piece_at(Position(0, 0)), p)

    def test_duplicate_occupancy_raises(self):
        p1 = W(Kind.ROOK, 0, 0)
        p2 = B(Kind.ROOK, 0, 0)
        b = board_with(p1)
        with self.assertRaises(BoardError):
            b.add_piece(p2)

    def test_move_piece_updates_cells(self):
        p = W(Kind.ROOK, 0, 0)
        b = board_with(p)
        b.move_piece(Position(0, 0), Position(0, 3))
        self.assertIsNone(b.piece_at(Position(0, 0)))
        self.assertEqual(b.piece_at(Position(0, 3)), p)

    def test_move_piece_captures_enemy(self):
        attacker = W(Kind.ROOK, 0, 0)
        target   = B(Kind.ROOK, 0, 3)
        b = board_with(attacker, target)
        b.move_piece(Position(0, 0), Position(0, 3))
        self.assertEqual(target.state, PieceState.CAPTURED)

    def test_remove_piece_clears_cell(self):
        p = W(Kind.ROOK, 0, 0)
        b = board_with(p)
        b.remove_piece(Position(0, 0))
        self.assertIsNone(b.piece_at(Position(0, 0)))
        self.assertEqual(p.state, PieceState.CAPTURED)

    def test_in_bounds(self):
        b = Board(width=4, height=4)
        self.assertTrue(b.in_bounds(Position(0, 0)))
        self.assertFalse(b.in_bounds(Position(4, 0)))
        self.assertFalse(b.in_bounds(Position(0, 4)))


if __name__ == '__main__':
    unittest.main()
