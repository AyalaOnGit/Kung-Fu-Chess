"""
Per-piece animation state machine.

Each piece follows states: idle → move/jump → short_rest → idle, etc.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from kungfu_chess.model.piece import Piece, Kind, Color
from graphics.sprite_loader import SpriteLoader, SpriteConfig, SpriteFrame


class PieceAnimatorState(Enum):
    """Animation state of a piece."""
    IDLE = "idle"
    MOVING = "moving"
    JUMPING = "jumping"
    SHORT_REST = "short_rest"
    LONG_REST = "long_rest"


@dataclass
class PieceAnimator:
    """
    Manages animation playback for a single piece.
    
    Responsibilities:
      - Track current animation state
      - Advance frame based on elapsed time
      - Auto-transition to next state when animation finishes
      - Return current sprite frame
    """
    piece: Piece
    sprite_loader: SpriteLoader
    state: PieceAnimatorState = PieceAnimatorState.IDLE
    elapsed_ms: float = 0.0
    current_frame_index: int = 0
    
    # Cached
    _current_config: Optional[SpriteConfig] = field(default=None, init=False)
    _current_frames: Optional[list[SpriteFrame]] = field(default=None, init=False)
    
    def _piece_code(self) -> str:
        """Return the piece code: e.g. QB (queen black), NW (knight white)."""
        kind_char = self.piece.kind.value
        color_char = self.piece.color.value
        return f"{kind_char}{color_char}"
    
    def _load_animation(self, state: PieceAnimatorState) -> None:
        """Load sprites and config for the given state."""
        piece_code = self._piece_code()
        try:
            self._current_frames = self.sprite_loader.load_frames(piece_code, state.value)
            self._current_config = self.sprite_loader.get_config(piece_code, state.value)
        except FileNotFoundError:
            # Fallback to idle if state not found
            if state != PieceAnimatorState.IDLE:
                self._load_animation(PieceAnimatorState.IDLE)
            else:
                # Create a blank frame as last resort
                import numpy as np
                blank = np.zeros((100, 100, 4), dtype=np.uint8)
                self._current_frames = [SpriteFrame(image=blank, duration_ms=100.0)]
                self._current_config = SpriteConfig(
                    frames_per_sec=10.0,
                    is_loop=True,
                    next_state_when_finished="idle"
                )
    
    def set_state(self, state: PieceAnimatorState) -> None:
        """
        Change the animation state and reset frame timing.
        
        :param state: new PieceAnimatorState
        """
        if self.state == state:
            return
        
        self.state = state
        self.elapsed_ms = 0.0
        self.current_frame_index = 0
        self._load_animation(state)
    
    def tick(self, dt_ms: float) -> Optional[str]:
        """
        Advance time by dt_ms and check for state transitions.
        
        :param dt_ms: milliseconds elapsed
        :return: new state to transition to, or None if no transition
        """
        if self._current_frames is None or self._current_config is None:
            self._load_animation(self.state)
        
        self.elapsed_ms += dt_ms
        frames = self._current_frames
        config = self._current_config
        
        # Calculate frame duration
        total_duration_ms = sum(f.duration_ms for f in frames)
        
        # Handle looping
        if self.elapsed_ms >= total_duration_ms:
            if config.is_loop:
                self.elapsed_ms = self.elapsed_ms % total_duration_ms
            else:
                # Animation finished, transition to next state
                self.set_state(PieceAnimatorState(config.next_state_when_finished))
                return config.next_state_when_finished
        
        # Calculate which frame to display
        accumulated_ms = 0.0
        for i, frame in enumerate(frames):
            accumulated_ms += frame.duration_ms
            if self.elapsed_ms < accumulated_ms:
                self.current_frame_index = i
                break
        else:
            # Shouldn't happen, but default to last frame
            self.current_frame_index = len(frames) - 1
        
        return None
    
    def get_current_frame(self) -> SpriteFrame:
        """Return the current sprite frame to draw."""
        if self._current_frames is None:
            self._load_animation(self.state)
        
        if not self._current_frames:
            # Fallback: blank frame
            import numpy as np
            blank = np.zeros((100, 100, 4), dtype=np.uint8)
            return SpriteFrame(image=blank, duration_ms=100.0)
        
        return self._current_frames[self.current_frame_index]
