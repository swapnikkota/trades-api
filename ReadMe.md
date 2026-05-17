1. You type a prompt — something like "Show me all BUY trades for AAPL" in Copilot's agent mode chat.
2. Copilot decides what to do — it reads the prompt and figures out which MCP tool matches. It doesn't just keyword-match — it reasons about which tool fits the intent. "Analyze my trades" might trigger get_trade_summary. "Flag anything big" triggers detect_large_trades.
3. MCP server receives the tool call — Copilot sends a structured JSON call over HTTP to your Railway MCP server, e.g. get_trades(symbol="AAPL", side="BUY").
4. MCP server calls your FastAPI — it translates the tool call into an HTTP request to your FastAPI: GET /trades?symbol=AAPL&side=BUY.
5. FastAPI queries PostgreSQL — builds a parameterized SQL query, runs it, and returns JSON rows.
6. Result travels back up the chain — JSON → MCP tool result → Copilot → you as a human-readable answer.
The agentic loop is the key insight — Copilot can call multiple tools in one turn. If you ask "Analyze my portfolio and flag any risks", it might call get_trade_summary first, then detect_large_trades, then combine both results into a single coherent answer. It keeps looping until it has everything it needs.