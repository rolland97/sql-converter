# Robust INSERT Parser Design

## Problem

The SQL-to-PHP and SQL-to-Excel converters do not process the full
`organization_2026-05-07_10-02-14.sql` dump. The current regex ends an
`INSERT` statement at the first semicolon. In the sample dump, `&amp;` inside a
quoted value contains a semicolon, so parsing stops before row `23`.

The visible symptom looks related to the comma in:

```sql
(23, "CREATIVE, IT AND PROGRAMMING &amp; TRANSLATION", 2, NULL, NULL, NULL),
```

The root cause is statement splitting that does not understand quoted strings.
Comma handling is also fragile and should be fixed in the same parser path.

## Scope

Fix all INSERT consumers:

- SQL-to-PHP conversion and column analysis.
- SQL-to-Excel conversion and column analysis.

Laravel migration conversion is out of scope because it parses `CREATE TABLE`,
not `INSERT`.

The UI and endpoint contracts stay unchanged.

## Approach

Create one shared INSERT parser module used by both PHP and Excel converters.
The parser will use a small state machine instead of regex-only parsing.

The shared parser will:

- Locate `INSERT INTO ... VALUES` statements.
- Treat `;` as statement-ending only when outside quoted strings.
- Split rows only on top-level row boundaries.
- Split values on commas only when outside quoted strings.
- Preserve commas, semicolons, HTML entities, and parentheses inside quoted
  values.
- Handle single-quoted and double-quoted SQL strings.
- Preserve current support for `NULL`, numeric values, and SQL escape
  sequences.

Consumer-specific conversion remains separate:

- PHP keeps `NULL` as `null`, keeps numbers suitable for PHP output, and escapes
  string output for PHP arrays.
- Excel converts `NULL` to `None`, converts numeric values to `int` or `float`,
  and writes strings as cell values.

## Error Handling

The parser will raise existing `SQLParsingError` and `ValidationError` types so
FastAPI error pages keep current behavior.

Errors should include the table name or line number when practical. Invalid rows
should not silently truncate values unless the existing converter behavior
intentionally permits it.

## Testing

Add focused parser tests for:

- A quoted value containing a comma.
- A quoted value containing `&amp;`.
- A quoted value containing a semicolon.
- Multiple rows after such values.
- `NULL`, integers, decimals, escaped quotes, and timestamps.
- Both PHP-shaped and Excel-shaped parsed output.

Also run a direct check against the provided organization dump and confirm the
`organization` table parses beyond row `23` through the end of the file.

## Acceptance Criteria

- The provided `organization_2026-05-07_10-02-14.sql` dump parses all INSERT
  rows for PHP conversion.
- Excel conversion uses the same fixed INSERT parsing behavior.
- The row containing `CREATIVE, IT AND PROGRAMMING &amp; TRANSLATION` is
  preserved as one field.
- Rows after that value are included in converted output.
- Existing endpoint behavior and file outputs remain compatible.
