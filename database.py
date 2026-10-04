import asyncpg
import os

# Schema to put first on the connection's search_path, e.g. "tradesdb" when
# this database is shared with another app via separate schemas (as on
# Neon, where one "neondb" database holds both this app's "tradesdb" schema
# and trade-agent-project's "trade_agent" schema). Empty (the default)
# leaves search_path untouched — fine for a standalone local database where
# the "trades" table just lives in "public". main.py's queries are all
# unqualified ("SELECT * FROM trades"), so they resolve via whatever schema
# is first on this connection's search_path.
DB_SCHEMA = os.getenv("DB_SCHEMA", "")


async def get_db_pool() -> asyncpg.Pool:
    server_settings = {"search_path": DB_SCHEMA} if DB_SCHEMA else None
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return await asyncpg.create_pool(
            dsn=database_url, min_size=2, max_size=10, server_settings=server_settings
        )
    return await asyncpg.create_pool(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        database=os.getenv("DB_NAME", "tradesdb"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "password"),
        min_size=2,
        max_size=10,
        server_settings=server_settings,
    )