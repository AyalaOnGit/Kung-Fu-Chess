import unittest
from game_state import GameState
from commands import ClickCommand, JumpCommand, WaitCommand, PrintBoardCommand, pixel_to_cell
from chess_pieces import KingMovement, KnightMovement, LinearMovement, PawnMovement
from piece_factory import PieceMovementFactory
from validator import validate_board
from config import CELL_SIZE_PX, MOVE_DURATION_MS, JUMP_DURATION_MS, PIECE_CONFIG, Piece, Color


def make_state(rows):
    return GameState(rows, len(rows[0].split()))


def make_context():
    return {'selected': None}


def P(token):
    """Shorthand: parse a piece token string into a Piece object."""
    return Piece.from_token(token)


# ---------------------------------------------------------------------------
# Piece / Color
# ---------------------------------------------------------------------------
class TestPiece(unittest.TestCase):
    def test_from_token(self):
        p = Piece.from_token('wR')
        self.assertEqual(p.color, Color.WHITE)
        self.assertEqual(p.type, 'R')

    def test_str(self):
        self.assertEqual(str(Piece.from_token('bK')), 'bK')

    def test_frozen(self):
        p = Piece.from_token('wQ')
        with self.assertRaises(Exception):
            p.type = 'R'

    def test_equality(self):
        self.assertEqual(Piece.from_token('wR'), Piece.from_token('wR'))
        self.assertNotEqual(Piece.from_token('wR'), Piece.from_token('bR'))

    def test_color_from_char(self):
        self.assertEqual(Color.from_char('w'), Color.WHITE)
        self.assertEqual(Color.from_char('b'), Color.BLACK)

    def test_color_from_char_invalid(self):
        with self.assertRaises(ValueError):
            Color.from_char('x')


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------
class TestConfig(unittest.TestCase):
    def test_royal_only_king(self):
        royals = [k for k, v in PIECE_CONFIG.items() if v['is_royal']]
        self.assertEqual(royals, ['K'])

    def test_pawn_promotes_to_queen(self):
        self.assertEqual(PIECE_CONFIG['P']['promotes_to'], 'Q')

    def test_cell_size_positive(self):
        self.assertGreater(CELL_SIZE_PX, 0)


# ---------------------------------------------------------------------------
# pixel_to_cell
# ---------------------------------------------------------------------------
class TestPixelToCell(unittest.TestCase):
    def test_top_left(self):
        self.assertEqual(pixel_to_cell(0, 0), (0, 0))

    def test_center_of_first_cell(self):
        self.assertEqual(pixel_to_cell(50, 50), (0, 0))

    def test_second_cell(self):
        self.assertEqual(pixel_to_cell(100, 100), (1, 1))

    def test_large_coords(self):
        self.assertEqual(pixel_to_cell(350, 250), (2, 3))


# ---------------------------------------------------------------------------
# validator
# ---------------------------------------------------------------------------
class TestValidator(unittest.TestCase):
    def test_valid_board(self):
        ok, w = validate_board(["wR wN wB wQ wK wB wN wR",
                                 "wP wP wP wP wP wP wP wP",
                                 ". . . . . . . .",
                                 "bP bP bP bP bP bP bP bP",
                                 "bR bN bB bQ bK bB bN bR"])
        self.assertTrue(ok)
        self.assertEqual(w, 8)

    def test_empty_board(self):
        ok, w = validate_board([])
        self.assertTrue(ok)
        self.assertEqual(w, 0)

    def test_row_width_mismatch(self):
        ok, msg = validate_board(["wK .", ". . ."])
        self.assertFalse(ok)
        self.assertIn("ROW_WIDTH_MISMATCH", msg)

    def test_unknown_token(self):
        ok, msg = validate_board(["wK xZ"])
        self.assertFalse(ok)
        self.assertIn("UNKNOWN_TOKEN", msg)

    def test_dot_is_valid(self):
        ok, _ = validate_board([". ."])
        self.assertTrue(ok)


# ---------------------------------------------------------------------------
# KingMovement
# ---------------------------------------------------------------------------
class TestKingMovement(unittest.TestCase):
    def setUp(self):
        self.board = [[P('wK'), None, None],
                      [None,   None, None],
                      [None,   None, None]]
        self.mv = KingMovement()

    def test_one_step_valid(self):
        self.assertTrue(self.mv.is_legal(self.board, (0, 0), (1, 1), P('wK'), 3))

    def test_two_steps_invalid(self):
        self.assertFalse(self.mv.is_legal(self.board, (0, 0), (2, 0), P('wK'), 3))

    def test_same_cell_handled_by_game_state(self):
        state = make_state(["wK . .", ". . .", ". . ."])
        self.assertFalse(state.is_legal_move((0, 0), (0, 0)))


# ---------------------------------------------------------------------------
# KnightMovement
# ---------------------------------------------------------------------------
class TestKnightMovement(unittest.TestCase):
    def setUp(self):
        self.board = [[None,    None, None, None],
                      [None,    P('wN'), None, None],
                      [None,    None, None, None],
                      [None,    None, None, None]]
        self.mv = KnightMovement()

    def test_valid_l_shape(self):
        self.assertTrue(self.mv.is_legal(self.board, (1, 1), (0, 3), P('wN'), 4))
        self.assertTrue(self.mv.is_legal(self.board, (1, 1), (3, 0), P('wN'), 4))

    def test_invalid_straight(self):
        self.assertFalse(self.mv.is_legal(self.board, (1, 1), (1, 3), P('wN'), 4))


# ---------------------------------------------------------------------------
# LinearMovement (Rook / Bishop / Queen)
# ---------------------------------------------------------------------------
class TestLinearMovement(unittest.TestCase):
    def setUp(self):
        self.board = [[None, None, None, None],
                      [None, None, None, None],
                      [None, None, None, None],
                      [None, None, None, None]]
        self.rook   = LinearMovement(allow_straight=True,  allow_diagonal=False)
        self.bishop = LinearMovement(allow_straight=False, allow_diagonal=True)
        self.queen  = LinearMovement(allow_straight=True,  allow_diagonal=True)

    def test_rook_straight(self):
        self.assertTrue(self.rook.is_legal(self.board, (0, 0), (0, 3), P('wR'), 4))

    def test_rook_diagonal_invalid(self):
        self.assertFalse(self.rook.is_legal(self.board, (0, 0), (2, 2), P('wR'), 4))

    def test_bishop_diagonal(self):
        self.assertTrue(self.bishop.is_legal(self.board, (0, 0), (3, 3), P('wB'), 4))

    def test_bishop_straight_invalid(self):
        self.assertFalse(self.bishop.is_legal(self.board, (0, 0), (0, 3), P('wB'), 4))

    def test_queen_both(self):
        self.assertTrue(self.queen.is_legal(self.board, (0, 0), (3, 3), P('wQ'), 4))
        self.assertTrue(self.queen.is_legal(self.board, (0, 0), (0, 3), P('wQ'), 4))

    def test_blocked_path(self):
        self.board[0][2] = P('bP')
        self.assertFalse(self.rook.is_legal(self.board, (0, 0), (0, 3), P('wR'), 4))

    def test_needs_clear_path_flag(self):
        self.assertTrue(self.rook.needs_clear_path)
        self.assertFalse(KingMovement().needs_clear_path)


# ---------------------------------------------------------------------------
# PawnMovement
# ---------------------------------------------------------------------------
class TestPawnMovement(unittest.TestCase):
    def _board(self, rows):
        return [
            [None if t == '.' else P(t) for t in r.split()]
            for r in rows
        ]

    def test_white_moves_up(self):
        board = self._board([". . .", "wP . .", ". . ."])
        self.assertTrue(PawnMovement().is_legal(board, (1, 0), (0, 0), P('wP'), 3))

    def test_white_cannot_move_down(self):
        board = self._board([". . .", "wP . .", ". . ."])
        self.assertFalse(PawnMovement().is_legal(board, (1, 0), (2, 0), P('wP'), 3))

    def test_black_moves_down(self):
        board = self._board([". bP .", ". . .", ". . ."])
        self.assertTrue(PawnMovement().is_legal(board, (0, 1), (1, 1), P('bP'), 3))

    def test_pawn_blocked_forward(self):
        board = self._board(["bP . .", "wP . .", ". . ."])
        self.assertFalse(PawnMovement().is_legal(board, (1, 0), (0, 0), P('wP'), 3))

    def test_pawn_diagonal_capture(self):
        board = self._board(["bP . .", "wP . .", ". . ."])
        self.assertFalse(PawnMovement().is_legal(board, (1, 0), (0, 0), P('wP'), 3))
        board[0][1] = P('bR')
        self.assertTrue(PawnMovement().is_legal(board, (1, 0), (0, 1), P('wP'), 3))

    def test_pawn_cannot_capture_forward(self):
        board = self._board(["bP . .", "wP . .", ". . ."])
        self.assertFalse(PawnMovement().is_legal(board, (1, 0), (0, 0), P('wP'), 3))

    def test_double_move_from_start(self):
        board = self._board([". . .", ". . .", "wP . .", ". . ."])
        self.assertTrue(PawnMovement().is_legal(board, (2, 0), (0, 0), P('wP'), 4))

    def test_double_move_blocked(self):
        board = self._board([". . .", "bP . .", "wP . .", ". . ."])
        self.assertFalse(PawnMovement().is_legal(board, (2, 0), (0, 0), P('wP'), 4))

    def test_double_move_not_from_start(self):
        board = self._board([". . .", ". . .", ". . .", "wP . ."])
        self.assertFalse(PawnMovement().is_legal(board, (3, 0), (1, 0), P('wP'), 4))


# ---------------------------------------------------------------------------
# PieceMovementFactory
# ---------------------------------------------------------------------------
class TestPieceMovementFactory(unittest.TestCase):
    def test_all_standard_pieces_registered(self):
        for p in ['K', 'Q', 'R', 'B', 'N', 'P']:
            self.assertIsNotNone(PieceMovementFactory.get_strategy(p))

    def test_unknown_piece_returns_none(self):
        self.assertIsNone(PieceMovementFactory.get_strategy('X'))

    def test_register_custom_strategy(self):
        class AlwaysLegal(KingMovement):
            def is_legal(self, board, src, dest, piece, height):
                return True

        PieceMovementFactory.register_strategy('X', AlwaysLegal())
        self.assertIsNotNone(PieceMovementFactory.get_strategy('X'))
        del PieceMovementFactory._strategies['X']


# ---------------------------------------------------------------------------
# GameState — board API
# ---------------------------------------------------------------------------
class TestGameStateAPI(unittest.TestCase):
    def setUp(self):
        self.state = make_state(["wK .", ". bK"])

    def test_get_piece(self):
        self.assertEqual(self.state.get_piece(0, 0), P('wK'))

    def test_set_piece(self):
        self.state.set_piece(0, 1, P('wR'))
        self.assertEqual(self.state.get_piece(0, 1), P('wR'))

    def test_is_empty(self):
        self.assertTrue(self.state.is_empty(0, 1))
        self.assertFalse(self.state.is_empty(0, 0))

    def test_in_bounds(self):
        self.assertTrue(self.state.in_bounds(0, 0))
        self.assertFalse(self.state.in_bounds(5, 5))

    def test_get_board_rows_returns_strings(self):
        rows = self.state.get_board_rows()
        self.assertEqual(rows[0][0], 'wK')
        self.assertEqual(rows[0][1], '.')

    def test_get_board_rows_is_copy(self):
        rows = self.state.get_board_rows()
        rows[0][0] = 'XX'
        self.assertEqual(self.state.get_piece(0, 0), P('wK'))


# ---------------------------------------------------------------------------
# GameState — move legality
# ---------------------------------------------------------------------------
class TestIsLegalMove(unittest.TestCase):
    def setUp(self):
        self.state = make_state(["wR . . .", ". . . .", ". . bR .", ". . . ."])

    def test_same_src_dest(self):
        self.assertFalse(self.state.is_legal_move((0, 0), (0, 0)))

    def test_empty_src(self):
        self.assertFalse(self.state.is_legal_move((0, 1), (0, 2)))

    def test_friendly_capture_blocked(self):
        self.state.set_piece(0, 3, P('wN'))
        self.assertFalse(self.state.is_legal_move((0, 0), (0, 3)))

    def test_legal_rook_move(self):
        self.assertTrue(self.state.is_legal_move((0, 0), (0, 3)))

    def test_rook_blocked(self):
        self.state.set_piece(0, 2, P('wN'))
        self.assertFalse(self.state.is_legal_move((0, 0), (0, 3)))


# ---------------------------------------------------------------------------
# GameState — move queue
# ---------------------------------------------------------------------------
class TestMoveQueue(unittest.TestCase):
    def setUp(self):
        self.state = make_state(["wR . . .", ". . . ."])

    def test_enqueue_move(self):
        self.state.enqueue_move((0, 0), (0, 3), P('wR'))
        self.assertTrue(self.state.is_piece_moving((0, 0)))

    def test_enqueue_jump(self):
        self.state.enqueue_jump((0, 0), P('wR'))
        self.assertTrue(self.state.is_piece_jumping((0, 0)))

    def test_piece_arrives_after_wait(self):
        self.state.enqueue_move((0, 0), (0, 3), P('wR'))
        self.state.clock += MOVE_DURATION_MS
        self.state.update_time()
        self.assertEqual(self.state.get_piece(0, 3), P('wR'))
        self.assertTrue(self.state.is_empty(0, 0))

    def test_piece_does_not_arrive_before_time(self):
        self.state.enqueue_move((0, 0), (0, 3), P('wR'))
        self.state.clock += MOVE_DURATION_MS - 1
        self.state.update_time()
        self.assertEqual(self.state.get_piece(0, 0), P('wR'))


# ---------------------------------------------------------------------------
# GameState — promotion
# ---------------------------------------------------------------------------
class TestPromotion(unittest.TestCase):
    def test_pawn_promotes_on_last_row(self):
        state = make_state([". . .", "wP . .", ". . ."])
        state.enqueue_move((1, 0), (0, 0), P('wP'))
        state.clock += MOVE_DURATION_MS
        state.update_time()
        self.assertEqual(state.get_piece(0, 0), P('wQ'))

    def test_pawn_no_promotion_mid_board(self):
        state = make_state([". . .", ". . .", "wP . .", ". . ."])
        state.enqueue_move((2, 0), (1, 0), P('wP'))
        state.clock += MOVE_DURATION_MS
        state.update_time()
        self.assertEqual(state.get_piece(1, 0), P('wP'))


# ---------------------------------------------------------------------------
# GameState — game over
# ---------------------------------------------------------------------------
class TestGameOver(unittest.TestCase):
    def test_capturing_king_ends_game(self):
        state = make_state(["wR bK", ". ."])
        state.enqueue_move((0, 0), (0, 1), P('wR'))
        state.clock += MOVE_DURATION_MS
        state.update_time()
        self.assertTrue(state.game_over)

    def test_moves_ignored_after_game_over(self):
        state = make_state(["wR bK", ". ."])
        state.enqueue_move((0, 0), (0, 1), P('wR'))
        state.clock += MOVE_DURATION_MS
        state.update_time()
        state.set_piece(1, 0, P('bR'))
        state.enqueue_move((1, 0), (0, 0), P('bR'))
        state.clock += MOVE_DURATION_MS
        state.update_time()
        self.assertEqual(state.get_piece(1, 0), P('bR'))


# ---------------------------------------------------------------------------
# GameState — jump mechanics
# ---------------------------------------------------------------------------
class TestJumpMechanics(unittest.TestCase):
    def test_airborne_piece_captures_arriving_enemy(self):
        state = make_state(["wR . .", ". . ."])
        state.enqueue_jump((0, 0), P('wR'))
        state.enqueue_move((0, 2), (0, 0), P('bR'))
        state.set_piece(0, 2, P('bR'))
        state.clock += JUMP_DURATION_MS
        state.update_time()
        self.assertTrue(state.is_empty(0, 2))
        self.assertEqual(state.get_piece(0, 0), P('wR'))

    def test_jump_expires_piece_stays(self):
        state = make_state(["wR . .", ". . ."])
        state.enqueue_jump((0, 0), P('wR'))
        state.clock += JUMP_DURATION_MS + 1
        state.update_time()
        self.assertEqual(state.get_piece(0, 0), P('wR'))


# ---------------------------------------------------------------------------
# ClickCommand
# ---------------------------------------------------------------------------
class TestClickCommand(unittest.TestCase):
    def _run(self, state, context, x, y):
        ClickCommand(x, y).execute(state, context)

    def test_click_selects_piece(self):
        state = make_state(["wR .", ". ."])
        ctx = make_context()
        self._run(state, ctx, 50, 50)
        self.assertEqual(ctx['selected'], (0, 0))

    def test_click_empty_no_selection(self):
        state = make_state(["wR .", ". ."])
        ctx = make_context()
        self._run(state, ctx, 150, 50)
        self.assertIsNone(ctx['selected'])

    def test_click_moves_piece(self):
        state = make_state(["wR .", ". ."])
        ctx = make_context()
        self._run(state, ctx, 50, 50)
        self._run(state, ctx, 150, 50)
        self.assertTrue(state.is_piece_moving((0, 0)))

    def test_click_outside_board_ignored(self):
        state = make_state(["wR .", ". ."])
        ctx = make_context()
        self._run(state, ctx, 50, 50)
        self._run(state, ctx, 9999, 9999)
        self.assertEqual(ctx['selected'], (0, 0))

    def test_click_replaces_selection_with_friendly(self):
        state = make_state(["wR wN", ". ."])
        ctx = make_context()
        self._run(state, ctx, 50, 50)
        self._run(state, ctx, 150, 50)
        self.assertEqual(ctx['selected'], (0, 1))

    def test_click_ignored_after_game_over(self):
        state = make_state(["wR .", ". ."])
        state.game_over = True
        ctx = make_context()
        self._run(state, ctx, 50, 50)
        self.assertIsNone(ctx['selected'])

    def test_click_moving_piece_ignored(self):
        state = make_state(["wR .", ". ."])
        ctx = make_context()
        state.enqueue_move((0, 0), (0, 1), P('wR'))
        self._run(state, ctx, 50, 50)
        self.assertIsNone(ctx['selected'])


# ---------------------------------------------------------------------------
# JumpCommand
# ---------------------------------------------------------------------------
class TestJumpCommand(unittest.TestCase):
    def _run(self, state, context, x, y):
        JumpCommand(x, y).execute(state, context)

    def test_jump_enqueues(self):
        state = make_state(["wR .", ". ."])
        ctx = make_context()
        self._run(state, ctx, 50, 50)
        self.assertTrue(state.is_piece_jumping((0, 0)))

    def test_jump_empty_cell_ignored(self):
        state = make_state(["wR .", ". ."])
        ctx = make_context()
        self._run(state, ctx, 150, 50)
        self.assertFalse(state.is_piece_jumping((0, 1)))

    def test_jump_outside_board_ignored(self):
        state = make_state(["wR .", ". ."])
        ctx = make_context()
        self._run(state, ctx, 9999, 9999)
        self.assertFalse(state.is_piece_jumping((0, 0)))

    def test_jump_already_moving_ignored(self):
        state = make_state(["wR .", ". ."])
        ctx = make_context()
        state.enqueue_move((0, 0), (0, 1), P('wR'))
        self._run(state, ctx, 50, 50)
        self.assertFalse(state.is_piece_jumping((0, 0)))

    def test_jump_ignored_after_game_over(self):
        state = make_state(["wR .", ". ."])
        state.game_over = True
        ctx = make_context()
        self._run(state, ctx, 50, 50)
        self.assertFalse(state.is_piece_jumping((0, 0)))


# ---------------------------------------------------------------------------
# WaitCommand
# ---------------------------------------------------------------------------
class TestWaitCommand(unittest.TestCase):
    def test_advances_clock(self):
        state = make_state(["wR .", ". ."])
        ctx = make_context()
        WaitCommand(500).execute(state, ctx)
        self.assertEqual(state.clock, 500)


# ---------------------------------------------------------------------------
# PrintBoardCommand
# ---------------------------------------------------------------------------
class TestPrintBoardCommand(unittest.TestCase):
    def test_prints_board(self):
        import io, sys
        state = make_state(["wR .", ". bK"])
        ctx = make_context()
        captured = io.StringIO()
        sys.stdout = captured
        PrintBoardCommand().execute(state, ctx)
        sys.stdout = sys.__stdout__
        output = captured.getvalue().strip().splitlines()
        self.assertEqual(output[0], "wR .")
        self.assertEqual(output[1], ". bK")


if __name__ == '__main__':
    unittest.main()
