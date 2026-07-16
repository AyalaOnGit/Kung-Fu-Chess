"""
Snapshot diffing: compare engine snapshots to detect game events.

The server's GameEngine.snapshot() returns a live view over the board,
not a point-in-time copy. We freeze snapshots here to fix that bug,
then diff them to infer events (piece arrived, captured, halted, etc.)
"""
from __future__ import annotations
import copy
from dataclasses import dataclass
from typing import Optional
from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Piece, Color
from kungfu_chess.model.position import Position


@dataclass
class FrozenSnapshot:
    """
    Point-in-time copy of a board state.
    
    Freezes the board so we can diff against it later without the snapshot
    changing when the engine advances. (The engine's snapshot() returns a live
    view, not a copy.)
    """
    pieces: dict[Position, Piece]  # Frozen copy of board._grid
    game_over: bool
    
    @staticmethod
    def from_board(board: Board, game_over: bool) -> FrozenSnapshot:
        """Create a frozen snapshot from a Board instance."""
        # Deep copy the grid
        pieces_copy = {}
        for pos, piece in board._grid.items():
            pieces_copy[pos] = copy.deepcopy(piece)
        
        return FrozenSnapshot(pieces=pieces_copy, game_over=game_over)
    
    def piece_at(self, pos: Position) -> Optional[Piece]:
        """Get piece at position in this frozen snapshot."""
        return self.pieces.get(pos)
    
    def all_pieces(self) -> list[Piece]:
        """Return all pieces in this snapshot."""
        return list(self.pieces.values())


def diff_snapshots(before: FrozenSnapshot, after: FrozenSnapshot,
                   piece_lookup: dict[int, Piece]) -> list[tuple[str, any]]:
    """
    Compare two snapshots and infer events.
    
    :param before: the state before tick
    :param after: the state after tick
    :param piece_lookup: mapping of piece.id -> piece for current board state
    :return: list of (event_type, event_data) tuples
    
    Event types:
      - 'piece_arrived': (piece, dst_pos)
      - 'piece_captured': (piece, capturer, pos)
      - 'piece_halted': (piece, halted_at)
      - 'promotion': (piece, new_kind)
      - 'game_over': (winner_color, loser_color)
    """
    events = []
    
    # Build reverse lookup: which piece ID moved or was captured?
    before_pieces_by_id = {p.id: (pos, p) for pos, p in before.pieces.items()}
    after_pieces_by_id = {p.id: (pos, p) for pos, p in after.pieces.items()}
    
    # Check for captures: pieces in 'before' but not in 'after'
    for piece_id, (old_pos, old_piece) in before_pieces_by_id.items():
        if piece_id not in after_pieces_by_id:
            # Piece was captured
            # Find the capturing piece (opponent piece is now where this one was)
            capturer_piece = after.piece_at(old_pos)
            if capturer_piece:
                events.append(('piece_captured', (old_piece, capturer_piece, old_pos)))
            else:
                events.append(('piece_captured', (old_piece, None, old_pos)))
    
    # Check for arrivals, halts, and other position changes
    for piece_id, (new_pos, new_piece) in after_pieces_by_id.items():
        if piece_id in before_pieces_by_id:
            old_pos, old_piece = before_pieces_by_id[piece_id]
            
            # Position changed
            if old_pos != new_pos:
                events.append(('piece_arrived', (new_piece, new_pos)))
            
            # Check for promotion
            if old_piece.kind != new_piece.kind:
                events.append(('promotion', (new_piece, old_piece.kind, new_piece.kind)))
    
    # Check for game over (if it just transitioned)
    if not before.game_over and after.game_over:
        # Someone won; infer by checking if a king is missing
        white_king = None
        black_king = None
        
        for piece in after.all_pieces():
            from kungfu_chess.model.piece import Kind, Color
            if piece.kind == Kind.KING:
                if piece.color == Color.WHITE:
                    white_king = piece
                else:
                    black_king = piece
        
        if white_king is None:
            events.append(('game_over', (Color.BLACK, Color.WHITE)))
        elif black_king is None:
            events.append(('game_over', (Color.WHITE, Color.BLACK)))
    
    return events
