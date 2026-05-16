import httpx
from mcp.server.fastmcp import FastMCP

API_BASE = "http://127.0.0.1:8000"

mcp = FastMCP("Trades MCP Server")


@mcp.tool()
async def get_trades(
    symbol: str = None,
    side: str = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """
    Get a list of trades from the trades database.

    Args:
        symbol: Filter by ticker symbol e.g. AAPL, TSLA (optional)
        side: Filter by BUY or SELL (optional)
        limit: Max number of trades to return (default 100)
        offset: Pagination offset (default 0)
    """
    params = {"limit": limit, "offset": offset}
    if symbol:
        params["symbol"] = symbol
    if side:
        params["side"] = side

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
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": price,
            },
        )
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    mcp.run(transport="sse")  # SSE for remote/deployed access
