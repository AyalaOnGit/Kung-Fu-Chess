"""
NetworkGameFacade: server-authoritative counterpart to state/game_facade.py's
GameFacade. Exposes the same public interface (subscribe, request_click,
request_jump, tick, get_selected_pos, get_cooldown_ratio, get_pending_motion)
so BoardRenderer/HudRenderer/ui_components/* work against it unmodified --
only UI/main.py needs to know which one it's holding.

Where GameFacade owns a local GameEngine and mutates it directly on every
click, NetworkGameFacade owns a *mirror* kungfu_chess.model.board.Board that
it only ever updates in response to wire events broadcast by
MultiplayerServer -- clicks/jumps are sent as commands and applied locally
only once the server's own broadcast confirms them (§2 of the spec:
"sending commands; receiving game state"). Motion/cooldown timing is
predicted client-side the same way GameFacade already predicts it (same
kungfu_chess.config constants), since the server streams accept/arrive/
capture events, not per-frame positions.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional

from kungfu_chess.config import COOLDOWN_MS, JUMP_DURATION_MS
from kungfu_chess.interaction.board_mapper import BoardMapper
from kungfu_chess.model.board import Board
from kungfu_chess.model.piece import Color, Kind, Piece, PieceState
from kungfu_chess.model.position import Position

from animation.motion_predictor import PixelMotion, duration_for_move_ms
from network.protocol import Envelope
from network.ws_client import WsClient
from state.game_events import (
    GameEvent, GameOver, MoveAccepted, OpponentDisconnected, PieceArrived,
    PieceCaptured, PieceHalted, Promotion, RatingUpdate,
)
from state.observer import Subject

_ROLE_TO_COLOR = {'white': Color.WHITE, 'black': Color.BLACK}


@dataclass
class PendingMotionData:
    """Tracks a piece in motion. Mirrors state/game_facade.py's own."""
    piece: Piece
    src_pos: Position
    dst_pos: Position
    is_jump: bool
    motion_start_time_ms: float
    motion_end_time_ms: float


def _piece_from_wire(data: Optional[dict]) -> Optional[Piece]:
    """Build a standalone Piece from a game/wire.py::_piece() dict. Used for
    event payloads (ScorePanel/MovesLogPanel only read color/kind/id off
    these); board identity is tracked separately via _find_piece()."""
    if data is None:
        return None
    row, col = data['cell']
    return Piece(id=data['id'], color=Color(data['color']), kind=Kind(data['kind']), cell=Position(row, col))


def board_from_state(state: dict) -> Board:
    """Build a mirror Board from a state_sync-shaped payload (the 'state'
    field of room_created/room_joined/match_found, or a login-reconnect
    state_sync envelope's data['state'])."""
    board = Board(width=8, height=8)
    for entry in state['pieces']:
        piece = _piece_from_wire(entry)
        piece.state = PieceState(entry.get('state', 'idle'))
        board.add_piece(piece)
    return board


class NetworkGameFacade:
    """
    :param ws_client: connected WsClient for this room.
    :param mapper: same BoardMapper the local facade uses.
    :param initial_state: the 'state' payload from room_created/room_joined/
        match_found -- seeds the mirror board and any in-progress cooldowns.
    :param my_role: 'white', 'black', or 'viewer'. Viewers can look but
        request_click/request_jump are no-ops for them, matching the
        server's own viewer_read_only gate.
    """

    def __init__(self, ws_client: WsClient, mapper: BoardMapper, initial_state: dict, my_role: str):
        self._ws = ws_client
        self._mapper = mapper
        self._my_color: Optional[Color] = _ROLE_TO_COLOR.get(my_role)
        self._is_viewer = self._my_color is None

        self._subject: Subject[GameEvent] = Subject()
        self._selected: Optional[Position] = None
        self._pending_motions: Dict[int, PendingMotionData] = {}
        self._cooldowns: Dict[int, float] = {}
        self._clock_ms: float = 0.0

        self._board = board_from_state(initial_state)
        self._seed_cooldowns(initial_state)

    def _seed_cooldowns(self, state: dict) -> None:
        for entry in state['pieces']:
            if entry.get('state') == 'cooling' and 'cooldown_ratio' in entry:
                remaining_ms = entry['cooldown_ratio'] * COOLDOWN_MS
                self._cooldowns[entry['id']] = self._clock_ms + remaining_ms

    @property
    def board(self) -> Board:
        return self._board

    @property
    def my_color(self) -> Optional[Color]:
        return self._my_color

    # --- event publishing ---

    def subscribe(self, callback) -> None:
        self._subject.subscribe(callback)

    # --- user input routing ---

    def request_click(self, x: int, y: int) -> bool:
        """Same selection semantics as kungfu_chess.interaction.controller.Controller,
        against the mirror board, gated to pieces of my_color. Returns True
        if this was a destination click (2nd click)."""
        if self._is_viewer or not self._mapper.in_bounds_px(x, y):
            return False
        pos = self._mapper.pixel_to_position(x, y)

        if self._selected is None:
            piece = self._board.piece_at(pos)
            if piece is not None and piece.color is self._my_color:
                self._selected = pos
            return False

        clicked = self._board.piece_at(pos)
        selected_piece = self._board.piece_at(self._selected)
        if clicked is not None and selected_piece is not None and clicked.color == selected_piece.color:
            self._selected = pos
            return False

        src = self._selected
        self._selected = None
        self._ws.send('move', {'src': [src.row, src.col], 'dest': [pos.row, pos.col]})
        return True

    def request_jump(self, x: int, y: int) -> None:
        if self._is_viewer or not self._mapper.in_bounds_px(x, y):
            return
        pos = self._mapper.pixel_to_position(x, y)
        piece = self._board.piece_at(pos)
        if piece is None or piece.color is not self._my_color:
            return
        self._selected = None
        self._ws.send('jump', {'cell': [pos.row, pos.col]})

    # --- core loop ---

    def tick(self, dt_ms: float) -> None:
        self._clock_ms += dt_ms
        self._resolve_expired_cooldowns()
        for envelope in self._ws.poll_events():
            self._handle_envelope(envelope)

    def _resolve_expired_cooldowns(self) -> None:
        expired_ids = [pid for pid, end_ms in self._cooldowns.items() if self._clock_ms >= end_ms]
        for piece_id in expired_ids:
            del self._cooldowns[piece_id]
            piece = self._find_piece(piece_id)
            if piece is not None and piece.state is PieceState.COOLING:
                piece.state = PieceState.IDLE

    def _find_piece(self, piece_id: int) -> Optional[Piece]:
        for piece in self._board.all_pieces():
            if piece.id == piece_id:
                return piece
        return None

    # --- wire event handling ---

    def _handle_envelope(self, envelope: Envelope) -> None:
        if envelope.type == 'move_accepted':
            self._on_move_accepted(envelope.data)
        elif envelope.type == 'jump_accepted':
            self._on_jump_accepted(envelope.data)
        elif envelope.type == 'piece_arrived':
            self._on_piece_arrived(envelope.data)
        elif envelope.type == 'piece_captured':
            self._on_piece_captured(envelope.data)
        elif envelope.type == 'promotion':
            self._on_promotion(envelope.data)
        elif envelope.type == 'game_over':
            self._on_game_over(envelope.data)
        elif envelope.type == 'opponent_disconnected':
            self._on_opponent_disconnected(envelope.data)
        elif envelope.type == 'rating_update':
            self._on_rating_update(envelope.data)
        elif envelope.type == 'state_sync':
            self._on_state_sync(envelope.data)
        # Anything else (accepted/error/pong/registered/...) is a direct
        # command reply the lobby/home-shell already consumed, or simply
        # not relevant to gameplay -- ignored here.

    def _on_move_accepted(self, data: dict) -> None:
        piece = self._find_piece(data['piece']['id'])
        if piece is None:
            return
        src, dest = Position(*data['src']), Position(*data['dest'])
        piece.state = PieceState.MOVING
        self._start_pending_motion(piece, src, dest, is_jump=False)
        self._subject.publish(MoveAccepted(piece=piece, src_pos=src, dst_pos=dest))

    def _on_jump_accepted(self, data: dict) -> None:
        piece = self._find_piece(data['piece']['id'])
        if piece is None:
            return
        cell = Position(*data['cell'])
        piece.state = PieceState.JUMPING
        self._start_pending_motion(piece, cell, cell, is_jump=True)
        # No UI event here -- the local GameFacade doesn't publish one for
        # jump acceptance either, only PieceArrived on completion.

    def _start_pending_motion(self, piece: Piece, src: Position, dst: Position, is_jump: bool) -> None:
        duration_ms = float(JUMP_DURATION_MS) if is_jump else duration_for_move_ms(src, dst)
        self._pending_motions[piece.id] = PendingMotionData(
            piece=piece, src_pos=src, dst_pos=dst, is_jump=is_jump,
            motion_start_time_ms=self._clock_ms, motion_end_time_ms=self._clock_ms + duration_ms,
        )

    def _on_piece_arrived(self, data: dict) -> None:
        piece = self._find_piece(data['piece']['id'])
        if piece is None:
            return  # unknown locally (e.g. joined mid-motion) -- next event will resync
        actual_pos = Position(*data['pos'])
        pending = self._pending_motions.pop(piece.id, None)

        if pending is not None and not pending.is_jump and pending.dst_pos != actual_pos:
            self._subject.publish(PieceHalted(piece=piece, halted_at=actual_pos))

        if piece.cell != actual_pos:
            self._board.move_piece(piece.cell, actual_pos)

        piece.state = PieceState.COOLING
        self._cooldowns[piece.id] = self._clock_ms + COOLDOWN_MS
        self._subject.publish(PieceArrived(piece=piece, pos=actual_pos))

    def _on_piece_captured(self, data: dict) -> None:
        # Board mutation already happened via the paired piece_arrived
        # (Board.move_piece implicitly evicts whatever occupied the
        # destination cell) -- this event is purely informational, for
        # ScorePanel/SoundManager/move history.
        piece = _piece_from_wire(data['piece'])
        capturer = _piece_from_wire(data['capturer'])
        pos = Position(*data['pos'])
        self._subject.publish(PieceCaptured(piece=piece, capturer=capturer, pos=pos))

    def _on_promotion(self, data: dict) -> None:
        old_kind, new_kind = Kind(data['old_kind']), Kind(data['new_kind'])
        piece = self._find_piece(data['piece']['id'])
        if piece is not None:
            piece.kind = new_kind
            pos = piece.cell
        else:
            piece = _piece_from_wire(data['piece'])
            pos = piece.cell
        self._subject.publish(Promotion(piece=piece, old_kind=old_kind, new_kind=new_kind, pos=pos))

    def _on_game_over(self, data: dict) -> None:
        self._subject.publish(GameOver(winner=Color(data['winner']), loser=Color(data['loser'])))

    def _on_opponent_disconnected(self, data: dict) -> None:
        self._subject.publish(OpponentDisconnected(grace_seconds=data.get('grace_seconds', 20.0)))

    def _on_rating_update(self, data: dict) -> None:
        self._subject.publish(RatingUpdate(
            white_elo_before=data['white_elo_before'], white_elo_after=data['white_elo_after'],
            black_elo_before=data['black_elo_before'], black_elo_after=data['black_elo_after'],
        ))

    def _on_state_sync(self, data: dict) -> None:
        """
        Full resync -- e.g. this client reconnected mid-game via login.

        Mutates the existing Board in place rather than rebinding
        self._board to a new instance: BoardRenderer is constructed once,
        holding a direct reference to this board, so replacing the
        attribute here would leave it rendering a stale snapshot forever.
        """
        state = data['state']
        fresh_board = board_from_state(state)
        self._board._grid.clear()
        self._board._grid.update(fresh_board._grid)
        self._pending_motions.clear()
        self._cooldowns.clear()
        self._seed_cooldowns(state)

    # --- motion/cooldown prediction (mirrors state/game_facade.py exactly) ---

    def get_selected_pos(self) -> Optional[Position]:
        return self._selected

    def get_cooldown_ratio(self, piece: Piece) -> float:
        end_ms = self._cooldowns.get(piece.id)
        if end_ms is None:
            return 0.0
        remaining_ms = end_ms - self._clock_ms
        return max(0.0, min(1.0, remaining_ms / COOLDOWN_MS))

    def get_pending_motion(self, piece_id: int) -> Optional[tuple[PixelMotion, float]]:
        motion_data = self._pending_motions.get(piece_id)
        if not motion_data:
            return None

        elapsed_ms = self._clock_ms - motion_data.motion_start_time_ms
        src_px = self._mapper.cell_center_pixel(motion_data.src_pos)
        dst_px = self._mapper.cell_center_pixel(motion_data.dst_pos)
        duration_ms = float(JUMP_DURATION_MS) if motion_data.is_jump \
            else duration_for_move_ms(motion_data.src_pos, motion_data.dst_pos)

        return PixelMotion(src_px=src_px, dst_px=dst_px, duration_ms=duration_ms), elapsed_ms
