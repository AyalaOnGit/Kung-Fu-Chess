import unittest
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece, Color, Kind, PieceState
from kungfu_chess.model.board import Board, BoardError
from kungfu_chess.rules.piece_rules import (
    RookRule, BishopRule, QueenRule, KnightRule, KingRule, PawnRule
)
from kungfu_chess.rules.rule_engine import RuleEngine
from kungfu_chess.realtime.motion import travel_duration_ms
from kungfu_chess.realtime.real_time_arbiter import RealTimeArbiter
from kungfu_chess.engine.game_engine import GameEngine
from kungfu_chess.input.board_mapper import BoardMapper
from kungfu_chess.input.controller import Controller
from kungfu_chess.io.board_parser import parse_board
from kungfu_chess.io.board_printer import board_to_lines
from kungfu_chess.factory import build_engine, build_script_runner

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_id = 0
def new_piece(color: Color, kind: Kind, row: int, col: int) -> Piece:
    global _id
    _id += 1
    return Piece(id=_id, color=color, kind=kind, cell=Position(row, col))


def W(kind: Kind, row: int, col: int) -> Piece:
    return new_piece(Color.WHITE, kind, row, col)


def B(kind: Kind, row: int, col: int) -> Piece:
    return new_piece(Color.BLACK, kind, row, col)


def empty_board(w=8, h=8) -> Board:
    return Board(width=w, height=h)


def board_with(*pieces) -> Board:
    b = empty_board()
    for p in pieces:
        b.add_piece(p)
    return b


# ---------------------------------------------------------------------------
# Position
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Piece
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Board
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Movement Rules
# ---------------------------------------------------------------------------
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
        self.assertIn(Position(3, 7), dests)   # straight
        self.assertIn(Position(7, 7), dests)   # diagonal


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


class TestKingRule(unittest.TestCase):
    def test_one_cell_only(self):
        rule = KingRule()
        p = W(Kind.KING, 3, 3)
        b = board_with(p)
        dests = rule.legal_destinations(b, p)
        self.assertIn(Position(4, 4), dests)
        self.assertNotIn(Position(5, 5), dests)
        self.assertEqual(len(dests), 8)


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
        p = W(Kind.PAWN, 7, 3)  # start row for white on 8-high board
        b = board_with(p)
        dests = self.rule.legal_destinations(b, p)
        self.assertIn(Position(5, 3), dests)

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


# ---------------------------------------------------------------------------
# RuleEngine
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# travel_duration_ms
# ---------------------------------------------------------------------------
class TestTravelDuration(unittest.TestCase):
    def test_one_square(self):
        self.assertEqual(travel_duration_ms(Position(0, 0), Position(0, 1)), 1000)

    def test_three_squares(self):
        self.assertEqual(travel_duration_ms(Position(0, 0), Position(0, 3)), 3000)

    def test_diagonal_uses_steps(self):
        self.assertEqual(travel_duration_ms(Position(0, 0), Position(3, 3)), 3000)


# ---------------------------------------------------------------------------
# RealTimeArbiter
# ---------------------------------------------------------------------------
class TestRealTimeArbiter(unittest.TestCase):
    def _make(self, *pieces):
        b = board_with(*pieces)
        captured = []
        arb = RealTimeArbiter(b, on_king_captured=lambda: captured.append(True))
        return b, arb, captured

    def test_piece_arrives_after_duration(self):
        p = W(Kind.ROOK, 0, 0)
        b, arb, _ = self._make(p)
        arb.start_motion(p, Position(0, 0), Position(0, 3))
        arb.advance_time(3000)
        self.assertEqual(b.piece_at(Position(0, 3)), p)
        self.assertIsNone(b.piece_at(Position(0, 0)))

    def test_piece_not_arrived_before_duration(self):
        p = W(Kind.ROOK, 0, 0)
        b, arb, _ = self._make(p)
        arb.start_motion(p, Position(0, 0), Position(0, 3))
        arb.advance_time(2999)
        self.assertEqual(b.piece_at(Position(0, 0)), p)

    def test_king_capture_triggers_callback(self):
        attacker = W(Kind.ROOK, 0, 0)
        king     = B(Kind.KING, 0, 3)
        b, arb, captured = self._make(attacker, king)
        arb.start_motion(attacker, Position(0, 0), Position(0, 3))
        arb.advance_time(3000)
        self.assertTrue(captured)

    def test_airborne_captures_arriving_enemy(self):
        jumper  = W(Kind.ROOK, 0, 0)
        enemy   = B(Kind.ROOK, 0, 1)  # 1 step away => arrives at 1000ms
        b, arb, _ = self._make(jumper, enemy)
        arb.start_jump(jumper)
        arb.start_motion(enemy, Position(0, 1), Position(0, 0))
        arb.advance_time(1000)
        self.assertIsNone(b.piece_at(Position(0, 1)))
        self.assertEqual(b.piece_at(Position(0, 0)), jumper)

    def test_pawn_promotes_on_last_row(self):
        p = W(Kind.PAWN, 1, 0)
        b, arb, _ = self._make(p)
        arb.start_motion(p, Position(1, 0), Position(0, 0))
        arb.advance_time(1000)
        self.assertEqual(b.piece_at(Position(0, 0)).kind, Kind.QUEEN)

    def test_has_active_motion(self):
        p = W(Kind.ROOK, 0, 0)
        b, arb, _ = self._make(p)
        self.assertFalse(arb.has_active_motion())
        arb.start_motion(p, Position(0, 0), Position(0, 3))
        self.assertTrue(arb.has_active_motion())


# ---------------------------------------------------------------------------
# GameEngine
# ---------------------------------------------------------------------------
class TestGameEngine(unittest.TestCase):
    def _make(self, *pieces):
        b      = board_with(*pieces)
        engine = build_engine(b)
        return b, engine

    def test_valid_move_accepted(self):
        p = W(Kind.ROOK, 0, 0)
        _, engine = self._make(p)
        result = engine.request_move(Position(0, 0), Position(0, 3))
        self.assertTrue(result.is_accepted)
        self.assertEqual(result.reason, 'ok')

    def test_game_over_rejects_move(self):
        p = W(Kind.ROOK, 0, 0)
        _, engine = self._make(p)
        engine._state.game_over = True
        result = engine.request_move(Position(0, 0), Position(0, 3))
        self.assertFalse(result.is_accepted)
        self.assertEqual(result.reason, 'game_over')

    def test_motion_in_progress_rejects_second_move(self):
        p = W(Kind.ROOK, 0, 0)
        _, engine = self._make(p)
        engine.request_move(Position(0, 0), Position(0, 3))
        result = engine.request_move(Position(0, 0), Position(0, 5))
        self.assertFalse(result.is_accepted)
        self.assertEqual(result.reason, 'motion_in_progress')

    def test_wait_advances_clock(self):
        p = W(Kind.ROOK, 0, 0)
        _, engine = self._make(p)
        engine.wait(500)
        self.assertEqual(engine.clock_ms, 500)

    def test_king_capture_sets_game_over(self):
        attacker = W(Kind.ROOK, 0, 0)
        king     = B(Kind.KING, 0, 3)
        b, engine = self._make(attacker, king)
        engine.request_move(Position(0, 0), Position(0, 3))
        engine.wait(3000)
        self.assertTrue(engine.game_over)


# ---------------------------------------------------------------------------
# BoardMapper
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# BoardParser
# ---------------------------------------------------------------------------
class TestBoardParser(unittest.TestCase):
    def test_parses_valid_board(self):
        b = parse_board(["wR . bK", ". . ."])
        self.assertIsNotNone(b.piece_at(Position(0, 0)))
        self.assertIsNone(b.piece_at(Position(0, 1)))
        self.assertIsNotNone(b.piece_at(Position(0, 2)))

    def test_dimensions(self):
        b = parse_board(["wR . bK", ". . ."])
        self.assertEqual(b.width, 3)
        self.assertEqual(b.height, 2)

    def test_unknown_token_raises(self):
        with self.assertRaises(ValueError):
            parse_board(["wR xZ"])

    def test_row_width_mismatch_raises(self):
        with self.assertRaises(ValueError):
            parse_board(["wR .", ". . ."])


# ---------------------------------------------------------------------------
# BoardPrinter
# ---------------------------------------------------------------------------
class TestBoardPrinter(unittest.TestCase):
    def test_prints_correct_tokens(self):
        b = parse_board(["wR .", ". bK"])
        lines = board_to_lines(b)
        self.assertEqual(lines[0], "wR .")
        self.assertEqual(lines[1], ". bK")

    def test_empty_board(self):
        b = Board(width=2, height=2)
        lines = board_to_lines(b)
        self.assertEqual(lines, [". .", ". ."])


# ---------------------------------------------------------------------------
# ScriptRunner (integration)
# ---------------------------------------------------------------------------
class TestScriptRunner(unittest.TestCase):
    def test_move_and_print(self):
        b = parse_board(["wR . . .", ". . . ."])
        _, runner = build_script_runner(b)
        output = runner.run([
            "click 50 50",
            "click 350 50",
            "wait 3000",
            "print board",
        ])
        self.assertEqual(output[0], ". . . wR")

    def test_game_over_after_king_capture(self):
        b = parse_board(["wR bK", ". ."])
        engine, runner = build_script_runner(b)
        runner.run(["click 50 50", "click 150 50", "wait 1000"])
        self.assertTrue(engine.game_over)


if __name__ == '__main__':
    unittest.main()
