import unittest
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece, Kind, PieceState
from kungfu_chess.realtime.motion import travel_duration_ms
from kungfu_chess.realtime.real_time_arbiter import RealTimeArbiter
from tests.conftest import W, B, board_with


class TestTravelDuration(unittest.TestCase):
    def test_one_square(self):
        self.assertEqual(travel_duration_ms(Position(0, 0), Position(0, 1)), 1000)

    def test_three_squares(self):
        self.assertEqual(travel_duration_ms(Position(0, 0), Position(0, 3)), 3000)

    def test_diagonal_uses_steps(self):
        self.assertEqual(travel_duration_ms(Position(0, 0), Position(3, 3)), 3000)


class TestRealTimeArbiter(unittest.TestCase):
    def _make(self, *pieces, cooldown_ms=0):
        b = board_with(*pieces)
        captured = []
        arb = RealTimeArbiter(
            b,
            on_piece_captured=lambda piece: captured.append(piece),
            on_piece_arrived=lambda piece: piece.try_promote(b.height),
            cooldown_ms=cooldown_ms,
        )
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

    def test_capture_triggers_callback_with_the_captured_piece(self):
        attacker = W(Kind.ROOK, 0, 0)
        king     = B(Kind.KING, 0, 3)
        b, arb, captured = self._make(attacker, king)
        arb.start_motion(attacker, Position(0, 0), Position(0, 3))
        arb.advance_time(3000)
        self.assertEqual(captured, [king])

    def test_non_royal_capture_also_triggers_callback(self):
        """The arbiter is chess-rule-agnostic: it reports every capture, not
        just kings -- deciding what a capture means (e.g. ending the game)
        is the caller's job."""
        attacker = W(Kind.ROOK, 0, 0)
        rook     = B(Kind.ROOK, 0, 3)
        b, arb, captured = self._make(attacker, rook)
        arb.start_motion(attacker, Position(0, 0), Position(0, 3))
        arb.advance_time(3000)
        self.assertEqual(captured, [rook])

    def test_airborne_captures_arriving_enemy(self):
        jumper = W(Kind.ROOK, 0, 0)
        enemy  = B(Kind.ROOK, 0, 1)
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

    def test_two_pieces_move_concurrently(self):
        p1 = W(Kind.ROOK, 0, 0)
        p2 = B(Kind.ROOK, 2, 0)
        b, arb, _ = self._make(p1, p2)
        arb.start_motion(p1, Position(0, 0), Position(0, 3))
        arb.start_motion(p2, Position(2, 0), Position(2, 3))
        arb.advance_time(3000)
        self.assertEqual(b.piece_at(Position(0, 3)), p1)
        self.assertEqual(b.piece_at(Position(2, 3)), p2)

    def test_collision_enemy_later_captures_earlier(self):
        p1 = W(Kind.ROOK, 0, 0)
        p2 = B(Kind.ROOK, 0, 6)
        b, arb, _ = self._make(p1, p2)
        arb.start_motion(p1, Position(0, 0), Position(0, 3))
        arb.start_motion(p2, Position(0, 6), Position(0, 3))
        arb.advance_time(3000)
        self.assertEqual(b.piece_at(Position(0, 3)), p2)
        self.assertEqual(p1.state, PieceState.CAPTURED)

    def test_dest_occupied_by_friendly_stops_one_before(self):
        p1 = W(Kind.ROOK, 0, 0)
        p2 = W(Kind.ROOK, 0, 3)
        b, arb, _ = self._make(p1, p2)
        arb.start_motion(p1, Position(0, 0), Position(0, 3))
        arb.advance_time(3000)
        self.assertEqual(b.piece_at(Position(0, 2)), p1)
        self.assertEqual(b.piece_at(Position(0, 3)), p2)
        self.assertIsNone(b.piece_at(Position(0, 0)))

    def test_enemy_arriving_later_captures_earlier_arrival(self):
        p1 = W(Kind.ROOK, 0, 2)  # 1 step, arrives at 1000ms
        p2 = B(Kind.ROOK, 0, 6)  # 3 steps, arrives at 3000ms
        b, arb, _ = self._make(p1, p2)
        arb.start_motion(p1, Position(0, 2), Position(0, 3))
        arb.start_motion(p2, Position(0, 6), Position(0, 3))
        arb.advance_time(3000)
        self.assertEqual(b.piece_at(Position(0, 3)), p2)
        self.assertEqual(p1.state, PieceState.CAPTURED)

    def test_cooldown_blocks_immediate_move(self):
        p = W(Kind.ROOK, 0, 0)
        b, arb, _ = self._make(p, cooldown_ms=1000)
        arb.start_motion(p, Position(0, 0), Position(0, 3))
        arb.advance_time(3000)
        self.assertTrue(arb.is_on_cooldown(p))

    def test_cooldown_expires_after_duration(self):
        p = W(Kind.ROOK, 0, 0)
        b, arb, _ = self._make(p, cooldown_ms=1000)
        arb.start_motion(p, Position(0, 0), Position(0, 3))
        arb.advance_time(3000 + 1000)
        self.assertFalse(arb.is_on_cooldown(p))


if __name__ == '__main__':
    unittest.main()
