"""
Sprite loader: loads and caches piece animation frames.

Reads piece sprites and config from pieces/ directories,
organized as <PIECE_CODE>/states/<STATE>/sprites/*.png and config.json
"""
from __future__ import annotations
import json
import pathlib
from dataclasses import dataclass
from typing import Optional
import numpy as np

from vendor.img import Img

@dataclass
class SpriteConfig:
    """Configuration for a piece state's animation."""
    frames_per_sec: float
    is_loop: bool
    next_state_when_finished: str


@dataclass
class SpriteFrame:
    """A single sprite frame."""
    image: np.ndarray  # BGR or BGRA numpy array
    duration_ms: float  # milliseconds this frame should be displayed


class SpriteLoader:
    """
    Loads and caches piece sprite animations.
    
    Responsibilities:
      - Load and cache sprite PNG files per (piece_code, state)
      - Parse state config.json for animation parameters
      - Return frame sequences and metadata
    """
    
    def __init__(self, pieces_dir: pathlib.Path):
        """
        Initialize sprite loader with a pieces directory.
        
        :param pieces_dir: path to pieces1/ or pieces3/ directory
        """
        self._pieces_dir = pathlib.Path(pieces_dir)
        self._cache: dict[tuple[str, str], list[SpriteFrame]] = {}
        self._config_cache: dict[tuple[str, str], SpriteConfig] = {}
    
    def load_frames(self, piece_code: str, state: str) -> list[SpriteFrame]:
        """
        Load all sprite frames for a piece in a given state.
        
        piece_code: e.g. "QB", "NW", "RB"
        state: e.g. "idle", "move", "jump", "short_rest", "long_rest"
        
        :return: list of SpriteFrame objects in order
        :raises FileNotFoundError: if piece or state not found
        """
        key = (piece_code, state)
        if key in self._cache:
            return self._cache[key]
        
        # Construct path: pieces/QB/states/idle/sprites/
        base_piece_dir = self._pieces_dir / piece_code

        # Handle case where assets are nested like `assets/pieces1/pieces1/RB/...`
        if not base_piece_dir.exists():
            # If pieces_dir contains a single subdirectory (e.g. 'pieces1'), try that
            try:
                children = [p for p in self._pieces_dir.iterdir() if p.is_dir()]
            except Exception:
                children = []
            if len(children) == 1 and (children[0] / piece_code).exists():
                base_piece_dir = children[0] / piece_code

        state_dir = base_piece_dir / "states" / state
        sprites_dir = state_dir / "sprites"
        config_file = state_dir / "config.json"
        
        if not config_file.exists():
            raise FileNotFoundError(f"No config for {piece_code} {state}: {config_file}")
        if not sprites_dir.exists():
            raise FileNotFoundError(f"No sprites dir: {sprites_dir}")
        
        # Load config
        with open(config_file, 'r') as f:
            cfg_data = json.load(f)
        
        fps = cfg_data['graphics']['frames_per_sec']
        is_loop = cfg_data['graphics']['is_loop']
        next_state = cfg_data['physics'].get('next_state_when_finished', 'idle')
        
        config = SpriteConfig(
            frames_per_sec=fps,
            is_loop=is_loop,
            next_state_when_finished=next_state
        )
        self._config_cache[key] = config
        
        # Load sprite PNGs
        frame_ms = 1000.0 / fps if fps > 0 else 100.0
        frames = []
        
        # Enumerate PNG files numerically (1.png, 2.png, etc.)
        sprite_files = sorted(sprites_dir.glob("*.png"), key=lambda p: int(p.stem))
        for sprite_file in sprite_files:
            try:
                sprite_img = Img().read(sprite_file)
            except FileNotFoundError:
                raise FileNotFoundError(f"Cannot load sprite: {sprite_file}")
            sprite_img.crop_to_content()
            frames.append(SpriteFrame(image=sprite_img.img, duration_ms=frame_ms))

        if not frames:
            raise FileNotFoundError(f"No sprite frames in {sprites_dir}")

        self._cache[key] = frames
        return frames

    def get_config(self, piece_code: str, state: str) -> SpriteConfig:
        """
        Get animated config for a piece state.
        
        Calls load_frames first if needed to populate the cache.
        """
        key = (piece_code, state)
        if key in self._config_cache:
            return self._config_cache[key]
        
        # Load frames to also populate config
        self.load_frames(piece_code, state)
        return self._config_cache[key]
