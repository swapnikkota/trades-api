# VACUUM & Autovacuum Tuning

## Why it matters
PostgreSQL uses MVCC — every UPDATE creates a new row version and marks the old
one dead. Dead tuples accumulate until VACUUM reclaims them. Neglected autovacuum
is one of the most common causes of table bloat, index bloat, and transaction ID
wraparound (which can take your database offline).

---

## Key concepts

| Term | What it means |
|------|---------------|
| Dead tuples | Old row versions left behind by UPDATE/DELETE |
| Table bloat | Physical table size grows beyond live data size |
| Index bloat | Indexes grow to include pointers to dead tuples |
| XID wraparound | Transaction IDs are 32-bit; at ~2B transactions Postgres forces a VACUUM FREEZE or shuts down |
| `n_dead_tup` | `pg_stat_user_tables` column — count of dead tuples in a table |
| `last_autovacuum` | When autovacuum last ran on the table |

---

## Detecting bloat

```sql
-- Tables with high dead tuple ratio
SELECT
    schemaname,
    relname,
    n_live_tup,
    n_dead_tup,
    round(n_dead_tup::numeric / nullif(n_live_tup + n_dead_tup, 0) * 100, 1) AS dead_pct,
    last_autovacuum,
    last_autoanalyze
FROM pg_stat_user_tables
WHERE n_dead_tup > 1000
ORDER BY dead_pct DESC;

-- Tables that haven't been vacuumed recently
SELECT relname, last_autovacuum, last_autoanalyze
FROM pg_stat_user_tables
WHERE last_autovacuum < now() - interval '1 day'
   OR last_autovacuum IS NULL
ORDER BY last_autovacuum NULLS FIRST;

-- XID age — tables approaching wraparound (danger > 1.5 billion)
SELECT relname,
       age(relfrozenxid) AS xid_age,
       pg_size_pretty(pg_total_relation_size(oid)) AS size
FROM pg_class
WHERE relkind = 'r'
ORDER BY age(relfrozenxid) DESC
LIMIT 20;
```

---

## Autovacuum triggers (defaults)

Autovacuum fires on a table when:
```
dead tuples > autovacuum_vacuum_threshold + autovacuum_vacuum_scale_factor * n_live_tup
            = 50                          + 0.02                            * n_live_tup
```

For a table with 10 million rows this means autovacuum waits until
**200,050 dead tuples** accumulate — far too late for high-write tables.

---

## Per-table overrides (recommended approach)

Rather than changing global settings, override per table:

```sql
-- High-write table: vacuum more aggressively
ALTER TABLE orders SET (
    autovacuum_vacuum_scale_factor = 0.01,   -- 1% dead tuples triggers vacuum
    autovacuum_vacuum_threshold    = 100,
    autovacuum_analyze_scale_factor = 0.005,
    autovacuum_vacuum_cost_delay   = 2       -- ms, lower = faster vacuum
);

-- Append-only / rarely updated table: relax vacuum
ALTER TABLE audit_log SET (
    autovacuum_vacuum_scale_factor = 0.1,
    autovacuum_analyze_scale_factor = 0.05
);

-- Freeze-sensitive table near XID wraparound
ALTER TABLE large_historical SET (
    autovacuum_freeze_max_age = 100000000  -- vacuum freeze earlier
);
```

---

## Manual VACUUM when needed

```sql
-- Standard: reclaim dead tuples (doesn't lock)
VACUUM orders;

-- Also update planner statistics
VACUUM ANALYZE orders;

-- Reclaim space back to OS (locks table briefly, use in maintenance windows)
VACUUM FULL orders;

-- Freeze old XIDs to prevent wraparound
VACUUM FREEZE orders;
```

---

## Index bloat

VACUUM reclaims dead tuples in the heap but doesn't always shrink indexes.
Check index bloat:

```sql
SELECT
    t.relname AS table_name,
    i.relname AS index_name,
    pg_size_pretty(pg_relation_size(ix.indexrelid)) AS index_size,
    pg_size_pretty(pg_relation_size(ix.indrelid))   AS table_size
FROM pg_index ix
JOIN pg_class t ON t.oid = ix.indrelid
JOIN pg_class i ON i.oid = ix.indexrelid
JOIN pg_namespace ns ON ns.oid = t.relnamespace
WHERE ns.nspname = 'public'
ORDER BY pg_relation_size(ix.indexrelid) DESC;
```

To rebuild a bloated index without downtime:
```sql
REINDEX INDEX CONCURRENTLY idx_orders_user_id;
```

---

## Global autovacuum settings worth knowing

| Setting | Default | Notes |
|---------|---------|-------|
| `autovacuum_max_workers` | 3 | Increase to 5-6 on busy databases |
| `autovacuum_vacuum_cost_delay` | 2ms | Lower = faster, more I/O impact |
| `autovacuum_vacuum_scale_factor` | 0.02 | Lower for large tables |
| `autovacuum_analyze_scale_factor` | 0.1 | Lower to keep stats fresh |
| `maintenance_work_mem` | 64MB | Increase to 256MB–1GB for faster vacuum |

---

## Warning signs

- `n_dead_tup` consistently above 20% of `n_live_tup`
- `last_autovacuum` never runs (autovacuum may be blocked by long transactions)
- XID age above 1 billion — **act immediately**
- Table size far exceeds `pg_size_pretty` of actual data (bloat)

Long-running transactions block VACUUM from reclaiming dead tuples. Check:
```sql
SELECT pid, now() - xact_start AS duration, query
FROM pg_stat_activity
WHERE xact_start IS NOT NULL
ORDER BY duration DESC;
```
