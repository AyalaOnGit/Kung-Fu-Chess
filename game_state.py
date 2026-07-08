from piece_factory import PieceMovementFactory
from config import Piece, MOVE_DURATION_MS, JUMP_DURATION_MS, PIECE_CONFIG


class GameState:
    """Holds the full mutable state of a running game: board, clock, pending moves and jumps."""

    def __init__(self, board_lines, expected_width):
        """
        Initialize the game state from raw board text lines.

        :param board_lines: List of strings, each representing one board row (tokens separated by spaces).
        :param expected_width: Number of columns the board is expected to have.
        """
        self._board = [
            [None if token == '.' else Piece.from_token(token) for token in line.split()]
            for line in board_lines if line.split()
        ]
        self.height = len(self._board)
        self.width = expected_width
        self.clock = 0
        self.game_over = False
        self._pending_moves = []
        self._pending_jumps = []

    # --- Board access API (encapsulated) ---

    def get_piece(self, row, col):
        """Return the Piece at (row, col), or None if the cell is empty."""
        return self._board[row][col]

    def set_piece(self, row, col, piece):
        """Place a Piece at (row, col). Pass None to clear the cell."""
        self._board[row][col] = piece

    def is_empty(self, row, col):
        """Return True if the cell at (row, col) contains no piece."""
        return self._board[row][col] is None

    def get_board_rows(self):
        """
        Return the board as a 2-D list of display strings (e.g. 'wR' or '.').

        Returns a copy — safe for external use such as printing.
        """
        return [
            [str(cell) if cell is not None else '.' for cell in row]
            for row in self._board
        ]

    def in_bounds(self, row, col):
        """Return True if (row, col) is a valid cell within the board dimensions."""
        return 0 <= row < self.height and 0 <= col < self.width

    # --- Move / Jump queue API (encapsulated) ---

    def is_piece_moving(self, cell):
        """Return True if a piece from the given cell is currently in transit."""
        return any(m['src'] == cell for m in self._pending_moves)

    def is_piece_jumping(self, cell):
        """Return True if the piece at the given cell is currently airborne (mid-jump)."""
        return any(j['cell'] == cell for j in self._pending_jumps)

    def enqueue_move(self, src, dest, piece):
        """
        Schedule a piece to move from src to dest, arriving after MOVE_DURATION_MS.

        :param src: (row, col) origin cell.
        :param dest: (row, col) destination cell.
        :param piece: The Piece being moved.
        """
        self._pending_moves.append({
            'src': src,
            'dest': dest,
            'piece': piece,
            'arrival_time': self.clock + MOVE_DURATION_MS,
        })

    def enqueue_jump(self, cell, piece):
        """
        Schedule a piece to jump from its cell, landing after JUMP_DURATION_MS.

        :param cell: (row, col) of the jumping piece.
        :param piece: The Piece performing the jump.
        """
        self._pending_jumps.append({
            'cell': cell,
            'piece': piece,
            'landing_time': self.clock + JUMP_DURATION_MS,
        })

    # --- Move legality ---

    def is_legal_move(self, src, dest) -> bool:
        """
        Return True if moving the piece at src to dest is a valid move.

        Checks: same-cell, empty source, friendly-fire, and the piece's movement strategy.

        :param src: (row, col) of the piece to move.
        :param dest: (row, col) of the target cell.
        """
        if src == dest:
            return False
        piece = self.get_piece(*src)
        if piece is None:
            return False
        dest_piece = self.get_piece(*dest)
        if dest_piece is not None and dest_piece.color == piece.color:
            return False
        strategy = PieceMovementFactory.get_strategy(piece.type)
        if not strategy:
            return False
        return strategy.is_legal(self._board, src, dest, piece, self.height)

    # --- Time update (split into helpers) ---

    def update_time(self):
        """
        Resolve all pending moves and jumps whose time has come.

        Moves are processed in arrival-time order. Expired jumps are removed.
        """
        self._pending_moves.sort(key=lambda m: m['arrival_time'])
        self._pending_moves = self._resolve_moves()
        self._pending_jumps = [j for j in self._pending_jumps if self.clock < j['landing_time']]

    def _resolve_moves(self):
        """
        Iterate pending moves and apply those whose arrival_time has been reached.

        :return: List of moves that have not yet arrived and should remain pending.
        """
        remaining = []
        for move in self._pending_moves:
            if self.game_over or self.clock < move['arrival_time']:
                remaining.append(move)
                continue
            self._apply_move(move)
        return remaining

    def _apply_move(self, move):
        """
        Apply a single resolved move to the board, handling airborne capture,
        path re-validation, friendly-fire guard, royal capture, and promotion.

        :param move: A move dict with keys 'src', 'dest', 'piece', 'arrival_time'.
        """
        src, dest, piece = move['src'], move['dest'], move['piece']
        s_r, s_c = src
        d_r, d_c = dest

        if self.get_piece(s_r, s_c) != piece:
            return

        if self._is_captured_by_airborne(dest, piece, move['arrival_time']):
            self.set_piece(s_r, s_c, None)
            if self._is_royal(piece):
                self.game_over = True
            return

        dest_piece = self.get_piece(d_r, d_c)
        if dest_piece is not None and dest_piece.color == piece.color:
            return

        if not self._path_still_clear(src, dest, piece):
            return

        if dest_piece is not None and self._is_royal(dest_piece):
            self.game_over = True

        final_piece = self._apply_promotion(piece, d_r)
        self.set_piece(d_r, d_c, final_piece)
        self.set_piece(s_r, s_c, None)

    def _is_captured_by_airborne(self, dest, piece, arrival_time):
        """
        Return True if an enemy airborne piece is occupying dest during this move's arrival.

        :param dest: (row, col) the moving piece is heading to.
        :param piece: The moving Piece.
        :param arrival_time: The clock time at which the moving piece arrives.
        """
        return any(
            j['cell'] == dest and
            j['piece'].color != piece.color and
            arrival_time <= j['landing_time']
            for j in self._pending_jumps
        )

    def _path_still_clear(self, src, dest, piece):
        """
        Re-validate the path for sliding pieces (rook, bishop, queen) at arrival time.

        Pieces that do not require a clear path (king, knight, pawn) always return True.

        :param src: (row, col) origin of the move.
        :param dest: (row, col) destination of the move.
        :param piece: The Piece being moved.
        """
        strategy = PieceMovementFactory.get_strategy(piece.type)
        if strategy and getattr(strategy, 'needs_clear_path', False):
            return strategy.is_legal(self._board, src, dest, piece, self.height)
        return True

    def _is_royal(self, piece):
        """
        Return True if the piece is marked as royal in PIECE_CONFIG.

        :param piece: A Piece object.
        """
        return PIECE_CONFIG.get(piece.type, {}).get('is_royal', False)

    def _apply_promotion(self, piece, dest_row):
        """
        Return the promoted Piece if the piece reaches a promotion row, otherwise return it unchanged.

        :param piece: The Piece to potentially promote.
        :param dest_row: The row index the piece is moving to.
        """
        promotes_to = PIECE_CONFIG.get(piece.type, {}).get('promotes_to')
        if promotes_to and (dest_row == 0 or dest_row == self.height - 1):
            return Piece(color=piece.color, type=promotes_to)
        return piece
