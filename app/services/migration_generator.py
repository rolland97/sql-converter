# app/services/migration_generator.py

from typing import Dict, Any, List

def type_mapping(sql_type: str) -> str:
    mapping = {
        'int': 'integer',
        'bigint': 'bigInteger',
        'varchar': 'string',
        'text': 'text',
        'timestamp': 'timestamp',
        'datetime': 'dateTime',
        'date': 'date',
        'tinyint(1)': 'boolean',
        'decimal': 'decimal',
        'enum': 'enum',
    }
    for sql, laravel in mapping.items():
        if sql in sql_type.lower():
            return laravel
    return 'string'  # Default to string if no match

def generate_migration_content(table_name: str, columns: List[Dict[str, Any]], engine: str) -> str:
    class_name = "Create" + "".join(word.capitalize() for word in table_name.split('_')) + "Table"
    
    content = f"""<?php

use Illuminate\\Database\\Migrations\\Migration;
use Illuminate\\Database\\Schema\\Blueprint;
use Illuminate\\Support\\Facades\\Schema;

return new class extends Migration
{{
    public function up(): void
    {{
        Schema::create('{table_name}', function (Blueprint $table) {{
"""
    
    for column in columns:
        column_def = f"            $table->{type_mapping(column['type'])}('{column['name']}')"
        if column['unsigned']:
            column_def += "->unsigned()"
        if column['nullable']:
            column_def += "->nullable()"
        if column['default'] is not None:
            if column['default'] == 'NULL':
                column_def += "->default(null)"
            elif column['default'] == 'CURRENT_TIMESTAMP':
                column_def += "->useCurrent()"
            else:
                column_def += f"->default('{column['default']}')"
        if column['comment']:
            column_def += f"->comment('{column['comment']}')"
        content += column_def + ";\n"
    
    content += f"""
            $table->engine = '{engine}';
        }});
    }}

    public function down(): void
    {{
        Schema::dropIfExists('{table_name}');
    }}
}};
"""
    return content