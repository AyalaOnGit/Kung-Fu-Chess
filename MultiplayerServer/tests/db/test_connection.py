import asyncio

import pytest

from db.connection import Database


@pytest.mark.asyncio
async def test_run_executes_fn_against_a_live_connection():
    db = Database(':memory:')
    try:
        def create_table(conn):
            conn.execute('CREATE TABLE t (n INTEGER)')
            conn.commit()

        def insert(conn):
            conn.execute('INSERT INTO t (n) VALUES (1)')
            conn.commit()

        def count(conn):
            return conn.execute('SELECT COUNT(*) AS c FROM t').fetchone()['c']

        await db.run(create_table)
        await db.run(insert)
        assert await db.run(count) == 1
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_same_connection_is_reused_across_calls():
    db = Database(':memory:')
    try:
        def get_id(conn):
            return id(conn)

        first = await db.run(get_id)
        second = await db.run(get_id)
        assert first == second
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_concurrent_calls_are_serialized_and_do_not_corrupt_state():
    """
    50 concurrent read-modify-write increments only add up to 50 if every
    call truly runs one at a time on the dedicated db thread — a race
    would lose updates and the final count would come out lower.
    """
    db = Database(':memory:')
    try:
        def create_table(conn):
            conn.execute('CREATE TABLE counter (n INTEGER)')
            conn.execute('INSERT INTO counter (n) VALUES (0)')
            conn.commit()

        def increment(conn):
            current = conn.execute('SELECT n FROM counter').fetchone()['n']
            conn.execute('UPDATE counter SET n = ?', (current + 1,))
            conn.commit()

        def read(conn):
            return conn.execute('SELECT n FROM counter').fetchone()['n']

        await db.run(create_table)
        await asyncio.gather(*(db.run(increment) for _ in range(50)))

        assert await db.run(read) == 50
    finally:
        await db.close()
