import sqlite3

from db.schema import init_schema


def test_init_schema_creates_both_tables():
    conn = sqlite3.connect(':memory:')
    init_schema(conn)

    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {'users', 'matches'} <= tables


def test_init_schema_is_idempotent():
    conn = sqlite3.connect(':memory:')
    init_schema(conn)
    init_schema(conn)  # must not raise
