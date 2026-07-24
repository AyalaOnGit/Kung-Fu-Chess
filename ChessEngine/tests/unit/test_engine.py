import unittest
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Kind
from kungfu_chess.engine.commands import MoveCommand, JumpCommand
from kungfu_chess.engine_builder import build_engine
from tests.conftest import W, B, board_with


class TestGameEngine(unittest.TestCase):
    def _make(self, *pieces, cooldown_ms=0):
        b      = board_with(*pieces)
        engine = build_engine(b, cooldown_ms=cooldown_ms)
        return b, engine

    def _move(self, engine, src, dest):
        return engine.execute(MoveCommand(src, dest))

    def _jump(self, engine, cell):
        return engine.execute(JumpCommand(cell))

    def test_valid_move_accepted(self):
        p = W(Kind.ROOK, 0, 0)
        _, engine = self._make(p)
        result = self._move(engine, Position(0, 0), Position(0, 3))
        self.assertTrue(result.is_accepted)
        self.assertEqual(result.reason, 'ok')

    def test_game_over_rejects_move(self):
        p = W(Kind.ROOK, 0, 0)
        _, engine = self._make(p)
        engine.force_game_over()
        result = self._move(engine, Position(0, 0), Position(0, 3))
        self.assertFalse(result.is_accepted)
        self.assertEqual(result.reason, 'game_over')

    def test_motion_in_progress_rejects_second_move(self):
        p = W(Kind.ROOK, 0, 0)
        _, engine = self._make(p)
        self._move(engine, Position(0, 0), Position(0, 3))
        result = self._move(engine, Position(0, 0), Position(0, 5))
        self.assertFalse(result.is_accepted)
        self.assertEqual(result.reason, 'motion_in_progress')

    def test_two_different_pieces_move_concurrently(self):
        p1 = W(Kind.ROOK, 0, 0)
        p2 = B(Kind.ROOK, 2, 0)
        b, engine = self._make(p1, p2)
        r1 = self._move(engine, Position(0, 0), Position(0, 3))
        r2 = self._move(engine, Position(2, 0), Position(2, 3))
        self.assertTrue(r1.is_accepted)
        self.assertTrue(r2.is_accepted)

    def test_jump_accepted(self):
        p = W(Kind.ROOK, 0, 0)
        _, engine = self._make(p)
        result = self._jump(engine, Position(0, 0))
        self.assertTrue(result.is_accepted)
        self.assertEqual(result.reason, 'ok')

    def test_jump_rejected_when_already_jumping(self):
        p = W(Kind.ROOK, 0, 0)
        _, engine = self._make(p)
        self._jump(engine, Position(0, 0))
        result = self._jump(engine, Position(0, 0))
        self.assertFalse(result.is_accepted)
        self.assertEqual(result.reason, 'motion_in_progress')

    def test_cooldown_rejects_move(self):
        p = W(Kind.ROOK, 0, 0)
        _, engine = self._make(p, cooldown_ms=1000)
        self._move(engine, Position(0, 0), Position(0, 3))
        engine.wait(3000)
        result = self._move(engine, Position(0, 3), Position(0, 5))
        self.assertFalse(result.is_accepted)
        self.assertEqual(result.reason, 'motion_in_progress')

    def test_cooldown_expires_and_allows_move(self):
        p = W(Kind.ROOK, 0, 0)
        _, engine = self._make(p, cooldown_ms=1000)
        self._move(engine, Position(0, 0), Position(0, 3))
        engine.wait(3000 + 1000)
        result = self._move(engine, Position(0, 3), Position(0, 5))
        self.assertTrue(result.is_accepted)

    def test_cooldown_rejects_jump(self):
        p = W(Kind.ROOK, 0, 0)
        _, engine = self._make(p, cooldown_ms=1000)
        self._move(engine, Position(0, 0), Position(0, 3))
        engine.wait(3000)  # piece has arrived at (0,3) and is now cooling
        result = self._jump(engine, Position(0, 3))
        self.assertFalse(result.is_accepted)
        self.assertEqual(result.reason, 'motion_in_progress')

    def test_cooldown_expires_and_allows_jump(self):
        p = W(Kind.ROOK, 0, 0)
        _, engine = self._make(p, cooldown_ms=1000)
        self._move(engine, Position(0, 0), Position(0, 3))
        engine.wait(3000 + 1000)
        result = self._jump(engine, Position(0, 3))
        self.assertTrue(result.is_accepted)

    def test_wait_advances_clock(self):
        p = W(Kind.ROOK, 0, 0)
        _, engine = self._make(p)
        engine.wait(500)
        self.assertEqual(engine.clock_ms, 500)

    def test_king_capture_sets_game_over(self):
        attacker = W(Kind.ROOK, 0, 0)
        king     = B(Kind.KING, 0, 3)
        b, engine = self._make(attacker, king)
        self._move(engine, Position(0, 0), Position(0, 3))
        engine.wait(3000)
        self.assertTrue(engine.game_over)

    def test_non_king_capture_does_not_set_game_over(self):
        """RealTimeArbiter reports every capture via on_piece_captured;
        GameEngine is the layer that decides a capture only ends the game
        if the captured piece is a king (Piece.is_royal)."""
        attacker = W(Kind.ROOK, 0, 0)
        rook     = B(Kind.ROOK, 0, 3)
        b, engine = self._make(attacker, rook)
        self._move(engine, Position(0, 0), Position(0, 3))
        engine.wait(3000)
        self.assertFalse(engine.game_over)

    def test_move_rejected_when_source_empty(self):
        _, engine = self._make()
        result = self._move(engine, Position(0, 0), Position(0, 3))
        self.assertFalse(result.is_accepted)
        self.assertEqual(result.reason, 'empty_source')

    def test_move_rejected_when_illegal_for_piece(self):
        p = W(Kind.ROOK, 0, 0)
        _, engine = self._make(p)
        result = self._move(engine, Position(0, 0), Position(3, 3))  # rook can't move diagonally
        self.assertFalse(result.is_accepted)
        self.assertEqual(result.reason, 'illegal_piece_move')

    def test_jump_rejected_when_game_over(self):
        p = W(Kind.ROOK, 0, 0)
        _, engine = self._make(p)
        engine.force_game_over()
        result = self._jump(engine, Position(0, 0))
        self.assertFalse(result.is_accepted)
        self.assertEqual(result.reason, 'game_over')

    def test_jump_rejected_when_source_empty(self):
        _, engine = self._make()
        result = self._jump(engine, Position(0, 0))
        self.assertFalse(result.is_accepted)
        self.assertEqual(result.reason, 'empty_source')

    def test_get_cooldown_ratio_reflects_remaining_fraction(self):
        p = W(Kind.ROOK, 0, 0)
        _, engine = self._make(p, cooldown_ms=1000)
        self._move(engine, Position(0, 0), Position(0, 3))
        engine.wait(3000)  # arrives, cooldown starts
        ratio_start = engine.get_cooldown_ratio(p)
        self.assertGreater(ratio_start, 0.0)
        self.assertLessEqual(ratio_start, 1.0)
        engine.wait(1000)  # cooldown expires
        self.assertEqual(engine.get_cooldown_ratio(p), 0.0)

    def test_path_block_check_skips_cells_already_passed(self):
        """_check_path_blocks must skip path cells the piece has already
        travelled past (current_idx), scanning only what's ahead."""
        p = W(Kind.ROOK, 0, 0)
        _, engine = self._make(p)
        self._move(engine, Position(0, 0), Position(0, 5))  # 5 steps, arrival=5000
        engine.wait(2000)
        engine.wait(1000)  # second tick: current_idx > 0, earlier cells are skipped
        self.assertIsNone(engine.board.piece_at(Position(0, 5)))  # not yet arrived (clock=3000)

    def test_in_flight_motion_redirected_around_friendly_flying_into_its_path(self):
        """A second piece's own in-flight destination counts as an occupied
        cell for path-blocking purposes even before it physically arrives
        (the board only updates on arrival) -- so a friendly piece flying
        toward a cell on another piece's path must shorten that path."""
        a = W(Kind.ROOK, 0, 0)
        c = W(Kind.ROOK, 5, 2)
        b, engine = self._make(a, c)
        self._move(engine, Position(0, 0), Position(0, 5))  # A: would arrive at 5000ms
        self._move(engine, Position(5, 2), Position(0, 2))  # C: flies onto a cell on A's path
        engine.wait(100)
        engine.wait(900)  # total 1000ms: A's redirected arrival time
        self.assertEqual(b.piece_at(Position(0, 1)), a)
        self.assertIsNone(b.piece_at(Position(0, 0)))
        self.assertIsNone(b.piece_at(Position(0, 5)))


if __name__ == '__main__':
    unittest.main()
