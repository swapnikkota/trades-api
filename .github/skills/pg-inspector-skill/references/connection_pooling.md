# Connection Pool Sizing

## Why it matters
Each PostgreSQL connection consumes ~5–10MB of RAM and a backend process.
Opening a new connection takes 20–100ms. Most applications need pooling —
without it, connection overhead dominates latency and you hit `max_connections`
under load.

---

## The core formula

```
optimal_pool_size = (num_cores * 2) + effective_spindle_count
```

For most cloud instances (SSD, no spindles):
```
optimal_pool_size = num_cores * 2
```

**Example:** 4-core server → pool size of 8–10.  
This often surprises people. More connections beyond this point adds
queue contention, not throughput.

---

## Check current connection usage

```sql
-- Current connections by state and user
SELECT
    usename,
    application_name,
    state,
    count(*) AS connections,
    max(now() - state_change) AS longest_in_state
FROM pg_stat_activity
WHERE pid <> pg_backend_pid()
GROUP BY usename, application_name, state
ORDER BY connections DESC;

-- Connections vs max_connections
SELECT
    count(*)                         AS current_connections,
    max_conn.setting::int            AS max_connections,
    round(count(*) * 100.0 /
          max_conn.setting::int, 1)  AS pct_used
FROM pg_stat_activity,
     (SELECT setting FROM pg_settings WHERE name = 'max_connections') max_conn
GROUP BY max_conn.setting;

-- Idle connections (wasted resources)
SELECT count(*) AS idle_connections
FROM pg_stat_activity
WHERE state = 'idle';
```

---

## max_connections guidance

| Workload | Recommended max_connections |
|----------|----------------------------|
| Small app / dev | 100 (default) |
| Web app with pooler | 200–400 |
| High-concurrency + PgBouncer | 100–200 (pooler handles the rest) |
| Large instance, no pooler | 300–500 (watch RAM) |

RAM cost: each connection reserves ~5–10MB.  
On a 4GB server, 200 connections = up to 2GB just for connection overhead.

---

## PgBouncer pool modes

| Mode | How it works | Best for |
|------|-------------|---------|
| `session` | Connection held for entire client session | Legacy apps, long sessions |
| `transaction` | Connection returned to pool after each transaction | Most web apps ✅ |
| `statement` | Connection returned after each statement | Rare, breaks multi-statement transactions |

**Transaction mode** is the right default for most applications.

---

## PgBouncer sizing formula

```
# pgbouncer.ini
[databases]
mydb = host=127.0.0.1 port=5432 dbname=mydb

[pgbouncer]
pool_mode        = transaction
max_client_conn  = 1000        # clients connecting to PgBouncer
default_pool_size = 20         # connections PgBouncer keeps to Postgres
min_pool_size    = 5
reserve_pool_size = 5
server_idle_timeout = 600
```

Rule of thumb:
- `default_pool_size` = CPU cores × 2
- `max_client_conn` = however many app threads/goroutines you have (can be 1000s)

---

## Detecting connection-related problems

```sql
-- Connections waiting for a lock
SELECT pid, wait_event_type, wait_event, query, now() - query_start AS wait_time
FROM pg_stat_activity
WHERE wait_event IS NOT NULL
  AND state = 'active'
ORDER BY wait_time DESC;

-- Idle-in-transaction connections (blocking vacuums and holding locks)
SELECT pid, usename, now() - xact_start AS idle_txn_duration, query
FROM pg_stat_activity
WHERE state = 'idle in transaction'
ORDER BY idle_txn_duration DESC;

-- Connection count trend (run periodically)
SELECT now(), count(*) FROM pg_stat_activity;
```

---

## idle-in-transaction timeout (important)

Connections stuck `idle in transaction` hold locks and block VACUUM.
Set a timeout to kill them automatically:

```sql
-- Kill connections idle in transaction for more than 30 seconds
ALTER SYSTEM SET idle_in_transaction_session_timeout = '30s';
SELECT pg_reload_conf();

-- Or per role
ALTER ROLE myapp SET idle_in_transaction_session_timeout = '30s';
```

---

## statement_timeout

Prevent runaway queries from holding connections:

```sql
-- Kill any query running longer than 30 seconds (app role)
ALTER ROLE myapp SET statement_timeout = '30s';

-- Per-session override for long admin queries
SET statement_timeout = '5min';
```

---

## Common mistakes

| Mistake | Impact | Fix |
|---------|--------|-----|
| No connection pooler | High latency, OOM under load | Add PgBouncer |
| Pool size = thread count (e.g. 100) | Queue thrash, high CPU | Reduce to cores × 2 |
| No `idle_in_transaction_session_timeout` | Locks held indefinitely | Set to 30–60s |
| No `statement_timeout` | Long queries starve the pool | Set per role |
| Opening new connections per request | 20–100ms overhead per request | Use persistent pool |
