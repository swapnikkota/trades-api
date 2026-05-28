#!/usr/bin/env python3
"""Show estimated row counts for all tables in a schema."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from _db import connect

schema = sys.argv[1] if len(sys.argv) > 1 else "public"
conn = connect()
cur = conn.cursor()
cur.execute("""
    SELECT
        relname AS table_name,
        reltuples::bigint AS estimated_rows,
        pg_size_pretty(pg_total_relation_size(oid)) AS total_size
    FROM pg_class
    WHERE relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = %s)
      AND relkind = 'r'
    ORDER BY reltuples DESC;
""", (schema,))
rows = cur.fetchall()

if not rows:
    print(f"No tables found in schema '{schema}'.")
else:
    print(f"\nRow counts for schema '{schema}':\n")
    print(f"{'Table':<40} {'Est. Rows':>15}  {'Total Size':>12}")
    print("-" * 70)
    for tname, est_rows, size in rows:
        print(f"{tname:<40} {est_rows:>15,}  {size:>12}")
    print("\n(Row counts are estimates from pg_class; run ANALYZE for fresh stats)")
conn.close()
