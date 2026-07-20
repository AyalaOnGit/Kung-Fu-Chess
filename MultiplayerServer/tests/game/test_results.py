import pytest
import pytest_asyncio

from db.connection import Database
from db.matches_repository import MatchesRepository
from db.schema import init_schema
from db.users_repository import UsersRepository
from game.results import record_match_result


@pytest_asyncio.fixture
async def repos():
    db = Database(':memory:')
    await db.run(init_schema)
    yield UsersRepository(db), MatchesRepository(db)
    await db.close()


@pytest.mark.asyncio
async def test_records_result_and_updates_elo_for_both_players(repos):
    users_repo, matches_repo = repos
    white = await users_repo.create('white_player', 'h', 's')
    black = await users_repo.create('black_player', 'h', 's')

    await record_match_result(
        users_repo, matches_repo,
        white_user_id=white.id, black_user_id=black.id,
        white_won=True, result_reason='king_captured',
    )

    assert (await users_repo.get_by_id(white.id)).elo == 1216
    assert (await users_repo.get_by_id(black.id)).elo == 1184


@pytest.mark.asyncio
async def test_black_win_updates_elo_the_other_direction(repos):
    users_repo, matches_repo = repos
    white = await users_repo.create('white_player', 'h', 's')
    black = await users_repo.create('black_player', 'h', 's')

    await record_match_result(
        users_repo, matches_repo,
        white_user_id=white.id, black_user_id=black.id,
        white_won=False, result_reason='king_captured',
    )

    assert (await users_repo.get_by_id(white.id)).elo == 1184
    assert (await users_repo.get_by_id(black.id)).elo == 1216


@pytest.mark.asyncio
async def test_anonymous_player_skips_persistence_entirely(repos):
    users_repo, matches_repo = repos
    white = await users_repo.create('white_player', 'h', 's')

    # black_user_id=None -> never logged in; nothing should be recorded or changed.
    await record_match_result(
        users_repo, matches_repo,
        white_user_id=white.id, black_user_id=None,
        white_won=True, result_reason='king_captured',
    )

    assert (await users_repo.get_by_id(white.id)).elo == 1200
