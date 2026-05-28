#!/usr/bin/env python3
"""Describe columns of a table. Usage: describe_table.py schema.table"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from _db import connect

if len(sys.argv) < 2:
    print("Usage: describe_table.py schema.table  (or just table for public schema)")
    sys.exit(1)

arg = sys.argv[1]
schema, table = arg.rsplit(".", 1) if "." in arg else ("public", arg)

conn = connect()
cur = conn.cursor()

# Columns
cur.execute("""
    SELECT
        c.column_name,
        c.data_type,
        c.character_maximum_length,
        c.numeric_precision,
        c.numeric_scale,
        c.is_nullable,
        c.column_default,
        pgd.description AS comment
    FROM information_schema.columns c
    LEFT JOIN pg_catalog.pg_statio_all_tables st
        ON st.schemaname = c.table_schema AND st.relname = c.table_name
    LEFT JOIN pg_catalog.pg_description pgd
        ON pgd.objoid = st.relid AND pgd.objsubid = c.ordinal_position
    WHERE c.table_schema = %s AND c.table_name = %s
    ORDER BY c.ordinal_position;
""", (schema, table))
columns = cur.fetchall()

if not columns:
    print(f"Table '{schema}.{table}' not found or has no columns.")
    sys.exit(1)

# Primary key columns
cur.execute("""
    SELECT kcu.column_name
    FROM information_schema.table_constraints tc
    JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name
       AND tc.table_schema = kcu.table_schema
    WHERE tc.constraint_type = 'PRIMARY KEY'
      AND tc.table_schema = %s AND tc.table_name = %s;
""", (schema, table))
pk_cols = {r[0] for r in cur.fetchall()}

print(f"\nTable: {schema}.{table}\n")
print(f"{'Column':<25} {'Type':<20} {'Null':<6} {'PK':<4} {'Default':<25} Comment")
print("-" * 100)
for col, dtype, char_len, num_prec, num_scale, nullable, default, comment in columns:
    # Build friendly type string
    if char_len:
        full_type = f"{dtype}({char_len})"
    elif num_prec and dtype in ('numeric', 'decimal'):
        full_type = f"{dtype}({num_prec},{num_scale or 0})"
    else:
        full_type = dtype

    pk = "✓" if col in pk_cols else ""
    null = "YES" if nullable == "YES" else "NO"
    dflt = (default or "")[:24]
    print(f"{col:<25} {full_type:<20} {null:<6} {pk:<4} {dflt:<25} {comment or ''}")

conn.close()
