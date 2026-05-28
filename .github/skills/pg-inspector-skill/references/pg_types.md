# PostgreSQL Type Reference

Quick guide for explaining column types to users.

## Numeric
| Type | Description |
|------|-------------|
| `smallint` / `int2` | 2-byte integer (-32768 to 32767) |
| `integer` / `int4` | 4-byte integer (-2B to 2B) |
| `bigint` / `int8` | 8-byte integer (very large numbers) |
| `numeric(p,s)` | Exact decimal, p digits total, s after decimal |
| `real` / `float4` | 4-byte floating point |
| `double precision` / `float8` | 8-byte floating point |
| `serial` | Auto-incrementing integer (alias for int + sequence) |
| `bigserial` | Auto-incrementing bigint |

## Text
| Type | Description |
|------|-------------|
| `char(n)` | Fixed-length, blank-padded |
| `varchar(n)` | Variable-length, max n chars |
| `text` | Unlimited variable-length |

## Date & Time
| Type | Description |
|------|-------------|
| `date` | Calendar date only |
| `time` | Time of day (no timezone) |
| `timetz` | Time of day with timezone |
| `timestamp` | Date + time (no timezone) |
| `timestamptz` | Date + time with timezone (recommended) |
| `interval` | Time span |

## Boolean
| Type | Description |
|------|-------------|
| `boolean` | true / false / null |

## Binary
| Type | Description |
|------|-------------|
| `bytea` | Binary data (byte array) |

## JSON
| Type | Description |
|------|-------------|
| `json` | Text JSON, validated on insert |
| `jsonb` | Binary JSON, indexed & faster to query |

## Arrays
Any type can be an array: `integer[]`, `text[]`, etc.

## Special
| Type | Description |
|------|-------------|
| `uuid` | 128-bit universally unique identifier |
| `inet` | IPv4 or IPv6 address |
| `cidr` | IP network address |
| `macaddr` | MAC address |
| `tsvector` | Full-text search document |
| `tsquery` | Full-text search query |
| `point`, `line`, `polygon` | Geometric types |
| `money` | Currency (locale-dependent — prefer `numeric`) |
