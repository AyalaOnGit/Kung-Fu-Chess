"""
Records a finished match's result and updates both players' ELO.

This is the callback a Room's on_game_over hook invokes when a game ends
(by capture or resignation) — the "existing hook, extended" that §5 Phase
2 describes, rather than a new mechanism bolted on separately.
"""
from __future__ import annotations
from typing import Optional

from db.matches_repository import MatchesRepository
from db.users_repository import UsersRepository
from rating.elo import update_ratings


async def record_match_result(
    users_repo: UsersRepository,
    matches_repo: MatchesRepository,
    *,
    white_user_id: Optional[int],
    black_user_id: Optional[int],
    white_won: bool,
    result_reason: str,
) -> None:
    """
    No-op if either player never logged in — only authenticated players get
    a persisted, rated result. An anonymous match simply isn't recorded.
    """
    if white_user_id is None or black_user_id is None:
        return

    white = await users_repo.get_by_id(white_user_id)
    black = await users_repo.get_by_id(black_user_id)
    if white is None or black is None:
        return

    white_score = 1.0 if white_won else 0.0
    new_white_elo, new_black_elo = update_ratings(white.elo, black.elo, white_score=white_score)
    winner_user_id = white_user_id if white_won else black_user_id

    await matches_repo.record_result(
        white_user_id=white_user_id, black_user_id=black_user_id, winner_user_id=winner_user_id,
        result_reason=result_reason,
        white_elo_before=white.elo, black_elo_before=black.elo,
        white_elo_after=new_white_elo, black_elo_after=new_black_elo,
    )
    await users_repo.update_elo(white_user_id, new_white_elo)
    await users_repo.update_elo(black_user_id, new_black_elo)
