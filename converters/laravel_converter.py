import re
import io
import zipfile
from fastapi import HTTPException
from utils.file_utils import create_temp_zip, cleanup_temp_file
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse

def parse_sql_file_for_migration(content):
    # Extract CREATE TABLE statements
    create_table_pattern = r"CREATE TABLE `(\w+)` \(([\s\S]*?)\) ENGINE=(\w+).*?;"
    matches = re.findall(create_table_pattern, content, re.DOTALL)
    return matches

def parse_column_definition(column_def):
    # Parse individual column definitions
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

def type_mapping(sql_type):
    # Map SQL types to Laravel column types
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

def generate_migration_content(table_name, columns, engine):
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

async def convert_sql_to_laravel_migration(background_tasks, file):
    if not file.filename.endswith('.sql'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an SQL file.")
    
    content = await file.read()
    content = content.decode('utf-8')
    
    try:
        tables = parse_sql_file_for_migration(content)
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
            for table_name, columns_sql, engine in tables:
                columns = [parse_column_definition(col) for col in columns_sql.strip().split('\n') if parse_column_definition(col)]
                migration_content = generate_migration_content(table_name, columns, engine)
                filename = f"create_{table_name}_table.php"
                zip_file.writestr(filename, migration_content)
        
        temp_zip_path = create_temp_zip(zip_buffer)
        background_tasks.add_task(cleanup_temp_file, temp_zip_path)

        return FileResponse(
            path=temp_zip_path,
            filename="laravel_migrations.zip",
            media_type='application/zip'
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")