import unittest
from kungfu_chess.model.position import Position
from kungfu_chess.model.piece import Kind
from kungfu_chess.observation.snapshot_diff import FrozenSnapshot, diff_snapshots
from tests.conftest import W, B, board_with


class TestFrozenSnapshot(unittest.TestCase):
    def test_from_board_copies_current_pieces(self):
        p = W(Kind.ROOK, 0, 0)
        b = board_with(p)
        snap = FrozenSnapshot.from_board(b, game_over=False)
        self.assertEqual(snap.piece_at(Position(0, 0)).id, p.id)
        self.assertEqual(snap.all_pieces(), [snap.piece_at(Position(0, 0))])
        self.assertFalse(snap.game_over)

    def test_snapshot_is_independent_of_later_board_mutation(self):
        """FrozenSnapshot deep-copies each piece, so mutating the live board
        afterwards must not retroactively change a snapshot already taken."""
        p = W(Kind.ROOK, 0, 0)
        b = board_with(p)
        snap = FrozenSnapshot.from_board(b, game_over=False)

        b.move_piece(Position(0, 0), Position(0, 3))

        self.assertEqual(snap.piece_at(Position(0, 0)).id, p.id)
        self.assertIsNone(snap.piece_at(Position(0, 3)))

    def test_piece_at_returns_none_for_empty_cell(self):
        snap = FrozenSnapshot.from_board(board_with(), game_over=False)
        self.assertIsNone(snap.piece_at(Position(0, 0)))


class TestDiffSnapshots(unittest.TestCase):
    def test_no_changes_yields_no_events(self):
        p = W(Kind.ROOK, 0, 0)
        b = board_with(p)
        snap = FrozenSnapshot.from_board(b, game_over=False)
        self.assertEqual(diff_snapshots(snap, snap, {}), [])

    def test_position_change_yields_piece_arrived(self):
        p = W(Kind.ROOK, 0, 0)
        b = board_with(p)
        before = FrozenSnapshot.from_board(b, game_over=False)
        b.move_piece(Position(0, 0), Position(0, 3))
        after = FrozenSnapshot.from_board(b, game_over=False)

        events = diff_snapshots(before, after, {})

        self.assertEqual(len(events), 1)
        event_type, (piece, pos) = events[0]
        self.assertEqual(event_type, 'piece_arrived')
        self.assertEqual(piece.id, p.id)
        self.assertEqual(pos, Position(0, 3))

    def test_disappearing_piece_yields_piece_captured_with_capturer(self):
        attacker = W(Kind.ROOK, 0, 0)
        target = B(Kind.ROOK, 0, 3)
        b = board_with(attacker, target)
        before = FrozenSnapshot.from_board(b, game_over=False)
        b.move_piece(Position(0, 0), Position(0, 3))
        after = FrozenSnapshot.from_board(b, game_over=False)

        events = diff_snapshots(before, after, {})

        captured_events = [e for e in events if e[0] == 'piece_captured']
        self.assertEqual(len(captured_events), 1)
        _, (piece, capturer, pos) = captured_events[0]
        self.assertEqual(piece.id, target.id)
        self.assertEqual(capturer.id, attacker.id)
        self.assertEqual(pos, Position(0, 3))

    def test_kind_change_yields_promotion(self):
        p = W(Kind.PAWN, 1, 0)
        b = board_with(p)
        before = FrozenSnapshot.from_board(b, game_over=False)
        p.kind = Kind.QUEEN
        after = FrozenSnapshot.from_board(b, game_over=False)

        events = diff_snapshots(before, after, {})

        self.assertEqual(len(events), 1)
        event_type, (piece, old_kind, new_kind) = events[0]
        self.assertEqual(event_type, 'promotion')
        self.assertEqual(old_kind, Kind.PAWN)
        self.assertEqual(new_kind, Kind.QUEEN)

    def test_white_king_missing_yields_black_wins(self):
        white_king = W(Kind.KING, 0, 0)
        black_king = B(Kind.KING, 7, 7)
        b = board_with(white_king, black_king)
        before = FrozenSnapshot.from_board(b, game_over=False)
        b.remove_piece(Position(0, 0))
        after = FrozenSnapshot.from_board(b, game_over=True)

        events = diff_snapshots(before, after, {})

        game_over_events = [e for e in events if e[0] == 'game_over']
        self.assertEqual(len(game_over_events), 1)
        _, (winner, loser) = game_over_events[0]
        from kungfu_chess.model.piece import Color
        self.assertEqual(winner, Color.BLACK)
        self.assertEqual(loser, Color.WHITE)

    def test_black_king_missing_yields_white_wins(self):
        white_king = W(Kind.KING, 0, 0)
        black_king = B(Kind.KING, 7, 7)
        b = board_with(white_king, black_king)
        before = FrozenSnapshot.from_board(b, game_over=False)
        b.remove_piece(Position(7, 7))
        after = FrozenSnapshot.from_board(b, game_over=True)

        events = diff_snapshots(before, after, {})

        game_over_events = [e for e in events if e[0] == 'game_over']
        self.assertEqual(len(game_over_events), 1)
        _, (winner, loser) = game_over_events[0]
        from kungfu_chess.model.piece import Color
        self.assertEqual(winner, Color.WHITE)
        self.assertEqual(loser, Color.BLACK)

    def test_game_over_already_true_before_yields_no_new_game_over_event(self):
        """Only the before->after transition should fire -- a diff between
        two already-game-over snapshots must not re-fire it."""
        p = W(Kind.KING, 0, 0)
        b = board_with(p)
        snap = FrozenSnapshot.from_board(b, game_over=True)

        events = diff_snapshots(snap, snap, {})

        self.assertEqual([e for e in events if e[0] == 'game_over'], [])


if __name__ == '__main__':
    unittest.main()
