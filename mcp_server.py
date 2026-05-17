import os
import asyncio
import httpx
import uvicorn
from mcp.server.fastmcp import FastMCP

API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

mcp = FastMCP("Trades Agent")


# ── Basic CRUD tools ───────────────────────────────────────────────────────────

@mcp.tool()
async def get_trades(
    symbol: str = None,
    side: str = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """
    Get a list of trades from the database.

    Args:
        symbol: Filter by ticker symbol e.g. AAPL, TSLA (optional)
        side: Filter by BUY or SELL (optional)
        limit: Max number of trades to return (default 100)
        offset: Pagination offset (default 0)
    """
    params = {"limit": limit, "offset": offset}
    if symbol:
        params["symbol"] = symbol.upper()
    if side:
        params["side"] = side.upper()

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE}/trades", params=params)
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def get_trade_by_id(trade_id: int) -> dict:
    """
    Get a single trade by its ID.

    Args:
        trade_id: The unique ID of the trade
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE}/trades/{trade_id}")
        response.raise_for_status()
        return response.json()


@mcp.tool()
async def create_trade(
    symbol: str,
    side: str,
    quantity: float,
    price: float,
) -> dict:
    """
    Create a new trade entry in the database.

    Args:
        symbol: Ticker symbol e.g. AAPL
        side: BUY or SELL
        quantity: Number of shares/units
        price: Price per unit
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE}/trades",
            json={
                "symbol": symbol.upper(),
                "side": side.upper(),
                "quantity": quantity,
                "price": price,
            },
        )
        response.raise_for_status()
        return response.json()


# ── Analytics tools ────────────────────────────────────────────────────────────

@mcp.tool()
async def get_trade_summary() -> dict:
    """
    Get a high-level summary of all trades including total count,
    BUY vs SELL breakdown, most traded symbols, and total value per symbol.
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE}/trades", params={"limit": 1000})
        response.raise_for_status()
        trades = response.json()

    if not trades:
        return {"message": "No trades found"}

    buys = [t for t in trades if t["side"] == "BUY"]
    sells = [t for t in trades if t["side"] == "SELL"]

    symbol_value: dict = {}
    symbol_count: dict = {}
    for t in trades:
        sym = t["symbol"]
        val = t["quantity"] * t["price"]
        symbol_value[sym] = symbol_value.get(sym, 0) + val
        symbol_count[sym] = symbol_count.get(sym, 0) + 1

    top_symbols = sorted(symbol_count, key=symbol_count.get, reverse=True)[:5]

    return {
        "total_trades": len(trades),
        "buy_count": len(buys),
        "sell_count": len(sells),
        "buy_sell_ratio": f"{len(buys)}:{len(sells)}",
        "top_symbols": top_symbols,
        "value_by_symbol": {
            sym: round(symbol_value[sym], 2)
            for sym in sorted(symbol_value, key=symbol_value.get, reverse=True)
        },
    }


@mcp.tool()
async def get_largest_trades(top_n: int = 5) -> list[dict]:
    """
    Get the largest trades by total value (quantity x price).

    Args:
        top_n: Number of top trades to return (default 5)
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE}/trades", params={"limit": 1000})
        response.raise_for_status()
        trades = response.json()

    for t in trades:
        t["total_value"] = round(t["quantity"] * t["price"], 2)

    return sorted(trades, key=lambda x: x["total_value"], reverse=True)[:top_n]


@mcp.tool()
async def get_trades_by_symbol_analysis(symbol: str) -> dict:
    """
    Get a detailed analysis for a specific symbol including average buy/sell
    price, total quantity, net position, and long/short status.

    Args:
        symbol: Ticker symbol to analyze e.g. AAPL
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/trades",
            params={"symbol": symbol.upper(), "limit": 1000}
        )
        response.raise_for_status()
        trades = response.json()

    if not trades:
        return {"symbol": symbol.upper(), "message": "No trades found"}

    buys = [t for t in trades if t["side"] == "BUY"]
    sells = [t for t in trades if t["side"] == "SELL"]
    avg_buy = sum(t["price"] for t in buys) / len(buys) if buys else 0
    avg_sell = sum(t["price"] for t in sells) / len(sells) if sells else 0
    total_bought = sum(t["quantity"] for t in buys)
    total_sold = sum(t["quantity"] for t in sells)
    net = total_bought - total_sold

    return {
        "symbol": symbol.upper(),
        "total_trades": len(trades),
        "buy_count": len(buys),
        "sell_count": len(sells),
        "avg_buy_price": round(avg_buy, 2),
        "avg_sell_price": round(avg_sell, 2),
        "total_quantity_bought": round(total_bought, 4),
        "total_quantity_sold": round(total_sold, 4),
        "net_position": round(net, 4),
        "net_position_status": "LONG" if net > 0 else "SHORT" if net < 0 else "FLAT",
    }


@mcp.tool()
async def detect_large_trades(threshold_value: float = 10000.0) -> list[dict]:
    """
    Detect trades where total value (quantity x price) exceeds a threshold.

    Args:
        threshold_value: Minimum trade value to flag (default $10,000)
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE}/trades", params={"limit": 1000})
        response.raise_for_status()
        trades = response.json()

    flagged = []
    for t in trades:
        value = t["quantity"] * t["price"]
        if value >= threshold_value:
            t["total_value"] = round(value, 2)
            flagged.append(t)

    return sorted(flagged, key=lambda x: x["total_value"], reverse=True)


@mcp.tool()
async def get_recent_trades(n: int = 10) -> list[dict]:
    """
    Get the N most recent trades ordered by timestamp.

    Args:
        n: Number of recent trades to return (default 10)
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{API_BASE}/trades",
            params={"limit": n, "offset": 0}
        )
        response.raise_for_status()
        return response.json()


# ── ASGI wrapper to fix host header for Railway proxy ─────────────────────────

class FixHostHeaderMiddleware:
    """
    Rewrites the host header in the ASGI scope directly,
    bypassing Railway's proxy host validation in the MCP server.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            # Rewrite headers in scope to replace host with localhost
            headers = [
                (b"host", b"localhost") if k.lower() == b"host" else (k, v)
                for k, v in scope.get("headers", [])
            ]
            scope["headers"] = headers
            scope["server"] = ("localhost", scope.get("server", ("localhost", 8080))[1])
        await self.app(scope, receive, send)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    mcp_app = mcp.streamable_http_app()
    app = FixHostHeaderMiddleware(mcp_app)

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
    server = uvicorn.Server(config)
    asyncio.run(server.serve())