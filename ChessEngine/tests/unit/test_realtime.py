import unittest
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Piece, Color, Kind, PieceState
from kungfu_chess.realtime.motion import travel_duration_ms, compute_path, Motion
from kungfu_chess.realtime.real_time_arbiter import RealTimeArbiter
from tests.conftest import W, B, board_with


class TestTravelDuration(unittest.TestCase):
    def test_one_square(self):
        self.assertEqual(travel_duration_ms(Position(0, 0), Position(0, 1)), 1000)

    def test_three_squares(self):
        self.assertEqual(travel_duration_ms(Position(0, 0), Position(0, 3)), 3000)

    def test_diagonal_uses_steps(self):
        self.assertEqual(travel_duration_ms(Position(0, 0), Position(3, 3)), 3000)


class TestComputePath(unittest.TestCase):
    def test_zero_distance_returns_empty_list(self):
        self.assertEqual(compute_path(Position(0, 0), Position(0, 0)), [])

    def test_knight_move_returns_dest_only(self):
        """Knight (and other non-ray) moves have no intermediate cells."""
        self.assertEqual(compute_path(Position(0, 0), Position(2, 1)), [Position(2, 1)])

    def test_straight_line_returns_every_intermediate_cell(self):
        self.assertEqual(
            compute_path(Position(0, 0), Position(0, 3)),
            [Position(0, 1), Position(0, 2), Position(0, 3)],
        )


class TestMotionCurrentStep(unittest.TestCase):
    def test_current_step_is_zero_when_path_is_empty(self):
        """A zero-length motion (src == dest) has an empty path; current_step
        must short-circuit to 0 rather than divide against an empty list."""
        p = W(Kind.ROOK, 0, 0)
        motion = Motion(piece=p, src=Position(0, 0), dest=Position(0, 0), arrival_time=0)
        self.assertEqual(motion.current_step(500), 0)


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

    def test_has_active_motion_for_color(self):
        p = W(Kind.ROOK, 0, 0)
        b, arb, _ = self._make(p)
        self.assertFalse(arb.has_active_motion_for_color(Color.WHITE))
        arb.start_motion(p, Position(0, 0), Position(0, 3))
        self.assertTrue(arb.has_active_motion_for_color(Color.WHITE))
        self.assertFalse(arb.has_active_motion_for_color(Color.BLACK))

    def test_redirect_motion_rescales_arrival_time_proportionally(self):
        p = W(Kind.ROOK, 0, 0)
        b, arb, _ = self._make(p)
        arb.start_motion(p, Position(0, 0), Position(0, 6))  # 6 steps, arrival=6000
        motion = arb.get_active_motions()[0]
        arb.redirect_motion(motion, Position(0, 3))          # shorten to 3 steps
        self.assertEqual(motion.dest, Position(0, 3))
        self.assertEqual(motion.arrival_time, 3000)
        self.assertEqual(
            motion.path,
            [Position(0, 1), Position(0, 2), Position(0, 3)],
        )

    def test_redirect_motion_is_noop_when_original_move_had_zero_steps(self):
        p = W(Kind.ROOK, 0, 0)
        b, arb, _ = self._make(p)
        arb.start_motion(p, Position(0, 0), Position(0, 0))  # zero-length motion
        motion = arb.get_active_motions()[0]
        arb.redirect_motion(motion, Position(0, 5))
        self.assertEqual(motion.dest, Position(0, 0))  # guarded no-op, unchanged

    def test_cooldown_ratio_for_reflects_remaining_time_and_zero_when_idle(self):
        p = W(Kind.ROOK, 0, 0)
        b, arb, _ = self._make(p, cooldown_ms=1000)
        self.assertEqual(arb.cooldown_ratio_for(p), 0.0)  # not cooling yet
        arb.start_motion(p, Position(0, 0), Position(0, 3))
        arb.advance_time(3000)  # arrives, cooldown starts (ready_time = 4000)
        ratio = arb.cooldown_ratio_for(p)
        self.assertGreater(ratio, 0.0)
        self.assertLessEqual(ratio, 1.0)
        arb.advance_time(1000)  # cooldown expires
        self.assertEqual(arb.cooldown_ratio_for(p), 0.0)

    def test_dest_occupied_by_friendly_one_square_away_stays_at_src_idle(self):
        """When the blocked destination is adjacent to src, the piece never
        actually moves at all, so it settles straight back to IDLE instead
        of entering a cooldown (unlike the multi-step case)."""
        p1 = W(Kind.ROOK, 0, 0)
        p2 = W(Kind.ROOK, 0, 1)
        b, arb, _ = self._make(p1, p2)
        arb.start_motion(p1, Position(0, 0), Position(0, 1))
        arb.advance_time(1000)
        self.assertEqual(b.piece_at(Position(0, 0)), p1)
        self.assertEqual(b.piece_at(Position(0, 1)), p2)
        self.assertEqual(p1.state, PieceState.IDLE)
        self.assertFalse(arb.is_on_cooldown(p1))

    def test_own_pending_arrival_dropped_after_piece_captured_mid_flight(self):
        """A piece can be captured at its original cell by a faster-arriving
        enemy while its own outbound motion is still in flight (the board
        keeps a piece logically on src until its motion resolves). When the
        stale motion's arrival_time is later reached, it must be a silent
        no-op instead of reviving or double-capturing the piece."""
        y = W(Kind.ROOK, 0, 0)
        z = B(Kind.ROOK, 3, 0)
        b, arb, captured = self._make(y, z)
        arb.start_motion(y, Position(0, 0), Position(0, 5))  # 5 steps, arrives at 5000
        arb.start_motion(z, Position(3, 0), Position(0, 0))  # 3 steps, arrives at 3000
        arb.advance_time(3000)
        self.assertEqual(captured, [y])
        self.assertEqual(b.piece_at(Position(0, 0)), z)
        self.assertEqual(y.state, PieceState.CAPTURED)

        arb.advance_time(2000)  # clock=5000: y's stale motion becomes due
        self.assertEqual(captured, [y])  # not double-fired
        self.assertIsNone(b.piece_at(Position(0, 5)))  # y never actually lands

    def test_jump_remains_active_before_landing_time(self):
        p = W(Kind.ROOK, 0, 0)
        b, arb, _ = self._make(p)
        arb.start_jump(p)
        arb.advance_time(500)  # JUMP_DURATION_MS default is 1000: still airborne
        self.assertTrue(arb.has_active_jump(Position(0, 0)))
        self.assertEqual(p.state, PieceState.JUMPING)

    def test_cooldown_ratio_for_returns_zero_when_cooling_state_has_no_timer_entry(self):
        """Defensive fallback: a piece can arrive already in COOLING state
        (e.g. reconstructed from a saved snapshot) in a freshly created
        arbiter that never registered a CooldownTimer for it -- the ratio
        lookup must not raise, it must just report 0.0."""
        p = W(Kind.ROOK, 0, 0)
        p.begin_cooldown()
        _, arb, _ = self._make()
        self.assertEqual(arb.cooldown_ratio_for(p), 0.0)

    def test_bounce_starts_cooldown_and_leaves_piece_at_src(self):
        p = W(Kind.ROOK, 0, 0)
        b, arb, _ = self._make(p, cooldown_ms=1000)
        arb.start_motion(p, Position(0, 0), Position(0, 3))
        motion = arb.get_active_motions()[0]
        arb._bounce(motion)
        self.assertTrue(arb.is_on_cooldown(p))
        self.assertEqual(b.piece_at(Position(0, 0)), p)


if __name__ == '__main__':
    unittest.main()
