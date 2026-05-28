#!/usr/bin/env python3
"""List tables in a schema (default: public)."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from _db import connect

schema = sys.argv[1] if len(sys.argv) > 1 else "public"
conn = connect()
cur = conn.cursor()
cur.execute("""
    SELECT
        t.table_name,
        t.table_type,
        obj_description((quote_ident(t.table_schema)||'.'||quote_ident(t.table_name))::regclass, 'pg_class') AS comment
    FROM information_schema.tables t
    WHERE t.table_schema = %s
      AND t.table_type IN ('BASE TABLE', 'VIEW')
    ORDER BY t.table_type, t.table_name;
""", (schema,))
rows = cur.fetchall()
if not rows:
    print(f"No tables found in schema '{schema}'.")
else:
    print(f"Tables in schema '{schema}':\n")
    print(f"{'Table':<40} {'Type':<12} Comment")
    print("-" * 80)
    for name, ttype, comment in rows:
        print(f"{name:<40} {ttype:<12} {comment or ''}")
conn.close()
