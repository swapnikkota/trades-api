#!/usr/bin/env python3
"""List constraints for a table. Usage: list_constraints.py schema.table"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from _db import connect

arg = sys.argv[1] if len(sys.argv) > 1 else "public."
schema, table = arg.rsplit(".", 1) if "." in arg else ("public", arg)

conn = connect()
cur = conn.cursor()
cur.execute("""
    SELECT
        tc.constraint_name,
        tc.constraint_type,
        string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) AS columns,
        ccu.table_schema AS foreign_schema,
        ccu.table_name   AS foreign_table,
        string_agg(DISTINCT ccu.column_name, ', ') AS foreign_columns,
        rc.delete_rule,
        rc.update_rule
    FROM information_schema.table_constraints tc
    LEFT JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name
       AND tc.table_schema = kcu.table_schema
       AND tc.table_name = kcu.table_name
    LEFT JOIN information_schema.referential_constraints rc
        ON tc.constraint_name = rc.constraint_name
       AND tc.table_schema = rc.constraint_schema
    LEFT JOIN information_schema.constraint_column_usage ccu
        ON rc.unique_constraint_name = ccu.constraint_name
       AND rc.unique_constraint_schema = ccu.constraint_schema
    WHERE tc.table_schema = %s AND tc.table_name = %s
    GROUP BY tc.constraint_name, tc.constraint_type,
             ccu.table_schema, ccu.table_name,
             rc.delete_rule, rc.update_rule
    ORDER BY tc.constraint_type, tc.constraint_name;
""", (schema, table))
rows = cur.fetchall()

if not rows:
    print(f"No constraints found on '{schema}.{table}'.")
else:
    print(f"\nConstraints on {schema}.{table}:\n")
    for name, ctype, cols, fschema, ftable, fcols, del_rule, upd_rule in rows:
        line = f"  [{ctype}] {name}  →  columns: {cols}"
        if ctype == "FOREIGN KEY":
            line += f"  references {fschema}.{ftable}({fcols})"
            line += f"  ON DELETE {del_rule}  ON UPDATE {upd_rule}"
        print(line)
conn.close()
