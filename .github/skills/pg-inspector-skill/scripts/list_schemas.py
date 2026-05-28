#!/usr/bin/env python3
"""List all user-defined schemas in the database."""
import os, sys
try:
    import psycopg2
except ImportError:
    os.system(f"{sys.executable} -m pip install psycopg2-binary --break-system-packages -q")
    import psycopg2

sys.path.insert(0, os.path.dirname(__file__))
from _db import connect

conn = connect()
cur = conn.cursor()
cur.execute("""
    SELECT schema_name, schema_owner
    FROM information_schema.schemata
    WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast',
                               'pg_temp_1', 'pg_toast_temp_1')
    ORDER BY schema_name;
""")
rows = cur.fetchall()
print(f"{'Schema':<30} {'Owner'}")
print("-" * 50)
for schema, owner in rows:
    print(f"{schema:<30} {owner}")
conn.close()
