# app/services/sql_parser.py

import re
import json
from typing import Dict, List, Any
from app.config import settings
import logging

logger = logging.getLogger(__name__)

def parse_sql_content(content: str) -> Dict[str, List[Dict[str, Any]]]:
    insert_pattern = r"INSERT INTO `(\w+)` \((.*?)\) VALUES\s*([\s\S]*?)(?:;|\Z)"
    matches = re.findall(insert_pattern, content, re.DOTALL)
    
    result = {}
    for match in matches:
        table_name = match[0]
        columns = [col.strip().strip('`') for col in match[1].split(',')]
        values_block = match[2]
        
        if table_name not in result:
            result[table_name] = []
        
        row_pattern = r"\((.*?)\)"
        rows = re.findall(row_pattern, values_block)
        
        for row in rows[:settings.MAX_INSERT_ROWS]:
            values = re.findall(r'"((?:\\.|[^"\\])*)"|\b(NULL)\b|(-?\d+(?:\.\d+)?)|\'((?:\\.|[^\'\\])*)\'', row)
            processed_values = []
            for v in values:
                if v[1] == 'NULL':
                    processed_values.append(None)
                elif v[2]:  # Numeric value
                    processed_values.append(float(v[2]) if '.' in v[2] else int(v[2]))
                elif v[0] or v[3]:  # String value
                    value = v[0] or v[3]
                    try:
                        if value.startswith('{') and value.endswith('}'):
                            processed_values.append(json.loads(value))
                        else:
                            processed_values.append(value)
                    except json.JSONDecodeError:
                        processed_values.append(value)
                else:
                    processed_values.append(None)
            
            row_dict = dict(zip(columns, processed_values))
            result[table_name].append(row_dict)
        
        if len(rows) > settings.MAX_INSERT_ROWS:
            logger.warning(f"Table {table_name} exceeded MAX_INSERT_ROWS. Truncated to {settings.MAX_INSERT_ROWS} rows.")

    return result

def parse_sql_file_for_migration(content: str) -> List[tuple]:
    create_table_pattern = r"CREATE TABLE `(\w+)` \(([\s\S]*?)\) ENGINE=(\w+).*?;"
    return re.findall(create_table_pattern, content, re.DOTALL)

def parse_column_definition(column_def: str) -> Dict[str, Any]:
    column_pattern = r"`(\w+)`\s+([\w()]+)(?:\s+(\w+))?(?:\s+(\w+))?(?:\s+DEFAULT\s+(.*?))?(?:\s+COMMENT\s+'(.*?)')?,?"
    match = re.match(column_pattern, column_def.strip())
    
    if match:
        name, type, unsigned, nullable, default, comment = match.groups()
        return {
            'name': name,
            'type': type,
            'unsigned': unsigned == 'unsigned',
            'nullable': nullable != 'NOT NULL',
            'default': default,
            'comment': comment
        }
    return None