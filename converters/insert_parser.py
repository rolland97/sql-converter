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
        "\\\\'": "'",
        '\\\\"': '"',
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
            elif char == quote and not _is_backslash_escaped(content, index):
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
            elif char == quote and not _is_backslash_escaped(text, index):
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
            elif char == quote and not _is_backslash_escaped(values_sql, index):
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


def _is_backslash_escaped(text, index):
    return index > 0 and text[index - 1] == "\\"


def _parse_value_token(token):
    token = token.strip()

    if token.upper() == "NULL":
        return None

    if len(token) >= 2 and token[0] in ("'", '"') and token[-1] == token[0]:
        return process_sql_escapes(token[1:-1])

    if re.fullmatch(r"-?\d+(?:\.\d+)?", token):
        return token

    return token
