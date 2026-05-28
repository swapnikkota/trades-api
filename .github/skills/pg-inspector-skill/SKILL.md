---
name: pg-inspector
description: >
  Connects to a PostgreSQL database and reads its structure — schemas, tables,
  columns, data types, primary/foreign keys, indexes, constraints, row counts,
  and sample data. Also explains and analyses SQL queries using EXPLAIN ANALYZE,
  flagging slow scans, missing indexes, and high-cost operations.
  Use this skill whenever the user wants to explore, document, or understand a
  PostgreSQL database's metadata or schema, or asks to explain / analyse / 
  optimise a SQL query. Trigger on phrases like "inspect the database", "show me
  the schema", "what tables exist", "describe this table", "list columns", "show
  indexes", "explain this query", "why is my query slow", "analyse this SQL",
  "query plan", "suggest indexes", "missing indexes", "unused indexes",
  "index advice", or any question about the DB's shape, contents, or performance.
---

# PostgreSQL Inspector Skill

Connects to a PostgreSQL database via environment variables and answers
questions about its structure and metadata.

---

## Connection Setup

The database connection is read from environment variables. Check for these
in order:

1. `DATABASE_URL` — full connection string, e.g.
   `postgresql://user:pass@host:5432/dbname`
2. Individual vars: `PGHOST`, `PGPORT` (default 5432), `PGUSER`, `PGPASSWORD`,
   `PGDATABASE`

**First step on every task**: verify the connection works by running
`scripts/connect_check.py`. If it fails, report the error clearly and ask the
user to check their environment variables — do not proceed.

---

## Workflow

### 1. Establish Connection
```bash
python scripts/connect_check.py
```
Prints connected server version + database name on success.

### 2. Decide What to Fetch

| User asks about…              | Script to run                        |
|-------------------------------|--------------------------------------|
| Schemas / overall structure   | `scripts/list_schemas.py`            |
| Tables in a schema            | `scripts/list_tables.py [schema]`    |
| Columns / structure of table  | `scripts/describe_table.py <schema.table>` |
| Indexes on a table            | `scripts/list_indexes.py <schema.table>` |
| Constraints (FK, unique, etc) | `scripts/list_constraints.py <schema.table>` |
| Row counts                    | `scripts/row_counts.py [schema]`     |
| Sample rows                   | `scripts/sample_data.py <schema.table> [limit]` |
| Explain / analyse a query     | `scripts/explain_query.py "<SQL>" [--analyze] [--json]` |
| Index recommendations         | `scripts/index_advisor.py [schema]`  |
| Index advice for a query      | `scripts/index_advisor.py --query "<SQL>"` |
| Full database overview        | Run all of the above in sequence     |

### 3. Present Results

- Format output as clean markdown tables where possible
- For a full overview, structure the response as:
  1. Server info & database name
  2. Schema list
  3. Per-schema: table list with row counts
  4. For each table (if ≤ 10 tables): columns + indexes + constraints
  5. Offer to drill into specific tables if there are many
- Always note nullable columns, primary keys, and foreign key relationships
  clearly
- If the user asks for sample data, show max 5 rows by default unless they
  specify otherwise

---

## Index Advisor

When the user asks for index recommendations, missing indexes, or wants to
optimise a schema:

1. Run `scripts/index_advisor.py [schema]` for a full schema-wide report
2. Or run `scripts/index_advisor.py --query "<SQL>"` for a specific query
3. Present suggestions grouped by priority (🔴 HIGH → 🟡 MEDIUM)
4. Always include the ready-to-run DDL so the user can copy-paste it
5. Highlight cleanup opportunities (unused / duplicate indexes) separately

**What it analyses:**
- **Sequential scan ratio** from `pg_stat_user_tables` — tables getting mostly
  seq scans with many rows are flagged
- **FK columns without indexes** — foreign key columns that lack a supporting
  index (cause slow JOINs and ON DELETE cascades)
- **Unused indexes** — indexes with zero scans since last stats reset
- **Duplicate indexes** — two indexes covering the same column set
- **Query-specific** — parses `EXPLAIN` output for a given SQL and maps seq
  scans to specific columns

> Stats come from `pg_stat_*` counters. For best results run on a production
> instance with real traffic. Suggest `ANALYZE` if stats look stale.

---

## Query Explainer

When the user asks to explain, analyse, or optimise a SQL query:

1. Extract the SQL from their message (clean up formatting if needed)
2. Run `scripts/explain_query.py "<SQL>" --analyze` for full analysis
3. Present the plan, summary metrics, and any observations
4. Suggest fixes for any warnings — e.g. "Add an index on `orders.user_id`"

**Flags:**
- `--analyze` — actually executes the query to get real timings (safe for SELECT)
- `--json` — outputs the raw JSON plan (useful for deep inspection)

**What the script checks for:**
- Sequential scans on large tables → suggest indexes
- High total cost estimates → flag for optimisation
- Stale statistics → suggest `ANALYZE <table>`
- Temporary file spills → suggest increasing `work_mem`

> Only SELECT / WITH / TABLE queries are allowed. The script blocks anything else.

---

## Error Handling

| Error | Action |
|-------|--------|
| Connection refused | Ask user to verify `DATABASE_URL` / PG* vars and that the DB is reachable |
| Permission denied on a table | Skip it, note it in output, continue |
| Schema not found | List available schemas and ask user to confirm |
| Table not found | List tables in the schema and suggest closest match |

---

## Reference Files

- `references/pg_queries.md` — Raw SQL queries used by the scripts (useful
  if you need to write ad-hoc queries or customise behaviour)
- `references/pg_types.md` — PostgreSQL type reference for explaining column
  types to users

---

## Notes

- Always use read-only queries — never INSERT, UPDATE, DELETE, or DDL
- Default schema is `public` if the user doesn't specify one
- `information_schema` and `pg_catalog` are system schemas — skip them in
  overviews unless the user explicitly asks
- When describing a table, always include: column name, data type, nullable,
  default value, and whether it's part of a PK or FK
