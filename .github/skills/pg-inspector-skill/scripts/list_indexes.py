#!/usr/bin/env python3
"""List indexes for a table. Usage: list_indexes.py schema.table"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from _db import connect

arg = sys.argv[1] if len(sys.argv) > 1 else "public."
schema, table = arg.rsplit(".", 1) if "." in arg else ("public", arg)

conn = connect()
cur = conn.cursor()
cur.execute("""
    SELECT
        i.relname AS index_name,
        ix.indisprimary AS is_primary,
        ix.indisunique  AS is_unique,
        array_to_string(array_agg(a.attname ORDER BY k.n), ', ') AS columns,
        am.amname AS index_type
    FROM pg_class t
    JOIN pg_index ix ON t.oid = ix.indrelid
    JOIN pg_class i  ON i.oid = ix.indexrelid
    JOIN pg_am am    ON am.oid = i.relam
    JOIN pg_namespace ns ON ns.oid = t.relnamespace
    JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS k(attnum, n) ON TRUE
    JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.attnum
    WHERE ns.nspname = %s AND t.relname = %s
    GROUP BY i.relname, ix.indisprimary, ix.indisunique, am.amname
    ORDER BY ix.indisprimary DESC, i.relname;
""", (schema, table))
rows = cur.fetchall()

if not rows:
    print(f"No indexes found on '{schema}.{table}'.")
else:
    print(f"\nIndexes on {schema}.{table}:\n")
    print(f"{'Index Name':<40} {'Type':<10} {'Primary':<9} {'Unique':<7} Columns")
    print("-" * 100)
    for name, is_pk, is_unique, cols, itype in rows:
        print(f"{name:<40} {itype:<10} {'✓' if is_pk else '':<9} {'✓' if is_unique else '':<7} {cols}")
conn.close()
