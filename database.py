import asyncpg
import os
import re

# Schema to put first on the connection's search_path, e.g. "tradesdb" when
# this database is shared with another app via separate schemas (as on
# Neon, where one "neondb" database holds both this app's "tradesdb" schema
# and trade-agent-project's "trade_agent" schema). Empty (the default)
# leaves search_path untouched — fine for a standalone local database where
# the "trades" table just lives in "public". main.py's queries are all
# unqualified ("SELECT * FROM trades"), so they resolve via whatever schema
# is first on this connection's search_path.
DB_SCHEMA = os.getenv("DB_SCHEMA", "")

# Neon's connection proxy does not forward the "search_path" startup
# parameter the way a normal Postgres server does (confirmed via a live
# /debug/db check: server_settings={"search_path": ...} passed to
# asyncpg.connect()/create_pool() is silently dropped — connections come
# back with the default "$user", public search_path regardless). So instead
# of relying on server_settings, we run "SET search_path" explicitly as a
# real query on every new pooled connection via asyncpg's `setup` hook.
# Restricted to a plain identifier (letters/digits/underscore) since it's
# interpolated directly into SQL.
if DB_SCHEMA and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", DB_SCHEMA):
    raise ValueError(f"DB_SCHEMA={DB_SCHEMA!r} is not a valid unquoted Postgres identifier")


async def _set_search_path(conn: asyncpg.Connection) -> None:
    await conn.execute(f"SET search_path TO {DB_SCHEMA}")


async def get_db_pool() -> asyncpg.Pool:
    pool_kwargs = {"min_size": 2, "max_size": 10}
    if DB_SCHEMA:
        pool_kwargs["setup"] = _set_search_path

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return await asyncpg.create_pool(dsn=database_url, **pool_kwargs)
    return await asyncpg.create_pool(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        database=os.getenv("DB_NAME", "tradesdb"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "password"),
        **pool_kwargs,
    )
