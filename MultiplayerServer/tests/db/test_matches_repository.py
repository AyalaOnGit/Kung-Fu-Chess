import pytest
import pytest_asyncio

from db.connection import Database
from db.matches_repository import MatchesRepository
from db.schema import init_schema
from db.users_repository import UsersRepository


@pytest_asyncio.fixture
async def repos():
    db = Database(':memory:')
    await db.run(init_schema)
    yield UsersRepository(db), MatchesRepository(db)
    await db.close()


@pytest.mark.asyncio
async def test_record_result_returns_a_new_row_id(repos):
    users_repo, matches_repo = repos
    white = await users_repo.create('white_player', 'h', 's')
    black = await users_repo.create('black_player', 'h', 's')

    match_id = await matches_repo.record_result(
        white_user_id=white.id, black_user_id=black.id, winner_user_id=white.id,
        result_reason='king_captured',
        white_elo_before=1200, black_elo_before=1200,
        white_elo_after=1216, black_elo_after=1184,
    )

    assert isinstance(match_id, int)


@pytest.mark.asyncio
async def test_recording_two_matches_yields_two_distinct_ids(repos):
    users_repo, matches_repo = repos
    white = await users_repo.create('white_player', 'h', 's')
    black = await users_repo.create('black_player', 'h', 's')

    kwargs = dict(
        white_user_id=white.id, black_user_id=black.id, winner_user_id=white.id,
        result_reason='king_captured',
        white_elo_before=1200, black_elo_before=1200,
        white_elo_after=1216, black_elo_after=1184,
    )
    first_id = await matches_repo.record_result(**kwargs)
    second_id = await matches_repo.record_result(**kwargs)

    assert first_id != second_id
