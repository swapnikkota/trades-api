"""Shared connection helper for all pg-inspector scripts."""
import os
try:
    import psycopg2
except ImportError:
    import subprocess, sys
    subprocess.run([sys.executable, "-m", "pip", "install",
                    "psycopg2-binary", "--break-system-packages", "-q"])
    import psycopg2

def connect():
    url = os.environ.get("DATABASE_URL")
    if url:
        return psycopg2.connect(dsn=url)
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        user=os.environ.get("PGUSER"),
        password=os.environ.get("PGPASSWORD"),
        dbname=os.environ.get("PGDATABASE"),
    )
