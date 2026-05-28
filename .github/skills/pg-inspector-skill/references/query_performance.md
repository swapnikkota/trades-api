# Query Performance Patterns

## N+1 Queries

The most common performance killer in applications. Occurs when code runs
one query to fetch a list, then one query per row to fetch related data.

**Problem:**
```python
# Fetches 1 query for orders, then 1 per order for user — N+1
orders = db.query("SELECT * FROM orders LIMIT 100")
for order in orders:
    user = db.query("SELECT * FROM users WHERE id = %s", order.user_id)
```

**Fix — use a JOIN:**
```sql
SELECT o.*, u.name, u.email
FROM orders o
JOIN users u ON u.id = o.user_id
LIMIT 100;
```

**Fix — use IN for batch fetch:**
```sql
-- Fetch all user IDs first, then one query for all users
SELECT * FROM users WHERE id = ANY(ARRAY[1,2,3,...]);
```

---

## Pagination

### OFFSET pagination (avoid for large offsets)

```sql
-- ❌ Slow — scans and discards 100,000 rows
SELECT * FROM orders ORDER BY created_at DESC LIMIT 20 OFFSET 100000;
```

Performance degrades linearly with offset size.

### Keyset / cursor pagination (use this instead)

```sql
-- ✅ Fast — uses index seek, O(log n) regardless of page depth
SELECT * FROM orders
WHERE created_at < :last_seen_created_at   -- from previous page
ORDER BY created_at DESC
LIMIT 20;

-- With a composite cursor for stable ordering
SELECT * FROM orders
WHERE (created_at, id) < (:last_created_at, :last_id)
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

Requires an index on the cursor columns:
```sql
CREATE INDEX ON orders (created_at DESC, id DESC);
```

---

## SELECT * (avoid in production)

```sql
-- ❌ Fetches all columns including large JSONB/TEXT blobs
SELECT * FROM products WHERE category = 'electronics';

-- ✅ Fetch only what you need
SELECT id, name, price, stock FROM products WHERE category = 'electronics';
```

Large columns (`TEXT`, `JSONB`, `BYTEA`) are expensive to transfer even if
the application discards them. Use covering indexes when possible:

```sql
-- Index includes all columns needed — avoids heap fetch entirely
CREATE INDEX ON products (category) INCLUDE (id, name, price, stock);
```

---

## Aggregations on large tables

```sql
-- ❌ Full table scan every time
SELECT count(*) FROM events WHERE user_id = 42;

-- ✅ Partial index for common filters
CREATE INDEX ON events (user_id) WHERE user_id IS NOT NULL;

-- ✅ For approximate counts (much faster)
SELECT reltuples::bigint AS approx_count
FROM pg_class WHERE relname = 'events';
```

---

## LIKE and full-text search

```sql
-- ❌ Leading wildcard — cannot use B-tree index
SELECT * FROM products WHERE name LIKE '%phone%';

-- ✅ Trigram index (pg_trgm) — supports LIKE '%...%'
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX ON products USING gin (name gin_trgm_ops);
SELECT * FROM products WHERE name LIKE '%phone%';  -- now uses index

-- ✅ Full-text search for natural language
ALTER TABLE articles ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (to_tsvector('english', title || ' ' || body)) STORED;
CREATE INDEX ON articles USING gin (search_vector);
SELECT * FROM articles WHERE search_vector @@ plainto_tsquery('english', 'postgres performance');
```

---

## OR conditions and indexes

```sql
-- ❌ OR can prevent index use
SELECT * FROM orders WHERE status = 'pending' OR status = 'processing';

-- ✅ Use IN instead
SELECT * FROM orders WHERE status IN ('pending', 'processing');

-- ✅ Or UNION ALL for very different selectivities
SELECT * FROM orders WHERE status = 'pending'
UNION ALL
SELECT * FROM orders WHERE status = 'processing';
```

---

## Expensive functions in WHERE clauses

```sql
-- ❌ Function call on every row — can't use index
SELECT * FROM users WHERE lower(email) = 'user@example.com';

-- ✅ Functional index
CREATE INDEX ON users (lower(email));
SELECT * FROM users WHERE lower(email) = 'user@example.com';

-- ❌ Date function prevents index use
SELECT * FROM orders WHERE date_trunc('day', created_at) = '2024-01-15';

-- ✅ Use range instead
SELECT * FROM orders
WHERE created_at >= '2024-01-15' AND created_at < '2024-01-16';
```

---

## work_mem and sort/hash performance

When a sort or hash join exceeds `work_mem`, Postgres spills to disk (temporary
files), which is 10–100x slower.

```sql
-- Check for temp file usage
SELECT query, temp_blks_written
FROM pg_stat_statements
WHERE temp_blks_written > 0
ORDER BY temp_blks_written DESC;

-- Increase work_mem for a specific session/query
SET work_mem = '256MB';
SELECT * FROM large_table ORDER BY complex_expression;
RESET work_mem;

-- Global default (affects all connections × all sorts simultaneously — be careful)
-- ALTER SYSTEM SET work_mem = '64MB';
```

Rule of thumb: `work_mem` × `max_connections` × 2 should be < 50% of RAM.

---

## CTEs (WITH clauses) — optimization fence behaviour

Before PostgreSQL 12, CTEs were always materialised (optimisation fence).
In PG 12+ they are inlined by default unless they are recursive or have
side effects.

```sql
-- PG 12+: inlined automatically, planner can optimise through it
WITH recent_orders AS (
    SELECT * FROM orders WHERE created_at > now() - interval '7 days'
)
SELECT * FROM recent_orders WHERE user_id = 42;

-- Force materialisation (useful when CTE result is reused many times)
WITH recent_orders AS MATERIALIZED (
    SELECT * FROM orders WHERE created_at > now() - interval '7 days'
)
SELECT ...;

-- Prevent materialisation explicitly
WITH recent_orders AS NOT MATERIALIZED (...)
SELECT ...;
```

---

## Reading EXPLAIN output — key signals

| Node type | What to look for |
|-----------|-----------------|
| `Seq Scan` | OK for small tables; bad on large ones with filters |
| `Index Scan` | Good — uses index |
| `Index Only Scan` | Best — never touches the heap |
| `Bitmap Heap Scan` | Good for moderate selectivity |
| `Hash Join` | Check estimated vs. actual rows — large diff = stale stats |
| `Nested Loop` | Fine for small inner sets; bad when inner is large |
| `Sort` | Check for "external merge" — means disk spill |

```sql
-- Full analysis with buffers (shows cache hits vs disk reads)
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) SELECT ...;
```

Look for: `rows=X` (estimate) vs actual rows — large differences mean
statistics are stale. Fix with `ANALYZE <table>`.
