import asyncpg
import os

async def get_db_pool() -> asyncpg.Pool:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return await asyncpg.create_pool(dsn=database_url, min_size=2, max_size=10)
    return await asyncpg.create_pool(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        database=os.getenv("DB_NAME", "tradesdb"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "password"),
        min_size=2,
        max_size=10,
    )