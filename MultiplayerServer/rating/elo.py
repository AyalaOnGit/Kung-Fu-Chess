"""expected_score, update_ratings — pure functions, no I/O, no clock needed."""
from __future__ import annotations

K_FACTOR = 32


def expected_score(rating_a: int, rating_b: int) -> float:
    """Probability that a player rated rating_a beats one rated rating_b."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))


def update_ratings(white_elo: int, black_elo: int, *, white_score: float) -> tuple[int, int]:
    """
    white_score: 1.0 white won, 0.0 black won, 0.5 draw.
    Returns (new_white_elo, new_black_elo), each rounded to the nearest int.
    """
    expected_white = expected_score(white_elo, black_elo)
    expected_black = 1.0 - expected_white
    black_score = 1.0 - white_score

    new_white = white_elo + K_FACTOR * (white_score - expected_white)
    new_black = black_elo + K_FACTOR * (black_score - expected_black)
    return round(new_white), round(new_black)
