import unittest
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Kind
from kungfu_chess.rules.piece_rules import (
    RookRule, BishopRule, QueenRule, KnightRule, KingRule, PawnRule
)
from kungfu_chess.rules.rule_engine import RuleEngine
from tests.conftest import W, B, empty_board, board_with


class TestRookRule(unittest.TestCase):
    def setUp(self):
        self.rule = RookRule()

    def test_moves_along_empty_row(self):
        p = W(Kind.ROOK, 0, 0)
        b = board_with(p)
        dests = self.rule.legal_destinations(b, p)
        self.assertIn(Position(0, 7), dests)
        self.assertIn(Position(7, 0), dests)

    def test_stops_before_friendly(self):
        p     = W(Kind.ROOK, 0, 0)
        block = W(Kind.PAWN, 0, 3)
        b = board_with(p, block)
        dests = self.rule.legal_destinations(b, p)
        self.assertIn(Position(0, 2), dests)
        self.assertNotIn(Position(0, 3), dests)
        self.assertNotIn(Position(0, 4), dests)

    def test_captures_enemy_but_not_past(self):
        p     = W(Kind.ROOK, 0, 0)
        enemy = B(Kind.PAWN, 0, 3)
        b = board_with(p, enemy)
        dests = self.rule.legal_destinations(b, p)
        self.assertIn(Position(0, 3), dests)
        self.assertNotIn(Position(0, 4), dests)

    def test_no_diagonal(self):
        p = W(Kind.ROOK, 3, 3)
        b = board_with(p)
        dests = self.rule.legal_destinations(b, p)
        self.assertNotIn(Position(4, 4), dests)


class TestBishopRule(unittest.TestCase):
    def setUp(self):
        self.rule = BishopRule()

    def test_moves_diagonally(self):
        p = W(Kind.BISHOP, 3, 3)
        b = board_with(p)
        dests = self.rule.legal_destinations(b, p)
        self.assertIn(Position(0, 0), dests)
        self.assertIn(Position(7, 7), dests)

    def test_no_straight(self):
        p = W(Kind.BISHOP, 3, 3)
        b = board_with(p)
        dests = self.rule.legal_destinations(b, p)
        self.assertNotIn(Position(3, 7), dests)


class TestQueenRule(unittest.TestCase):
    def test_combines_rook_and_bishop(self):
        rule = QueenRule()
        p = W(Kind.QUEEN, 3, 3)
        b = board_with(p)
        dests = rule.legal_destinations(b, p)
        self.assertIn(Position(3, 7), dests)
        self.assertIn(Position(7, 7), dests)


class TestKnightRule(unittest.TestCase):
    def test_l_shape(self):
        rule = KnightRule()
        p = W(Kind.KNIGHT, 3, 3)
        b = board_with(p)
        dests = rule.legal_destinations(b, p)
        self.assertIn(Position(1, 2), dests)
        self.assertIn(Position(5, 4), dests)

    def test_jumps_over_blockers(self):
        rule = KnightRule()
        p     = W(Kind.KNIGHT, 3, 3)
        block = W(Kind.PAWN, 4, 3)
        b = board_with(p, block)
        dests = rule.legal_destinations(b, p)
        self.assertIn(Position(5, 4), dests)

    def test_corner_skips_out_of_bounds_offsets(self):
        """From a corner, most of the 8 L-shaped offsets land off the
        board and must be skipped rather than raising or being included."""
        rule = KnightRule()
        p = W(Kind.KNIGHT, 0, 0)
        b = board_with(p)
        dests = rule.legal_destinations(b, p)
        self.assertEqual(dests, {Position(2, 1), Position(1, 2)})


class TestKingRule(unittest.TestCase):
    def test_one_cell_only(self):
        rule = KingRule()
        p = W(Kind.KING, 3, 3)
        b = board_with(p)
        dests = rule.legal_destinations(b, p)
        self.assertIn(Position(4, 4), dests)
        self.assertNotIn(Position(5, 5), dests)
        self.assertEqual(len(dests), 8)

    def test_corner_skips_out_of_bounds_offsets(self):
        """From a corner, 5 of the 8 one-step offsets land off the board."""
        rule = KingRule()
        p = W(Kind.KING, 0, 0)
        b = board_with(p)
        dests = rule.legal_destinations(b, p)
        self.assertEqual(
            dests,
            {Position(0, 1), Position(1, 0), Position(1, 1)},
        )


class TestPawnRule(unittest.TestCase):
    def setUp(self):
        self.rule = PawnRule()

    def test_white_moves_up(self):
        p = W(Kind.PAWN, 6, 3)
        b = board_with(p)
        dests = self.rule.legal_destinations(b, p)
        self.assertIn(Position(5, 3), dests)
        self.assertNotIn(Position(7, 3), dests)

    def test_black_moves_down(self):
        p = B(Kind.PAWN, 1, 3)
        b = board_with(p)
        dests = self.rule.legal_destinations(b, p)
        self.assertIn(Position(2, 3), dests)

    def test_double_move_from_start(self):
        p = W(Kind.PAWN, 6, 3)
        b = board_with(p)
        dests = self.rule.legal_destinations(b, p)
        self.assertIn(Position(4, 3), dests)

    def test_double_move_blocked(self):
        p     = W(Kind.PAWN, 6, 3)
        block = W(Kind.PAWN, 5, 3)
        b = board_with(p, block)
        dests = self.rule.legal_destinations(b, p)
        self.assertNotIn(Position(4, 3), dests)

    def test_diagonal_capture(self):
        p     = W(Kind.PAWN, 4, 3)
        enemy = B(Kind.PAWN, 3, 4)
        b = board_with(p, enemy)
        dests = self.rule.legal_destinations(b, p)
        self.assertIn(Position(3, 4), dests)

    def test_no_forward_capture(self):
        p     = W(Kind.PAWN, 4, 3)
        enemy = B(Kind.PAWN, 3, 3)
        b = board_with(p, enemy)
        dests = self.rule.legal_destinations(b, p)
        self.assertNotIn(Position(3, 3), dests)

    def test_diagonal_capture_skips_out_of_bounds_column(self):
        """On the edge column, one diagonal capture direction falls off
        the board and must be skipped rather than raising or included."""
        p     = W(Kind.PAWN, 4, 0)
        enemy = B(Kind.PAWN, 3, 1)
        b = board_with(p, enemy)
        dests = self.rule.legal_destinations(b, p)
        self.assertIn(Position(3, 1), dests)   # valid diagonal capture still works
        self.assertEqual(len(dests), 2)        # forward step + the one valid diagonal only


class TestRuleEngine(unittest.TestCase):
    def setUp(self):
        self.engine = RuleEngine()

    def test_valid_move(self):
        p = W(Kind.ROOK, 0, 0)
        b = board_with(p)
        r = self.engine.validate_move(b, Position(0, 0), Position(0, 5))
        self.assertTrue(r.is_valid)
        self.assertEqual(r.reason, 'ok')

    def test_outside_board(self):
        b = empty_board()
        r = self.engine.validate_move(b, Position(0, 0), Position(9, 9))
        self.assertFalse(r.is_valid)
        self.assertEqual(r.reason, 'outside_board')

    def test_empty_source(self):
        b = empty_board()
        r = self.engine.validate_move(b, Position(0, 0), Position(0, 1))
        self.assertFalse(r.is_valid)
        self.assertEqual(r.reason, 'empty_source')

    def test_friendly_destination(self):
        p1 = W(Kind.ROOK, 0, 0)
        p2 = W(Kind.PAWN, 0, 3)
        b = board_with(p1, p2)
        r = self.engine.validate_move(b, Position(0, 0), Position(0, 3))
        self.assertFalse(r.is_valid)
        self.assertEqual(r.reason, 'friendly_destination')

    def test_illegal_piece_move(self):
        p = W(Kind.ROOK, 0, 0)
        b = board_with(p)
        r = self.engine.validate_move(b, Position(0, 0), Position(3, 3))
        self.assertFalse(r.is_valid)
        self.assertEqual(r.reason, 'illegal_piece_move')


if __name__ == '__main__':
    unittest.main()
