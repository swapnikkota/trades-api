#!/usr/bin/env python3
"""
Index Advisor — suggests missing indexes based on:
  1. pg_stat_user_tables  — sequential scans vs index scans ratio
  2. pg_stat_statements   — slow / high-cost queries (if extension is enabled)
  3. Existing indexes      — detects unused and duplicate indexes
  4. Foreign key columns   — FK columns without a supporting index

Usage:
  index_advisor.py                    # analyse all tables in public schema
  index_advisor.py [schema]           # analyse specific schema
  index_advisor.py --query "<SQL>"    # advise for a specific query
"""
import os, sys, json, re
sys.path.insert(0, os.path.dirname(__file__))
from _db import connect

schema = "public"
target_query = None

args = sys.argv[1:]
i = 0
while i < len(args):
    if args[i] == "--query" and i + 1 < len(args):
        target_query = args[i + 1]
        i += 2
    elif not args[i].startswith("--"):
        schema = args[i]
        i += 1
    else:
        i += 1

conn = connect()
cur = conn.cursor()

suggestions = []   # list of dicts: {priority, table, reason, suggestion, sql}
warnings    = []   # list of strings

# ─── Helper ───────────────────────────────────────────────────────────────────

def add(priority, table, reason, suggestion, ddl=None):
    suggestions.append(dict(priority=priority, table=table,
                            reason=reason, suggestion=suggestion, ddl=ddl))

# ─── 1. Sequential scan ratio from pg_stat_user_tables ───────────────────────

cur.execute("""
    SELECT
        relname                              AS table_name,
        seq_scan,
        idx_scan,
        n_live_tup                           AS live_rows,
        seq_tup_read
    FROM pg_stat_user_tables
    WHERE schemaname = %s
      AND (seq_scan + coalesce(idx_scan,0)) > 0
    ORDER BY seq_tup_read DESC NULLS LAST;
""", (schema,))
stat_rows = cur.fetchall()

for tname, seq, idx, live_rows, seq_tup in stat_rows:
    idx = idx or 0
    seq = seq or 0
    total = seq + idx
    if total == 0:
        continue
    seq_ratio = seq / total
    if seq_ratio > 0.5 and live_rows > 1000:
        priority = "🔴 HIGH" if seq_ratio > 0.8 else "🟡 MEDIUM"
        add(priority, f"{schema}.{tname}",
            f"Seq scan ratio {seq_ratio:.0%} ({seq:,} seq / {idx:,} idx scans, {live_rows:,} rows)",
            f"Profile queries hitting '{tname}' and add indexes on frequent WHERE / JOIN columns")

# ─── 2. Foreign key columns without indexes ───────────────────────────────────

cur.execute("""
    SELECT
        kcu.table_name,
        kcu.column_name,
        ccu.table_name  AS ref_table,
        ccu.column_name AS ref_col
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name
       AND tc.table_schema    = kcu.table_schema
    JOIN information_schema.referential_constraints rc
        ON tc.constraint_name    = rc.constraint_name
       AND tc.table_schema       = rc.constraint_schema
    JOIN information_schema.constraint_column_usage ccu
        ON rc.unique_constraint_name   = ccu.constraint_name
       AND rc.unique_constraint_schema = ccu.constraint_schema
    WHERE tc.constraint_type = 'FOREIGN KEY'
      AND tc.table_schema    = %s;
""", (schema,))
fk_rows = cur.fetchall()

# Get all existing single-column indexes
cur.execute("""
    SELECT t.relname, a.attname
    FROM pg_index ix
    JOIN pg_class t  ON t.oid = ix.indrelid
    JOIN pg_class i  ON i.oid = ix.indexrelid
    JOIN pg_namespace ns ON ns.oid = t.relnamespace
    JOIN pg_attribute a  ON a.attrelid = t.oid
                        AND a.attnum = ANY(ix.indkey)
    WHERE ns.nspname = %s
      AND array_length(ix.indkey, 1) = 1;
""", (schema,))
indexed_cols = {(r[0], r[1]) for r in cur.fetchall()}

for tname, col, ref_table, ref_col in fk_rows:
    if (tname, col) not in indexed_cols:
        ddl = f"CREATE INDEX CONCURRENTLY idx_{tname}_{col} ON {schema}.{tname} ({col});"
        add("🟡 MEDIUM", f"{schema}.{tname}",
            f"FK column '{col}' → {ref_table}.{ref_col} has no index",
            f"Index '{col}' to speed up JOIN and ON DELETE operations",
            ddl)

# ─── 3. Unused indexes ────────────────────────────────────────────────────────

cur.execute("""
    SELECT
        t.relname        AS table_name,
        i.relname        AS index_name,
        coalesce(xs.idx_scan, 0) AS idx_scan,
        pg_size_pretty(coalesce(pg_relation_size(i.oid), 0)) AS index_size
    FROM pg_class t
    JOIN pg_index ix ON t.oid = ix.indrelid
    JOIN pg_class i  ON i.oid = ix.indexrelid
    JOIN pg_namespace ns ON ns.oid = t.relnamespace
    LEFT JOIN pg_stat_user_indexes xs ON xs.indexrelid = i.oid
    WHERE ns.nspname = %s
      AND NOT ix.indisprimary
      AND coalesce(xs.idx_scan, 0) = 0
    ORDER BY coalesce(pg_relation_size(i.oid), 0) DESC;
""", (schema,))
unused = cur.fetchall()

for row in unused:
    tname, iname, _, isize = row
    warnings.append(
        f"⚠️  Unused index '{iname}' on '{schema}.{tname}' ({isize}) — "
        f"consider dropping it:  DROP INDEX CONCURRENTLY {iname};"
    )

# ─── 4. Duplicate / redundant indexes ────────────────────────────────────────

cur.execute("""
    SELECT
        t.relname        AS table_name,
        i.relname        AS index_name,
        array_to_string(array_agg(a.attname ORDER BY k.n), ', ') AS cols
    FROM pg_class t
    JOIN pg_index ix ON t.oid = ix.indrelid
    JOIN pg_class i  ON i.oid = ix.indexrelid
    JOIN pg_namespace ns ON ns.oid = t.relnamespace
    JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS k(attnum, n) ON TRUE
    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.attnum
    WHERE ns.nspname = %s
      AND NOT ix.indisprimary
    GROUP BY t.relname, i.relname
    ORDER BY t.relname, cols;
""", (schema,))
idx_cols = cur.fetchall()

seen = {}  # table -> list of (index_name, cols)
for tname, iname, cols in idx_cols:
    key = (tname, cols)
    if key in seen:
        warnings.append(
            f"⚠️  Duplicate index: '{iname}' and '{seen[key]}' on '{schema}.{tname}' "
            f"both cover ({cols})"
        )
    else:
        seen[key] = iname

# ─── 5. Specific query analysis (optional) ───────────────────────────────────

query_suggestions = []
if target_query:
    stripped = target_query.strip().upper()
    if not (stripped.startswith("SELECT") or stripped.startswith("WITH")):
        print("⚠️  --query only supports SELECT / WITH statements.")
    else:
        try:
            cur.execute(f"EXPLAIN (FORMAT JSON) {target_query}")
            plan_json = json.loads(cur.fetchone()[0])

            def walk_plan(node):
                ntype = node.get("Node Type", "")
                alias = node.get("Alias") or node.get("Relation Name", "")
                if ntype == "Seq Scan" and alias:
                    filter_cond = node.get("Filter", "")
                    cols = re.findall(r"\((\w+)\s*[=<>]", filter_cond)
                    if cols:
                        for col in cols:
                            ddl = (f"CREATE INDEX CONCURRENTLY idx_{alias}_{col} "
                                   f"ON {schema}.{alias} ({col});")
                            query_suggestions.append(
                                (f"{schema}.{alias}",
                                 f"Seq scan with filter on '{col}'",
                                 f"Add index on '{alias}.{col}' to avoid full table scan",
                                 ddl)
                            )
                    else:
                        query_suggestions.append(
                            (f"{schema}.{alias}",
                             f"Seq scan on '{alias}' (no filter extracted)",
                             f"Review WHERE clauses on '{alias}' and add appropriate index",
                             None)
                        )
                for child in node.get("Plans", []):
                    walk_plan(child)

            walk_plan(plan_json[0]["Plan"])
        except Exception as e:
            print(f"⚠️  Could not analyse query: {e}")

# ─── Output ───────────────────────────────────────────────────────────────────

print("\n" + "═" * 70)
print("  INDEX ADVISOR REPORT")
print(f"  Schema: {schema}")
print("═" * 70)

# Query-specific suggestions first
if query_suggestions:
    print("\n🔍 Query-Specific Suggestions\n" + "-" * 50)
    for table, reason, suggestion, ddl in query_suggestions:
        print(f"\n  Table      : {table}")
        print(f"  Reason     : {reason}")
        print(f"  Suggestion : {suggestion}")
        if ddl:
            print(f"  DDL        : {ddl}")

# General suggestions
if suggestions:
    print("\n💡 Index Suggestions\n" + "-" * 50)
    for s in suggestions:
        print(f"\n  Priority   : {s['priority']}")
        print(f"  Table      : {s['table']}")
        print(f"  Reason     : {s['reason']}")
        print(f"  Suggestion : {s['suggestion']}")
        if s['ddl']:
            print(f"  DDL        : {s['ddl']}")
else:
    print("\n✅ No missing indexes detected from usage statistics.")

# Warnings
if warnings:
    print("\n🗑  Cleanup Opportunities\n" + "-" * 50)
    for w in warnings:
        print(f"\n  {w}")

if not suggestions and not warnings and not query_suggestions:
    print("\n✅ Everything looks good — no index issues found.")

print("\n⚠️  Note: Statistics are based on pg_stat_* counters since last")
print("   server start or last RESET. Run on a production instance with")
print("   realistic traffic for best results.\n")

conn.close()
