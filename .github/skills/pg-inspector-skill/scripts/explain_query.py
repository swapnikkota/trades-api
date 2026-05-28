#!/usr/bin/env python3
"""
Explain a SQL query using EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT).
Usage: explain_query.py "<SQL>" [--analyze] [--json]

  --analyze   Run EXPLAIN ANALYZE (actually executes the query — safe for SELECT)
  --json      Output raw JSON plan instead of formatted text
"""
import os, sys, json, re
sys.path.insert(0, os.path.dirname(__file__))
from _db import connect

if len(sys.argv) < 2:
    print("Usage: explain_query.py \"<SQL>\" [--analyze] [--json]")
    sys.exit(1)

args = sys.argv[1:]
flags = {a for a in args if a.startswith("--")}
sql = next((a for a in args if not a.startswith("--")), None)

if not sql:
    print("Error: no SQL query provided.")
    sys.exit(1)

# Safety check — only allow SELECT / WITH (read-only)
stripped = sql.strip().lstrip("(").upper()
if not (stripped.startswith("SELECT") or stripped.startswith("WITH") or stripped.startswith("TABLE")):
    print("✗ Only SELECT / WITH / TABLE queries are allowed for safety.")
    sys.exit(1)

use_analyze = "--analyze" in flags
use_json    = "--json" in flags

conn = connect()
conn.autocommit = True  # EXPLAIN ANALYZE inside a transaction is fine but autocommit is cleaner
cur = conn.cursor()

if use_json:
    explain_sql = f"EXPLAIN (ANALYZE {str(use_analyze).upper()}, BUFFERS, FORMAT JSON) {sql}"
else:
    explain_sql = f"EXPLAIN (ANALYZE {str(use_analyze).upper()}, BUFFERS, FORMAT TEXT) {sql}"

try:
    cur.execute(explain_sql)
    rows = cur.fetchall()
except Exception as e:
    print(f"✗ Query failed: {e}")
    sys.exit(1)

if use_json:
    plan = json.loads(rows[0][0])
    print(json.dumps(plan, indent=2))
    conn.close()
    sys.exit(0)

# ── Text plan output ──────────────────────────────────────────────────────────
plan_lines = [r[0] for r in rows]
plan_text  = "\n".join(plan_lines)

print("\n" + "═" * 70)
print("  QUERY PLAN")
print("═" * 70)
print(plan_text)
print("═" * 70)

# ── Parse key metrics from ANALYZE output ────────────────────────────────────
if use_analyze:
    exec_time  = re.search(r"Execution Time:\s+([\d.]+)\s+ms", plan_text)
    plan_time  = re.search(r"Planning Time:\s+([\d.]+)\s+ms", plan_text)
    rows_out   = re.search(r"rows=(\d+)", plan_text)

    print("\n📊 Summary")
    print("-" * 40)
    if plan_time:
        print(f"  Planning time  : {plan_time.group(1)} ms")
    if exec_time:
        ms = float(exec_time.group(1))
        label = "🟢 fast" if ms < 100 else ("🟡 moderate" if ms < 1000 else "🔴 slow")
        print(f"  Execution time : {ms} ms  {label}")

# ── Warnings ──────────────────────────────────────────────────────────────────
warnings = []

if "Seq Scan" in plan_text:
    # Find which tables are seq-scanned
    tables = re.findall(r"Seq Scan on (\S+)", plan_text)
    for t in set(tables):
        warnings.append(f"⚠️  Sequential scan on '{t}' — consider adding an index if this table is large")

if "Hash Join" in plan_text and "rows=1)" in plan_text:
    warnings.append("⚠️  Hash join with very low row estimate — statistics may be stale, try ANALYZE <table>")

if re.search(r"cost=\d+\.\d+\.\.(\d+)\.", plan_text):
    costs = re.findall(r"\.\.([\d]+)\.", plan_text)
    if costs and int(max(costs, key=int)) > 100000:
        warnings.append("⚠️  High estimated cost — query may benefit from optimisation or better indexes")

if "temporary file" in plan_text.lower():
    warnings.append("⚠️  Temporary files used — query exceeded work_mem; consider increasing it")

if warnings:
    print("\n🔍 Observations")
    print("-" * 40)
    for w in warnings:
        print(f"  {w}")
else:
    print("\n✅ No obvious issues detected in the plan.")

print()
conn.close()
