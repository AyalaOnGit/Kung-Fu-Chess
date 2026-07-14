"""
Player labels: displays player names.
"""
from kungfu_chess.model.piece import Color


class PlayerLabels:
    """
    Displays static player labels (White/Black).
    """
    
    def __init__(self):
        self._player_names = {
            Color.WHITE: "White",
            Color.BLACK: "Black",
        }
    
    def get_label(self, color: Color) -> str:
        """Get label for a player."""
        return self._player_names.get(color, "Unknown")
