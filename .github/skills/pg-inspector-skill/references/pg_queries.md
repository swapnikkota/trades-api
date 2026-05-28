# PostgreSQL Metadata Queries Reference

Use these when you need to run ad-hoc queries or customise script behaviour.

---

## List User Schemas
```sql
SELECT schema_name, schema_owner
FROM information_schema.schemata
WHERE schema_name NOT IN ('information_schema','pg_catalog','pg_toast')
ORDER BY schema_name;
```

## List Tables in a Schema
```sql
SELECT table_name, table_type
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

## Describe Table Columns
```sql
SELECT column_name, data_type, character_maximum_length,
       is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'your_table'
ORDER BY ordinal_position;
```

## Primary Keys
```sql
SELECT kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
WHERE tc.constraint_type = 'PRIMARY KEY'
  AND tc.table_schema = 'public' AND tc.table_name = 'your_table';
```

## Foreign Keys
```sql
SELECT
    kcu.column_name,
    ccu.table_name  AS foreign_table,
    ccu.column_name AS foreign_column,
    rc.delete_rule, rc.update_rule
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.referential_constraints rc
    ON tc.constraint_name = rc.constraint_name
JOIN information_schema.constraint_column_usage ccu
    ON rc.unique_constraint_name = ccu.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'public' AND tc.table_name = 'your_table';
```

## Indexes
```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public' AND tablename = 'your_table';
```

## Row Counts (Estimated)
```sql
SELECT relname, reltuples::bigint, pg_size_pretty(pg_total_relation_size(oid))
FROM pg_class
WHERE relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
  AND relkind = 'r'
ORDER BY reltuples DESC;
```

## Table Comments
```sql
SELECT obj_description('public.your_table'::regclass, 'pg_class');
```

## Column Comments
```sql
SELECT a.attname, pgd.description
FROM pg_catalog.pg_statio_all_tables st
JOIN pg_catalog.pg_description pgd ON pgd.objoid = st.relid
JOIN pg_catalog.pg_attribute a ON a.attrelid = st.relid AND a.attnum = pgd.objsubid
WHERE st.schemaname = 'public' AND st.relname = 'your_table';
```

## Check Constraints
```sql
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'public.your_table'::regclass AND contype = 'c';
```

## Sequences Linked to a Table
```sql
SELECT sequence_name
FROM information_schema.sequences
WHERE sequence_schema = 'public';
```
