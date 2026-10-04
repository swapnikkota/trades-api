from fastapi import FastAPI, HTTPException, Query
from typing import Optional
import asyncpg
import os
from contextlib import asynccontextmanager
from models import Trade, TradeCreate
from database import get_db_pool

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await get_db_pool()
    yield
    await app.state.db.close()

app = FastAPI(title="Trades API", version="1.0.0", lifespan=lifespan)


@app.get("/trades", response_model=list[Trade])
async def get_trades(
    symbol: Optional[str] = Query(None, description="Filter by symbol, e.g. AAPL"),
    side: Optional[str] = Query(None, description="Filter by side: BUY or SELL"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    query = "SELECT * FROM trades WHERE 1=1"
    params = []

    if symbol:
        params.append(symbol.upper())
        query += f" AND symbol = ${len(params)}"
    if side:
        params.append(side.upper())
        query += f" AND side = ${len(params)}"

    params.append(limit)
    query += f" ORDER BY timestamp DESC LIMIT ${len(params)}"
    params.append(offset)
    query += f" OFFSET ${len(params)}"

    async with app.state.db.acquire() as conn:
        rows = await conn.fetch(query, *params)

    return [dict(row) for row in rows]


@app.get("/trades/{trade_id}", response_model=Trade)
async def get_trade(trade_id: int):
    async with app.state.db.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM trades WHERE id = $1", trade_id)
    if not row:
        raise HTTPException(status_code=404, detail="Trade not found")
    return dict(row)


@app.post("/trades", response_model=Trade, status_code=201)
async def create_trade(trade: TradeCreate):
    async with app.state.db.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO trades (symbol, side, quantity, price, timestamp)
            VALUES ($1, $2, $3, $4, NOW())
            RETURNING *
            """,
            trade.symbol.upper(),
            trade.side.upper(),
            trade.quantity,
            trade.price,
        )
    return dict(row)


@app.get("/health")
async def health():
    return {"status": "ok"}
