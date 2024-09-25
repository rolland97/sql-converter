# app/services/php_formatter.py
import os
import datetime
from typing import Dict, List, Any, Tuple
from app.config import settings

def format_as_php_array(data: Dict[str, List[Dict[str, Any]]], total_rows: Dict[str, int]) -> Tuple[str, List[str]]:
    output = []
    large_files = []
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    for table, rows in data.items():
        if total_rows[table] > settings.MAX_INSERT_ROWS:
            filename = os.path.join('/app/temp', f"{table}_data_{timestamp}.php")
            with open(filename, 'w') as f:
                f.write(f"<?php\n\n${table} = [\n")
                for row in rows:
                    row_str = format_row(row)
                    f.write(f"{settings.PHP_ARRAY_INDENT}{row_str},\n")
                f.write("];\n")
            large_files.append(filename)
            output.append(f"// Data for table '{table}' is in file '{os.path.basename(filename)}'\n")
        else:
            output.append(f"${table} = [")
            for row in rows:
                row_str = format_row(row)
                output.append(f"{settings.PHP_ARRAY_INDENT}{row_str},")
            output.append("];")
            output.append("")  # Add an empty line between tables
    return "\n".join(output), large_files

def format_row(row: Dict[str, Any]) -> str:
    row_items = []
    for k, v in row.items():
        if v is None:
            row_items.append(f"'{k}' => null")
        elif isinstance(v, (int, float)):
            row_items.append(f"'{k}' => {v}")
        elif isinstance(v, dict):
            json_str = json.dumps(v, ensure_ascii=False).replace('"', '\\"')
            row_items.append(f"'{k}' => json_decode('{json_str}', true)")
        elif isinstance(v, str):
            v = v.replace('\\', '').replace("'", "\\'")
            row_items.append(f"'{k}' => '{v}'")
        else:
            row_items.append(f"'{k}' => {v}")
    return "[" + ", ".join(row_items) + "]"