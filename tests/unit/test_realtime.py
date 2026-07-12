import unittest
from unittest.mock import patch
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
    def _make(self, *pieces):
        b = board_with(*pieces)
        captured = []

        def on_piece_arrived(piece):
            promoted_kind = Piece.promotion_kind(piece.kind)
            if promoted_kind is not None and piece.cell.row == Piece.promotion_row(piece.color, b.height):
                piece.kind = promoted_kind

        arb = RealTimeArbiter(
            b,
            on_king_captured=lambda: captured.append(True),
            on_piece_arrived=on_piece_arrived,
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

    def test_king_capture_triggers_callback(self):
        attacker = W(Kind.ROOK, 0, 0)
        king     = B(Kind.KING, 0, 3)
        b, arb, captured = self._make(attacker, king)
        arb.start_motion(attacker, Position(0, 0), Position(0, 3))
        arb.advance_time(3000)
        self.assertTrue(captured)

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

    def test_collision_both_pieces_stay(self):
        p1 = W(Kind.ROOK, 0, 0)
        p2 = B(Kind.ROOK, 0, 6)
        b, arb, _ = self._make(p1, p2)
        arb.start_motion(p1, Position(0, 0), Position(0, 3))
        arb.start_motion(p2, Position(0, 6), Position(0, 3))
        arb.advance_time(3000)
        self.assertEqual(b.piece_at(Position(0, 0)), p1)
        self.assertEqual(b.piece_at(Position(0, 6)), p2)
        self.assertIsNone(b.piece_at(Position(0, 3)))

    def test_dest_occupied_by_friendly_cancels_motion(self):
        p1 = W(Kind.ROOK, 0, 0)
        p2 = W(Kind.ROOK, 0, 3)
        b, arb, _ = self._make(p1, p2)
        arb.start_motion(p1, Position(0, 0), Position(0, 3))
        arb.advance_time(3000)
        self.assertEqual(b.piece_at(Position(0, 0)), p1)
        self.assertEqual(b.piece_at(Position(0, 3)), p2)

    @patch('kungfu_chess.realtime.real_time_arbiter.COOLDOWN_MS', 1000)
    def test_cooldown_blocks_immediate_remove(self):
        p = W(Kind.ROOK, 0, 0)
        b, arb, _ = self._make(p)
        arb.start_motion(p, Position(0, 0), Position(0, 3))
        arb.advance_time(3000)
        self.assertTrue(arb.is_on_cooldown(p))

    @patch('kungfu_chess.realtime.real_time_arbiter.COOLDOWN_MS', 1000)
    def test_cooldown_expires_after_duration(self):
        p = W(Kind.ROOK, 0, 0)
        b, arb, _ = self._make(p)
        arb.start_motion(p, Position(0, 0), Position(0, 3))
        arb.advance_time(3000 + 1000)
        self.assertFalse(arb.is_on_cooldown(p))


if __name__ == '__main__':
    unittest.main()
