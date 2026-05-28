#!/usr/bin/env python3
"""Verify PostgreSQL connection and print server info."""
import os, sys

try:
    import psycopg2
except ImportError:
    print("Installing psycopg2-binary...")
    os.system(f"{sys.executable} -m pip install psycopg2-binary --break-system-packages -q")
    import psycopg2

def get_conn_params():
    url = os.environ.get("DATABASE_URL")
    if url:
        return {"dsn": url}
    return {
        "host":     os.environ.get("PGHOST", "localhost"),
        "port":     os.environ.get("PGPORT", "5432"),
        "user":     os.environ.get("PGUSER"),
        "password": os.environ.get("PGPASSWORD"),
        "dbname":   os.environ.get("PGDATABASE"),
    }

try:
    conn = psycopg2.connect(**get_conn_params())
    cur = conn.cursor()
    cur.execute("SELECT version(), current_database(), current_user;")
    version, dbname, user = cur.fetchone()
    print(f"✓ Connected to database: {dbname}")
    print(f"  User   : {user}")
    print(f"  Server : {version.split(',')[0]}")
    conn.close()
except Exception as e:
    print(f"✗ Connection failed: {e}", file=sys.stderr)
    sys.exit(1)
