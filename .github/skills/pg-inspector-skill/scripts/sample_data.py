#!/usr/bin/env python3
"""Show sample rows from a table. Usage: sample_data.py schema.table [limit]"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from _db import connect

if len(sys.argv) < 2:
    print("Usage: sample_data.py schema.table [limit]")
    sys.exit(1)

arg = sys.argv[1]
schema, table = arg.rsplit(".", 1) if "." in arg else ("public", arg)
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5

conn = connect()
cur = conn.cursor()

# Fetch column names first
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_schema = %s AND table_name = %s
    ORDER BY ordinal_position;
""", (schema, table))
col_names = [r[0] for r in cur.fetchall()]

if not col_names:
    print(f"Table '{schema}.{table}' not found.")
    sys.exit(1)

cur.execute(f'SELECT * FROM {schema}.{table} LIMIT %s;', (limit,))
rows = cur.fetchall()

if not rows:
    print(f"Table '{schema}.{table}' is empty.")
else:
    print(f"\nSample data from {schema}.{table} (first {len(rows)} rows):\n")
    col_widths = [max(len(str(col)), max((len(str(r[i])) for r in rows), default=0))
                  for i, col in enumerate(col_names)]
    col_widths = [min(w, 30) for w in col_widths]

    header = "  ".join(str(col)[:w].ljust(w) for col, w in zip(col_names, col_widths))
    print(header)
    print("-" * len(header))
    for row in rows:
        print("  ".join(str(v)[:w].ljust(w) if v is not None else "NULL".ljust(w)
                        for v, w in zip(row, col_widths)))
conn.close()
