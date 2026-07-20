import pytest
import pytest_asyncio

from auth import service
from db.connection import Database
from db.schema import init_schema
from db.users_repository import UsersRepository


@pytest_asyncio.fixture
async def repo():
    db = Database(':memory:')
    await db.run(init_schema)
    yield UsersRepository(db)
    await db.close()


@pytest.mark.asyncio
async def test_register_creates_a_user(repo):
    result = await service.register(repo, 'alice', 'hunter2')

    assert result.ok
    assert result.user.username == 'alice'
    assert result.user.elo == 1200


@pytest.mark.asyncio
async def test_register_rejects_duplicate_username(repo):
    await service.register(repo, 'alice', 'hunter2')
    result = await service.register(repo, 'alice', 'different_password')

    assert not result.ok
    assert result.error == 'username_taken'


@pytest.mark.asyncio
async def test_login_succeeds_with_correct_password(repo):
    await service.register(repo, 'alice', 'hunter2')
    result = await service.login(repo, 'alice', 'hunter2')

    assert result.ok
    assert result.user.username == 'alice'


@pytest.mark.asyncio
async def test_login_fails_with_wrong_password(repo):
    await service.register(repo, 'alice', 'hunter2')
    result = await service.login(repo, 'alice', 'wrong')

    assert not result.ok
    assert result.error == 'invalid_credentials'


@pytest.mark.asyncio
async def test_login_fails_for_unknown_username_with_same_error_as_wrong_password(repo):
    # Deliberately indistinguishable from a wrong-password failure — see
    # auth/service.py's comment on why (avoids username enumeration).
    result = await service.login(repo, 'nobody', 'whatever')

    assert not result.ok
    assert result.error == 'invalid_credentials'
