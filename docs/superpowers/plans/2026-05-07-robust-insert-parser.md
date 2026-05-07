# Robust INSERT Parser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse every row in SQL INSERT dumps even when quoted values contain commas, semicolons, HTML entities, or parentheses.

**Architecture:** Add one shared `converters/insert_parser.py` module that extracts INSERT statements and row values with a quote-aware state machine. PHP and Excel converters keep their own output formatting but consume the same parsed rows.

**Tech Stack:** Python 3, FastAPI app modules, built-in `unittest`, existing `SQLParsingError` and `ValidationError`.

---

## File Structure

- Create `converters/insert_parser.py`: shared INSERT parsing, row splitting, value splitting, SQL escape handling, value token classification.
- Modify `converters/php_converter.py`: remove duplicated INSERT parsing internals and adapt shared parsed values to current PHP array shape.
- Modify `converters/excel_converter.py`: remove duplicated INSERT parsing internals and adapt shared parsed values to current Excel workbook shape.
- Create `tests/test_insert_parser.py`: direct parser tests for semicolon/comma/entity behavior.
- Create `tests/test_php_converter.py`: PHP converter compatibility tests.
- Create `tests/test_excel_converter.py`: Excel converter compatibility tests.

---

### Task 1: Shared INSERT Parser

**Files:**
- Create: `converters/insert_parser.py`
- Test: `tests/test_insert_parser.py`

- [ ] **Step 1: Write failing parser tests**

Create `tests/test_insert_parser.py`:

```python
import unittest

from converters.insert_parser import parse_insert_statements


class InsertParserTest(unittest.TestCase):
    def test_parses_semicolon_and_comma_inside_double_quoted_value(self):
        sql = '''
        INSERT INTO `organization` (`id`, `name`, `parent_id`, `supervisor`, `deleted_by`, `deleted_at`) VALUES
            (21, "CORPORATE ACCOUNTS SUPPORT", 2, NULL, NULL, NULL),
            (23, "CREATIVE, IT AND PROGRAMMING &amp; TRANSLATION", 2, NULL, NULL, NULL),
            (24, "E-COMMERCE", 2, NULL, NULL, NULL);
        '''

        parsed = parse_insert_statements(sql)

        self.assertEqual(["organization"], list(parsed.keys()))
        self.assertEqual(
            ["id", "name", "parent_id", "supervisor", "deleted_by", "deleted_at"],
            parsed["organization"]["columns"],
        )
        self.assertEqual(3, len(parsed["organization"]["rows"]))
        self.assertEqual(
            "CREATIVE, IT AND PROGRAMMING &amp; TRANSLATION",
            parsed["organization"]["rows"][1][1],
        )
        self.assertEqual("E-COMMERCE", parsed["organization"]["rows"][2][1])

    def test_parses_semicolon_inside_single_quoted_value(self):
        sql = "INSERT INTO `notes` (`id`, `body`) VALUES (1, 'first; still same value'), (2, 'next');"

        parsed = parse_insert_statements(sql)

        self.assertEqual(2, len(parsed["notes"]["rows"]))
        self.assertEqual("first; still same value", parsed["notes"]["rows"][0][1])
        self.assertEqual("next", parsed["notes"]["rows"][1][1])

    def test_parses_parentheses_and_escaped_quotes_inside_values(self):
        sql = r"INSERT INTO `items` (`id`, `name`, `amount`) VALUES (1, 'Lab (Asia) O\\'Brien', -12.50);"

        parsed = parse_insert_statements(sql)

        self.assertEqual("Lab (Asia) O'Brien", parsed["items"]["rows"][0][1])
        self.assertEqual("-12.50", parsed["items"]["rows"][0][2])

    def test_raises_when_no_insert_exists(self):
        with self.assertRaisesRegex(Exception, "No INSERT statements found"):
            parse_insert_statements("CREATE TABLE `users` (`id` int);")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 -m unittest tests.test_insert_parser -v
```

Expected: fail with `ModuleNotFoundError: No module named 'converters.insert_parser'`.

- [ ] **Step 3: Implement shared parser**

Create `converters/insert_parser.py`:

```python
"""
Shared parser for SQL INSERT statements.
"""
import re

from exceptions import SQLParsingError, ValidationError


def get_line_number(content, position):
    """Return the 1-based line number for a string position."""
    return content[:position].count("\n") + 1


def process_sql_escapes(value):
    """Process SQL escape sequences in a quoted string."""
    replacements = {
        "\\'": "'",
        '\\"': '"',
        "\\\\": "\\",
        "\\n": "\n",
        "\\r": "\r",
        "\\t": "\t",
    }

    result = value
    for escape_seq, replacement in replacements.items():
        result = result.replace(escape_seq, replacement)

    return result


def parse_insert_statements(content):
    """
    Parse SQL INSERT statements into table columns and row values.

    Returns:
        dict[str, dict[str, list]]: table name mapped to columns and rows.
    """
    statements = _extract_insert_statements(content)
    if not statements:
        if re.search(r"\bINSERT\s+INTO\b", content, re.IGNORECASE):
            match = re.search(r"\bINSERT\s+INTO\b.*", content, re.IGNORECASE | re.DOTALL)
            position = match.start() if match else 0
            raise SQLParsingError(
                "Found INSERT statements but couldn't parse them. Ensure proper MySQL format.",
                sql_snippet=content[position:position + 50],
                line_number=get_line_number(content, position),
            )

        raise SQLParsingError("No INSERT statements found in the SQL file.")

    parsed = {}

    for statement, position in statements:
        header = re.match(
            r"\s*INSERT\s+INTO\s+`?([A-Za-z0-9_]+)`?\s*\((.*?)\)\s+VALUES\s*(.*)\s*;?\s*\Z",
            statement,
            re.IGNORECASE | re.DOTALL,
        )
        if not header:
            raise SQLParsingError(
                "Found INSERT statement but couldn't parse table, columns, or values.",
                sql_snippet=statement[:80],
                line_number=get_line_number(content, position),
            )

        table_name, columns_sql, values_sql = header.groups()
        columns = [_clean_identifier(column) for column in _split_top_level(columns_sql)]
        rows = [_parse_row(row, table_name, content, position) for row in _split_rows(values_sql)]

        if table_name not in parsed:
            parsed[table_name] = {"columns": columns, "rows": []}

        parsed[table_name]["columns"] = columns
        parsed[table_name]["rows"].extend(rows)

    if not parsed:
        raise ValidationError("No valid data found in the SQL file.")

    return parsed


def _extract_insert_statements(content):
    statements = []
    pattern = re.compile(r"\bINSERT\s+INTO\b", re.IGNORECASE)
    search_position = 0

    while True:
        match = pattern.search(content, search_position)
        if not match:
            break

        end = _find_statement_end(content, match.start())
        if end == -1:
            end = len(content)

        statements.append((content[match.start():end].strip(), match.start()))
        search_position = end

    return statements


def _find_statement_end(content, start):
    quote = None
    escaped = False

    for index in range(start, len(content)):
        char = content[index]

        if escaped:
            escaped = False
            continue

        if quote:
            if char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue

        if char in ("'", '"'):
            quote = char
        elif char == ";":
            return index + 1

    return -1


def _clean_identifier(identifier):
    return identifier.strip().strip("`").strip()


def _split_top_level(text):
    parts = []
    start = 0
    quote = None
    escaped = False
    depth = 0

    for index, char in enumerate(text):
        if escaped:
            escaped = False
            continue

        if quote:
            if char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue

        if char in ("'", '"'):
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(text[start:index].strip())
            start = index + 1

    final = text[start:].strip()
    if final:
        parts.append(final)

    return parts


def _split_rows(values_sql):
    rows = []
    quote = None
    escaped = False
    depth = 0
    row_start = None

    for index, char in enumerate(values_sql):
        if escaped:
            escaped = False
            continue

        if quote:
            if char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue

        if char in ("'", '"'):
            quote = char
        elif char == "(":
            if depth == 0:
                row_start = index + 1
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0 and row_start is not None:
                rows.append(values_sql[row_start:index].strip())
                row_start = None

    return rows


def _parse_row(row_sql, table_name, content, statement_position):
    if not row_sql:
        raise SQLParsingError(
            f"Could not extract VALUES from table {table_name}",
            line_number=get_line_number(content, statement_position),
        )

    return [_parse_value_token(token) for token in _split_top_level(row_sql)]


def _parse_value_token(token):
    token = token.strip()

    if token.upper() == "NULL":
        return None

    if len(token) >= 2 and token[0] in ("'", '"') and token[-1] == token[0]:
        return process_sql_escapes(token[1:-1])

    if re.fullmatch(r"-?\d+(?:\.\d+)?", token):
        return token

    return token
```

- [ ] **Step 4: Run parser tests**

Run:

```bash
python3 -m unittest tests.test_insert_parser -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit parser**

Run:

```bash
git add converters/insert_parser.py tests/test_insert_parser.py
git commit -m "Add robust SQL insert parser"
```

---

### Task 2: Integrate PHP Converter

**Files:**
- Modify: `converters/php_converter.py`
- Test: `tests/test_php_converter.py`

- [ ] **Step 1: Write failing PHP compatibility tests**

Create `tests/test_php_converter.py`:

```python
import unittest

from converters.php_converter import format_as_php_array, parse_sql_content


class PhpConverterTest(unittest.TestCase):
    def test_parse_sql_content_preserves_rows_after_html_entity_semicolon(self):
        sql = '''
        INSERT INTO `organization` (`id`, `name`, `parent_id`, `supervisor`, `deleted_by`, `deleted_at`) VALUES
            (21, "CORPORATE ACCOUNTS SUPPORT", 2, NULL, NULL, NULL),
            (23, "CREATIVE, IT AND PROGRAMMING &amp; TRANSLATION", 2, NULL, NULL, NULL),
            (24, "E-COMMERCE", 2, NULL, NULL, NULL);
        '''

        data, table_columns = parse_sql_content(sql)

        self.assertEqual(
            ["id", "name", "parent_id", "supervisor", "deleted_by", "deleted_at"],
            table_columns["organization"],
        )
        self.assertEqual(3, len(data["organization"]))
        self.assertEqual(
            "CREATIVE, IT AND PROGRAMMING &amp; TRANSLATION",
            data["organization"][1]["name"],
        )
        self.assertEqual("E-COMMERCE", data["organization"][2]["name"])

    def test_format_as_php_array_keeps_nulls_and_numbers(self):
        data = {
            "organization": [
                {
                    "id": "23",
                    "name": "CREATIVE, IT AND PROGRAMMING &amp; TRANSLATION",
                    "parent_id": "2",
                    "deleted_at": "null",
                }
            ]
        }

        php = format_as_php_array(data)

        self.assertIn("'id' => '23'", php)
        self.assertIn("'name' => 'CREATIVE, IT AND PROGRAMMING &amp; TRANSLATION'", php)
        self.assertIn("'deleted_at' => null", php)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run PHP tests to verify current failure**

Run:

```bash
python3 -m unittest tests.test_php_converter -v
```

Expected before integration: failure because current parser returns only rows before `&amp;`.

- [ ] **Step 3: Replace duplicated PHP parser logic**

Modify `converters/php_converter.py`:

```python
from converters.insert_parser import get_line_number, parse_insert_statements, process_sql_escapes
```

Replace `parse_sql_content` body with:

```python
def parse_sql_content(content):
    """
    Parse SQL content to extract INSERT statements and convert to structured data.
    """
    parsed_tables = parse_insert_statements(content)
    result = {}
    table_columns = {}

    for table_name, table_data in parsed_tables.items():
        columns = table_data["columns"]
        table_columns[table_name] = columns
        result.setdefault(table_name, [])

        for row_idx, raw_values in enumerate(table_data["rows"]):
            processed_values = []
            for value in raw_values:
                if value is None:
                    processed_values.append("null")
                else:
                    processed_values.append(value)

            if len(processed_values) < len(columns):
                logger.warning(
                    f"Row {row_idx + 1} in table {table_name} has fewer values than columns. "
                    f"Expected {len(columns)}, got {len(processed_values)}. Filling with nulls."
                )
                processed_values.extend(["null"] * (len(columns) - len(processed_values)))

            if len(processed_values) > len(columns):
                logger.warning(
                    f"Row {row_idx + 1} in table {table_name} has more values than columns. "
                    f"Expected {len(columns)}, got {len(processed_values)}. Extra values will be ignored."
                )
                processed_values = processed_values[:len(columns)]

            result[table_name].append(dict(zip(columns, processed_values)))

    if not result:
        raise ValidationError("No valid data found in the SQL file.")

    return result, table_columns
```

Leave `format_as_php_array`, validation, and endpoint-facing functions unchanged.

- [ ] **Step 4: Run PHP and parser tests**

Run:

```bash
python3 -m unittest tests.test_insert_parser tests.test_php_converter -v
```

Expected: all tests pass.

- [ ] **Step 5: Verify provided dump through PHP parser**

Run:

```bash
python3 -c "from converters.php_converter import parse_sql_content; p='/mnt/c/Users/rolland.motimbin/Downloads/organization_2026-05-07_10-02-14.sql'; data, cols = parse_sql_content(open(p, encoding='utf-8').read()); rows = data['organization']; print(len(rows)); print(rows[20]['name']); print(rows[-1])"
```

Expected: count is greater than `20`, row index `20` is `CREATIVE, IT AND PROGRAMMING &amp; TRANSLATION`, last row prints from the end of the dump.

- [ ] **Step 6: Commit PHP integration**

Run:

```bash
git add converters/php_converter.py tests/test_php_converter.py
git commit -m "Use robust insert parser for PHP conversion"
```

---

### Task 3: Integrate Excel Converter

**Files:**
- Modify: `converters/excel_converter.py`
- Test: `tests/test_excel_converter.py`

- [ ] **Step 1: Write failing Excel compatibility tests**

Create `tests/test_excel_converter.py`:

```python
import unittest

from converters.excel_converter import parse_sql_insert_statements


class ExcelConverterTest(unittest.TestCase):
    def test_parse_sql_insert_statements_preserves_rows_after_html_entity_semicolon(self):
        sql = '''
        INSERT INTO `organization` (`id`, `name`, `parent_id`, `supervisor`, `deleted_by`, `deleted_at`) VALUES
            (21, "CORPORATE ACCOUNTS SUPPORT", 2, NULL, NULL, NULL),
            (23, "CREATIVE, IT AND PROGRAMMING &amp; TRANSLATION", 2, NULL, NULL, NULL),
            (24, "E-COMMERCE", 2, NULL, NULL, NULL);
        '''

        data = parse_sql_insert_statements(sql)

        self.assertEqual(
            ["id", "name", "parent_id", "supervisor", "deleted_by", "deleted_at"],
            data["organization"]["columns"],
        )
        self.assertEqual(3, len(data["organization"]["rows"]))
        self.assertEqual(
            "CREATIVE, IT AND PROGRAMMING &amp; TRANSLATION",
            data["organization"]["rows"][1][1],
        )
        self.assertEqual("E-COMMERCE", data["organization"]["rows"][2][1])

    def test_parse_sql_insert_statements_converts_excel_value_types(self):
        sql = "INSERT INTO `metrics` (`id`, `amount`, `deleted_at`) VALUES (7, -12.50, NULL);"

        data = parse_sql_insert_statements(sql)

        self.assertEqual(7, data["metrics"]["rows"][0][0])
        self.assertEqual(-12.50, data["metrics"]["rows"][0][1])
        self.assertIsNone(data["metrics"]["rows"][0][2])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run Excel tests to verify current failure**

Run:

```bash
python3 -m unittest tests.test_excel_converter -v
```

Expected before integration: failure because current parser returns only rows before `&amp;`.

- [ ] **Step 3: Replace duplicated Excel parser logic**

Modify `converters/excel_converter.py`:

```python
from converters.insert_parser import get_line_number, parse_insert_statements, process_sql_escapes
```

Replace `parse_sql_insert_statements` body with:

```python
def parse_sql_insert_statements(content):
    """
    Parse SQL content to extract INSERT statements and convert to structured data.
    """
    parsed_tables = parse_insert_statements(content)
    result = {}

    for table_name, table_data in parsed_tables.items():
        columns = table_data["columns"]
        result.setdefault(table_name, {"columns": columns, "rows": []})
        result[table_name]["columns"] = columns

        for row_idx, raw_values in enumerate(table_data["rows"]):
            processed_values = [_convert_excel_value(value) for value in raw_values]

            if len(processed_values) < len(columns):
                logger.warning(
                    f"Row {row_idx + 1} in table {table_name} has fewer values than columns. "
                    f"Expected {len(columns)}, got {len(processed_values)}. Filling with None."
                )
                processed_values.extend([None] * (len(columns) - len(processed_values)))

            if len(processed_values) > len(columns):
                logger.warning(
                    f"Row {row_idx + 1} in table {table_name} has more values than columns. "
                    f"Expected {len(columns)}, got {len(processed_values)}. Extra values will be ignored."
                )
                processed_values = processed_values[:len(columns)]

            result[table_name]["rows"].append(processed_values)

    if not result:
        raise ValidationError("No valid data found in the SQL file.")

    return result
```

Add this helper below `parse_sql_insert_statements`:

```python
def _convert_excel_value(value):
    if value is None:
        return None

    if isinstance(value, str) and re.fullmatch(r"-?\d+", value):
        return int(value)

    if isinstance(value, str) and re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)

    return value
```

Leave workbook creation, validation, analysis, and endpoint-facing functions unchanged.

- [ ] **Step 4: Run full unittest suite**

Run:

```bash
python3 -m unittest discover -v
```

Expected: all tests pass.

- [ ] **Step 5: Verify provided dump through Excel parser**

Run:

```bash
python3 -c "from converters.excel_converter import parse_sql_insert_statements; p='/mnt/c/Users/rolland.motimbin/Downloads/organization_2026-05-07_10-02-14.sql'; data = parse_sql_insert_statements(open(p, encoding='utf-8').read()); rows = data['organization']['rows']; print(len(rows)); print(rows[20][1]); print(rows[-1])"
```

Expected: count is greater than `20`, row index `20` is `CREATIVE, IT AND PROGRAMMING &amp; TRANSLATION`, last row prints from the end of the dump.

- [ ] **Step 6: Commit Excel integration**

Run:

```bash
git add converters/excel_converter.py tests/test_excel_converter.py
git commit -m "Use robust insert parser for Excel conversion"
```

---

### Task 4: Final Verification

**Files:**
- No source changes expected.

- [ ] **Step 1: Run all tests**

Run:

```bash
python3 -m unittest discover -v
```

Expected: all tests pass.

- [ ] **Step 2: Inspect parser output on provided dump**

Run:

```bash
python3 -c "from converters.php_converter import parse_sql_content; p='/mnt/c/Users/rolland.motimbin/Downloads/organization_2026-05-07_10-02-14.sql'; data, _ = parse_sql_content(open(p, encoding='utf-8').read()); print(len(data['organization'])); print(data['organization'][20]['name']); print(data['organization'][-1]['name'])"
```

Expected: output confirms more than `20` rows, row `23` name preserved, and final organization name present.

- [ ] **Step 3: Check git status**

Run:

```bash
git status --short
```

Expected: clean working tree after task commits, or only intentional uncommitted plan-file changes if the plan was not committed before execution.

---

## Self-Review

- Spec coverage: parser fixes semicolon, comma, entity, parentheses, quote, NULL, numeric, PHP, Excel, and provided dump checks.
- Placeholder scan: no placeholders or vague implementation steps.
- Type consistency: shared parser returns `dict[table]["columns"]` and `dict[table]["rows"]`; PHP maps rows to dicts, Excel keeps rows as lists.
