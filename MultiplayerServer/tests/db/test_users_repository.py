import sqlite3

import pytest
import pytest_asyncio

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
async def test_create_and_get_by_username(repo):
    created = await repo.create('alice', 'hash', 'salt')

    assert created.username == 'alice'
    assert created.elo == 1200
    assert created.id is not None
    assert await repo.get_by_username('alice') == created


@pytest.mark.asyncio
async def test_get_by_username_returns_none_when_missing(repo):
    assert await repo.get_by_username('nobody') is None


@pytest.mark.asyncio
async def test_get_by_id_round_trips(repo):
    created = await repo.create('bob', 'h', 's')
    assert await repo.get_by_id(created.id) == created


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_missing(repo):
    assert await repo.get_by_id(9999) is None


@pytest.mark.asyncio
async def test_update_elo_persists(repo):
    created = await repo.create('carol', 'h', 's')
    await repo.update_elo(created.id, 1350)

    assert (await repo.get_by_id(created.id)).elo == 1350


@pytest.mark.asyncio
async def test_duplicate_username_is_rejected(repo):
    await repo.create('dave', 'h', 's')
    with pytest.raises(sqlite3.IntegrityError):
        await repo.create('dave', 'h2', 's2')
