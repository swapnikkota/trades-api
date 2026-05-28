#!/usr/bin/env python3
"""
Codebase Query Analyzer — scans source files for SQL queries and runs
index advice + EXPLAIN on each one.

Usage:
  analyze_codebase.py <path>                  # scan a directory or file
  analyze_codebase.py <path> --explain        # also run EXPLAIN on each query
  analyze_codebase.py <path> --ext .py .js    # limit to specific file types
  analyze_codebase.py <path> --schema myschema

Supported patterns (auto-detected):
  - Raw SQL strings:  SELECT ... FROM ...
  - ORM-style:        .where(  .filter(  .query(  .execute(  .raw(
  - Template strings, multiline strings, f-strings
  - JS/TS: db.query(  pool.query(  knex.(  sequelize.query(
  - Java/Kotlin: @Query(  entityManager.createQuery(  jdbcTemplate
"""
import os, sys, re, json
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from _db import connect

# ─── Args ─────────────────────────────────────────────────────────────────────

args = sys.argv[1:]
scan_path = None
run_explain = False
schema = "public"
extensions = {".py", ".js", ".ts", ".java", ".kt", ".go", ".rb", ".php",
              ".sql", ".env", ".txt"}

i = 0
while i < len(args):
    if args[i] == "--explain":
        run_explain = True; i += 1
    elif args[i] == "--schema" and i + 1 < len(args):
        schema = args[i + 1]; i += 2
    elif args[i] == "--ext" and i + 1 < len(args):
        extensions = set()
        i += 1
        while i < len(args) and not args[i].startswith("--"):
            extensions.add(args[i] if args[i].startswith(".") else f".{args[i]}")
            i += 1
    elif not args[i].startswith("--"):
        scan_path = args[i]; i += 1
    else:
        i += 1

if not scan_path:
    print("Usage: analyze_codebase.py <path> [--explain] [--schema name] [--ext .py .js ...]")
    sys.exit(1)

scan_path = Path(scan_path).resolve()
if not scan_path.exists():
    print(f"✗ Path not found: {scan_path}")
    sys.exit(1)

# ─── SQL Extraction ───────────────────────────────────────────────────────────

# Patterns that indicate a SQL string follows
TRIGGER_PATTERNS = [
    r'(?:execute|query|raw|run|prepare|cursor\.execute|db\.query|pool\.query'
    r'|knex\.raw|sequelize\.query|entityManager\.create(?:Native)?Query'
    r'|jdbcTemplate\.\w+|@Query|\.where\b|\.filter\b|\.select\b)',
]

# Regex to find bare SELECT/INSERT/UPDATE/DELETE/WITH blocks
SQL_REGEX = re.compile(
    r'(?<!["\w])'                          # not inside another word
    r'((?:SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM|WITH\s+\w+\s+AS)\b'
    r'[\s\S]{10,800}?)'                    # capture up to ~800 chars
    r'(?=["\'\`;]|\Z|\n\n)',               # stop at quote, backtick, blank line
    re.IGNORECASE
)

# Multiline string patterns (Python triple-quote, JS template literal)
MULTILINE_REGEX = re.compile(
    r'(?:"""|\'\'\`|`)(\s*(?:SELECT|INSERT|UPDATE|DELETE|WITH)[\s\S]+?)(?:"""|\'\'\`|`)',
    re.IGNORECASE
)

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv",
             "dist", "build", ".next", "target", "vendor"}

def clean_sql(sql):
    """Strip string delimiters, interpolation placeholders, normalize whitespace."""
    sql = re.sub(r'\$\{[^}]+\}', '?', sql)       # JS template vars
    sql = re.sub(r'%\([^)]+\)s', '%s', sql)       # Python named params
    sql = re.sub(r':\w+', ':param', sql)           # named bind params
    sql = re.sub(r'\s+', ' ', sql).strip()
    sql = sql.strip('"\'`')
    return sql

def extract_sql_from_file(filepath):
    try:
        text = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    found = []

    # 1. Multiline strings
    for m in MULTILINE_REGEX.finditer(text):
        sql = clean_sql(m.group(1))
        if len(sql) > 15:
            found.append((sql, m.start()))

    # 2. Bare SQL blocks
    for m in SQL_REGEX.finditer(text):
        sql = clean_sql(m.group(1))
        if len(sql) > 15 and not any(sql in f for f in found):
            found.append((sql, m.start()))

    # Deduplicate by normalized SQL
    seen = set()
    unique = []
    for sql, pos in found:
        key = re.sub(r'\s+', ' ', sql.upper()[:120])
        if key not in seen:
            seen.add(key)
            # Get approximate line number
            line_no = text[:pos].count('\n') + 1
            unique.append((sql, line_no))

    return unique

def collect_files(root, extensions):
    root = Path(root)
    if root.is_file():
        return [root]
    files = []
    for p in root.rglob("*"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.is_file() and p.suffix.lower() in extensions:
            files.append(p)
    return sorted(files)

# ─── Scan ─────────────────────────────────────────────────────────────────────

print(f"\n🔍 Scanning: {scan_path}")
print(f"   Extensions : {', '.join(sorted(extensions))}")
print(f"   Schema     : {schema}")
print(f"   EXPLAIN    : {'yes' if run_explain else 'no (use --explain to enable)'}")
print()

files = collect_files(scan_path, extensions)
all_queries = []   # (file, line, sql)

for f in files:
    queries = extract_sql_from_file(f)
    for sql, line in queries:
        rel = f.relative_to(scan_path) if scan_path.is_dir() else f.name
        all_queries.append((str(rel), line, sql))

if not all_queries:
    print("No SQL queries found. Try --ext to broaden the file types searched.")
    sys.exit(0)

print(f"Found {len(all_queries)} SQL queries across {len(files)} files scanned.\n")

# ─── Analyse each query ───────────────────────────────────────────────────────

conn = connect()
cur  = conn.cursor()

results = []   # (file, line, sql, issues, plan_summary)

for filepath, line, sql in all_queries:
    issues = []
    plan_summary = None

    # Only EXPLAIN SELECT / WITH queries
    stripped = sql.strip().upper()
    is_select = stripped.startswith("SELECT") or stripped.startswith("WITH")

    if is_select and run_explain:
        try:
            cur.execute(f"EXPLAIN (FORMAT JSON) {sql}")
            plan = json.loads(cur.fetchone()[0])[0]["Plan"]

            total_cost = plan.get("Total Cost", 0)
            plan_rows  = plan.get("Plan Rows", 0)

            def find_issues(node, issues):
                ntype  = node.get("Node Type", "")
                rel    = node.get("Relation Name") or node.get("Alias", "")
                filt   = node.get("Filter", "")
                cost   = node.get("Total Cost", 0)

                if ntype == "Seq Scan" and rel:
                    cols = re.findall(r'\b(\w+)\s*[=<>]', filt)
                    if cols:
                        issues.append(f"Seq scan on '{rel}' filtering on: {', '.join(set(cols))} → add index")
                    else:
                        issues.append(f"Seq scan on '{rel}' (full table scan)")

                if ntype in ("Hash Join", "Merge Join", "Nested Loop"):
                    cond = node.get("Hash Cond") or node.get("Join Filter", "")
                    if cond:
                        issues.append(f"{ntype} on condition: {cond}")

                for child in node.get("Plans", []):
                    find_issues(child, issues)

            find_issues(plan, issues)

            label = "🟢" if total_cost < 1000 else ("🟡" if total_cost < 50000 else "🔴")
            plan_summary = f"{label} cost={total_cost:.0f}  rows≈{plan_rows}"

        except Exception as e:
            plan_summary = f"⚠️  Could not explain: {e}"

    results.append((filepath, line, sql, issues, plan_summary))

conn.close()

# ─── Report ───────────────────────────────────────────────────────────────────

print("═" * 70)
print("  CODEBASE QUERY ANALYSIS REPORT")
print("═" * 70)

flagged   = [(f, l, s, iss, ps) for f, l, s, iss, ps in results if iss]
clean     = [(f, l, s, iss, ps) for f, l, s, iss, ps in results if not iss]

if flagged:
    print(f"\n⚠️  {len(flagged)} queries with potential issues:\n")
    for filepath, line, sql, issues, plan_summary in flagged:
        print(f"  📄 {filepath}:{line}")
        preview = sql[:120].replace('\n', ' ')
        print(f"     SQL     : {preview}{'...' if len(sql) > 120 else ''}")
        if plan_summary:
            print(f"     Plan    : {plan_summary}")
        for issue in issues:
            print(f"     ⚠️   {issue}")
        print()
else:
    print("\n✅ No issues found in extracted queries.")

if clean and run_explain:
    print(f"✅ {len(clean)} queries look fine (no seq scans or join issues detected).")

# Summary table of all queries
print(f"\n{'─' * 70}")
print(f"  All {len(results)} queries found:\n")
print(f"  {'File':<45} {'Line':>5}  Preview")
print(f"  {'─'*45} {'─'*5}  {'─'*20}")
for filepath, line, sql, issues, _ in results:
    flag  = "⚠️ " if issues else "✅ "
    preview = sql[:40].replace('\n', ' ')
    print(f"  {flag}{filepath[:43]:<45} {line:>5}  {preview}...")

print(f"\n💡 Tip: re-run with --explain to get query plans for all SELECT queries.")
print(f"💡 Tip: pipe output to a file:  python3 analyze_codebase.py . > report.txt\n")
