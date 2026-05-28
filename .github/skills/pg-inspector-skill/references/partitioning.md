# Table Partitioning & Partition Pruning

## Why it matters
For large tables (100M+ rows or tables measured in GB), partitioning lets
Postgres skip entire chunks of data at query time (partition pruning), run
maintenance on smaller pieces, and drop old data instantly via `DROP TABLE`
on a partition rather than slow `DELETE`.

---

## When to partition

Partition when:
- Table exceeds ~100M rows or ~50GB
- Queries almost always filter on a specific column (date, region, tenant_id)
- You need to purge old data regularly (time-series, logs, events)
- Autovacuum struggles to keep up with a single large table

Don't partition when:
- Table is small — partitioning adds overhead
- Queries don't filter on the partition key (pruning won't fire)
- You need cross-partition foreign keys (not supported)

---

## Partition types

### Range partitioning (most common — dates, IDs)

```sql
CREATE TABLE orders (
    id          bigserial,
    created_at  timestamptz NOT NULL,
    user_id     bigint,
    total       numeric
) PARTITION BY RANGE (created_at);

-- Create partitions per month
CREATE TABLE orders_2024_01 PARTITION OF orders
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE orders_2024_02 PARTITION OF orders
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');

-- Default partition catches anything that doesn't match
CREATE TABLE orders_default PARTITION OF orders DEFAULT;
```

### List partitioning (discrete values — region, status)

```sql
CREATE TABLE events (
    id      bigserial,
    region  text NOT NULL,
    payload jsonb
) PARTITION BY LIST (region);

CREATE TABLE events_us   PARTITION OF events FOR VALUES IN ('us-east', 'us-west');
CREATE TABLE events_eu   PARTITION OF events FOR VALUES IN ('eu-west', 'eu-central');
CREATE TABLE events_apac PARTITION OF events FOR VALUES IN ('ap-southeast', 'ap-northeast');
```

### Hash partitioning (even distribution — tenant_id, user_id)

```sql
CREATE TABLE user_events (
    id        bigserial,
    user_id   bigint NOT NULL,
    event     text
) PARTITION BY HASH (user_id);

CREATE TABLE user_events_0 PARTITION OF user_events FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE user_events_1 PARTITION OF user_events FOR VALUES WITH (MODULUS 4, REMAINDER 1);
CREATE TABLE user_events_2 PARTITION OF user_events FOR VALUES WITH (MODULUS 4, REMAINDER 2);
CREATE TABLE user_events_3 PARTITION OF user_events FOR VALUES WITH (MODULUS 4, REMAINDER 3);
```

---

## Partition pruning — how it works

Postgres eliminates partitions at plan time when the WHERE clause matches
the partition key:

```sql
-- ✅ Pruning fires — only scans orders_2024_01
SELECT * FROM orders WHERE created_at >= '2024-01-01' AND created_at < '2024-02-01';

-- ❌ Pruning does NOT fire — full scan across all partitions
SELECT * FROM orders WHERE user_id = 42;
-- (user_id is not the partition key)

-- ✅ Pruning fires at runtime (not just plan time) with parameters
PREPARE q(timestamptz) AS SELECT * FROM orders WHERE created_at >= $1;
```

Verify pruning is working:
```sql
EXPLAIN (ANALYZE, PARTITIONS)
SELECT * FROM orders WHERE created_at >= '2024-01-01' AND created_at < '2024-02-01';
-- Look for "Partitions removed: N" in the output
```

---

## Indexes on partitioned tables

Indexes must be created on the parent — Postgres propagates them:

```sql
-- Creates the index on every partition automatically
CREATE INDEX ON orders (user_id);
CREATE INDEX ON orders (created_at);

-- Unique/PK constraints must include the partition key
ALTER TABLE orders ADD PRIMARY KEY (id, created_at);
```

---

## Dropping old partitions (fast data expiry)

```sql
-- Instant — no DELETE scan, no VACUUM needed
DROP TABLE orders_2022_01;

-- Or detach first (keeps data accessible temporarily)
ALTER TABLE orders DETACH PARTITION orders_2022_01;
-- ... do something with it ...
DROP TABLE orders_2022_01;
```

vs. the slow alternative:
```sql
-- ❌ Slow — full table scan, generates dead tuples, needs VACUUM
DELETE FROM orders WHERE created_at < '2022-02-01';
```

---

## Automating partition creation

Use `pg_partman` extension (widely available):

```sql
-- Install
CREATE EXTENSION pg_partman;

-- Set up automatic monthly partitions
SELECT partman.create_parent(
    p_parent_table := 'public.orders',
    p_control      := 'created_at',
    p_interval     := '1 month',
    p_premake      := 3  -- create 3 months ahead
);

-- Run maintenance (add to pg_cron or cron job)
SELECT partman.run_maintenance();
```

---

## Checking partition sizes

```sql
SELECT
    child.relname               AS partition,
    pg_size_pretty(pg_relation_size(child.oid)) AS size,
    pg_stat_user_tables.n_live_tup AS live_rows
FROM pg_inherits
JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
JOIN pg_class child  ON pg_inherits.inhrelid  = child.oid
LEFT JOIN pg_stat_user_tables ON pg_stat_user_tables.relname = child.relname
WHERE parent.relname = 'orders'
ORDER BY child.relname;
```

---

## Common pitfalls

| Pitfall | Problem | Fix |
|---------|---------|-----|
| Partition key not in WHERE clause | Pruning never fires, full scan | Always filter on partition key |
| Too many partitions (1000+) | Planner overhead, slow DDL | Stay under 500 partitions |
| Forgetting default partition | Inserts fail for out-of-range values | Always create a DEFAULT partition |
| FK referencing partitioned table | Not supported in older PG | Upgrade to PG 12+ or restructure |
| Unique constraint without partition key | Not allowed | Include partition key in all unique constraints |
