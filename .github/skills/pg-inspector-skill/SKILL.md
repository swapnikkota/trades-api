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
  "query plan", or any question about the DB's shape, contents, or performance.
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
