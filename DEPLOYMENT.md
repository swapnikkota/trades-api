# Trades API + MCP Server — Full Deployment Guide

## Architecture Overview

```
GitHub Copilot
     │  MCP SSE
     ▼
MCP Server (Railway Service 1)
     │  HTTP
     ▼
FastAPI Trades API (Railway Service 2)
     │  asyncpg
     ▼
PostgreSQL (Railway Managed DB)

GitHub Copilot (Agent)
      ↓ MCP SSE
welcoming-analysis.up.railway.app
      ↓ HTTP
trades-api-production.up.railway.app
      ↓ asyncpg
Railway PostgreSQL

```

---

## Prerequisites

Install these before starting:

```bash
brew install railway        # Railway CLI
brew install git            # Git (if not already installed)
```

Create a free account at https://railway.app

---

## Step 1 — Prepare your project

Make sure your project folder looks like this:

```
trades_api/
├── main.py
├── models.py
├── database.py
├── schema.sql
├── mcp_server.py
├── requirements.txt         # FastAPI deps
├── requirements.mcp.txt     # MCP deps
├── Dockerfile.api           # For FastAPI
├── Dockerfile.mcp           # For MCP server
├── railway.toml             # Active config (switch per deploy)
└── .vscode/
    └── mcp.json             # Copilot config
```

---

## Step 2 — Push to GitHub

Railway deploys from Git, so push your code first:

```bash
cd trades_api

git init
git add .
git commit -m "initial commit"

# Create a repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/trades-api.git
git push -u origin main
```

---

## Step 3 — Create a Railway project

```bash
railway login
railway init
# Choose: "Empty Project"
# Give it a name e.g. "trades-platform"
```

---

## Step 4 — Deploy PostgreSQL on Railway

```bash
# Add a Postgres plugin to your Railway project
railway add --plugin postgresql
```

This creates a managed PostgreSQL instance. Get the connection URL:

```bash
railway variables
# Look for DATABASE_URL — copy it, you'll need it shortly
```

Now run your schema against it:

```bash
# Install psql if needed: brew install libpq
psql "$DATABASE_URL" -f schema.sql
```

---

## Step 5 — Deploy the FastAPI service

**5a. Set railway.toml to use the API Dockerfile:**

```toml
[build]
dockerfilePath = "Dockerfile.api"

[deploy]
startCommand = "uvicorn main:app --host 0.0.0.0 --port 8000"
restartPolicyType = "on_failure"
```

**5b. Deploy:**

```bash
railway up --detach
```

**5c. Set environment variables for the API:**

```bash
railway variables --set "DB_HOST=host"
railway variables --set "DB_PORT=port"
railway variables --set "DB_NAME=dbname"
railway variables --set "DB_USER=user"
railway variables --set "DB_PASSWORD=pwd"
```

> Tip: Railway's DATABASE_URL format is:
> `postgresql://USER:PASSWORD@HOST:PORT/DBNAME`
> Parse out each part from that string.

**5d. Generate a public domain for the API:**

```bash
railway domain
# Outputs: https://trades-api-production.up.railway.app
```

Test it:
```bash
curl https://trades-api-production.up.railway.app/trades
curl https://trades-api-production.up.railway.app/health
```

---

## Step 6 — Deploy the MCP Server

**6a. Update railway.toml to use the MCP Dockerfile:**

```toml
[build]
dockerfilePath = "Dockerfile.mcp"

[deploy]
startCommand = "python mcp_server.py"
restartPolicyType = "on_failure"
```

**6b. Create a second Railway service:**

In the Railway dashboard:
- Click **"+ New Service"** inside your existing project
- Choose **"GitHub Repo"** → select your repo
- Railway will pick up `railway.toml` automatically

**6c. Set the API URL environment variable:**

```bash
railway variables --set "API_BASE_URL=https://trades-api-production.up.railway.app"
```

**6d. Generate a public domain for the MCP server:**

```bash
railway domain
# Outputs: https://trades-mcp-production.up.railway.app
```

Test SSE endpoint:
```bash
curl https://trades-mcp-production.up.railway.app/sse
# Should return a streaming SSE response
```

---

## Step 7 — Connect to GitHub Copilot

**7a. Update `.vscode/mcp.json`** in your project:

```json
{
  "servers": {
    "trades": {
      "type": "sse",
      "url": "https://trades-mcp-production.up.railway.app/sse"
    }
  }
}
```

**7b. In VS Code:**

1. Open VS Code in your project folder
2. Open Command Palette (`Cmd+Shift+P`)
3. Run: `MCP: List Servers` — you should see **trades** listed as connected
4. Open Copilot Chat (`Cmd+Shift+I`)
5. Switch to **Agent mode** using the mode selector
6. Type `#trades` or just ask naturally

**Example prompts in Copilot:**
- *"Get all BUY trades for AAPL"*
- *"Show me the last 10 trades"*
- *"Create a trade: buy 5 shares of TSLA at $245"*

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `railway up` fails | Run `railway logs` to see build errors |
| `/sse` returns 404 | Check MCP server started with `transport="sse"` |
| Copilot can't connect | Verify URL in `mcp.json` is correct and reachable |
| DB connection error | Double-check all `DB_*` env vars on Railway |
| `psql` not found | `brew install libpq && brew link libpq --force` |

---

## Full environment variables reference

### FastAPI Service
| Variable | Example |
|---|---|
| `DB_HOST` | `roundhouse.proxy.rlwy.net` |
| `DB_PORT` | `5432` |
| `DB_NAME` | `railway` |
| `DB_USER` | `postgres` |
| `DB_PASSWORD` | `abc123xyz` |

### MCP Server Service
| Variable | Example |
|---|---|
| `API_BASE_URL` | `https://trades-api-production.up.railway.app` |
