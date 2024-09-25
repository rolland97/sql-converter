# app/services/php_formatter.py

import json
from typing import Dict, List, Any
from app.config import settings

def format_as_php_array(data: Dict[str, List[Dict[str, Any]]]) -> str:
    output = []
    for table, rows in data.items():
        output.append(f"${table} = [")
        for row in rows:
            row_str = f"{settings.PHP_ARRAY_INDENT}["
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
                    v = v.replace("'", "\\'")
                    row_items.append(f"'{k}' => '{v}'")
                else:
                    row_items.append(f"'{k}' => {v}")
            row_str += ", ".join(row_items)
            row_str += "],"
            output.append(row_str)
        output.append("];")
        output.append("")  # Add an empty line between tables
    return "\n".join(output)