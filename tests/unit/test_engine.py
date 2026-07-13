import unittest
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Kind
from kungfu_chess.engine.commands import MoveCommand, JumpCommand
from kungfu_chess.factory import build_engine
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


if __name__ == '__main__':
    unittest.main()
