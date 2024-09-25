import re
import os
import tempfile
import zipfile
import io
import json

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

app = FastAPI()
# Mount a static directory for CSS
app.mount("/static", StaticFiles(directory="static"), name="static")

def parse_sql_content(content):
    # Extract INSERT statements
    insert_pattern = r"INSERT INTO `(\w+)` \((.*?)\) VALUES\s*([\s\S]*?)(?:;|\Z)"
    matches = re.findall(insert_pattern, content, re.DOTALL)
    
    result = {}
    for match in matches:
        table_name = match[0]
        columns = [col.strip().strip('`') for col in match[1].split(',')]
        values_block = match[2]
        
        if table_name not in result:
            result[table_name] = []
        
        # Extract individual rows
        row_pattern = r"\((.*?)\)"
        rows = re.findall(row_pattern, values_block)
        
        for row in rows:
            values = re.findall(r'"((?:\\.|[^"\\])*)"|\b(NULL)\b|(-?\d+(?:\.\d+)?)|\'((?:\\.|[^\'\\])*)\'', row)
            # Process values
            processed_values = []
            for v in values:
                if v[1] == 'NULL':
                    processed_values.append(None)
                elif v[2]:  # This is a numeric value
                    processed_values.append(float(v[2]) if '.' in v[2] else int(v[2]))
                elif v[0] or v[3]:  # This is a string value
                    value = v[0] or v[3]
                    try:
                        # Try to parse as JSON if it looks like JSON
                        if value.startswith('{') and value.endswith('}'):
                            processed_values.append(json.loads(value))
                        else:
                            processed_values.append(value)
                    except json.JSONDecodeError:
                        processed_values.append(value)
                else:
                    processed_values.append(None)
            
            # Create a dictionary for this row
            row_dict = dict(zip(columns, processed_values))
            result[table_name].append(row_dict)

    return result

def format_as_php_array(data):
    output = []
    for table, rows in data.items():
        output.append(f"${table} = [")
        for row in rows:
            row_str = "    ["
            row_items = []
            for k, v in row.items():
                if v is None:
                    row_items.append(f"'{k}' => null")
                elif isinstance(v, (int, float)):
                    row_items.append(f"'{k}' => {v}")  # No quotes for numeric values
                elif isinstance(v, dict):
                    json_str = json.dumps(v, ensure_ascii=False).replace('"', '\\"')
                    row_items.append(f"'{k}' => json_decode('{json_str}', true)")
                elif isinstance(v, str):
                    v = v.replace("'", "\\'")  # Escape single quotes
                    row_items.append(f"'{k}' => '{v}'")
                else:
                    row_items.append(f"'{k}' => {v}")
            row_str += ", ".join(row_items)
            row_str += "],"
            output.append(row_str)
        output.append("];")
        output.append("")  # Add an empty line between tables
    return "\n".join(output)

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

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SQL Converter</title>
        <link rel="stylesheet" href="/static/styles.css">
    </head>
    <body>
        <div class="container">
            <h1>SQL Converter</h1>
            <div class="tab">
                <button class="tablinks" onclick="openTab(event, 'PHPArray')" id="defaultOpen">PHP Array</button>
                <button class="tablinks" onclick="openTab(event, 'LaravelMigration')">Laravel Migration</button>
            </div>

            <div id="PHPArray" class="tabcontent">
                <h2>SQL to PHP Array Converter</h2>
                <form action="/convert/php" method="post" enctype="multipart/form-data">
                    <input type="file" name="file" accept=".sql">
                    <input type="submit" value="Convert to PHP Array">
                </form>
            </div>

            <div id="LaravelMigration" class="tabcontent">
                <h2>SQL to Laravel Migration Converter</h2>
                <form action="/convert/laravel" method="post" enctype="multipart/form-data">
                    <input type="file" name="file" accept=".sql">
                    <input type="submit" value="Convert to Laravel Migration">
                </form>
            </div>
        </div>

        <script>
        function openTab(evt, tabName) {
            var i, tabcontent, tablinks;
            tabcontent = document.getElementsByClassName("tabcontent");
            for (i = 0; i < tabcontent.length; i++) {
                tabcontent[i].style.display = "none";
            }
            tablinks = document.getElementsByClassName("tablinks");
            for (i = 0; i < tablinks.length; i++) {
                tablinks[i].className = tablinks[i].className.replace(" active", "");
            }
            document.getElementById(tabName).style.display = "block";
            evt.currentTarget.className += " active";
        }

        // Get the element with id="defaultOpen" and click on it
        document.getElementById("defaultOpen").click();
        </script>
    </body>
    </html>
    """

@app.post("/convert/php")
async def convert_sql_to_php_array(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.endswith('.sql'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an SQL file.")
    
    content = await file.read()
    content = content.decode('utf-8')
    
    try:
        result = parse_sql_content(content)
        php_array = format_as_php_array(result)
        
        # Generate the output filename
        base_name = os.path.splitext(file.filename)[0]
        output_filename = f"{base_name}_converted.php"
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.php') as temp_file:
            temp_file.write("<?php\n\n")
            temp_file.write(php_array)
            temp_file.write("\n?>")
            temp_path = temp_file.name

        # Add the cleanup task to background tasks
        background_tasks.add_task(os.unlink, temp_path)

        # Return the file as a download
        return FileResponse(
            path=temp_path, 
            filename=output_filename, 
            media_type='application/php'
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.post("/convert/laravel")
async def convert_sql_to_laravel_migration(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.endswith('.sql'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an SQL file.")
    
    content = await file.read()
    content = content.decode('utf-8')
    
    try:
        tables = parse_sql_file_for_migration(content)
        
        # Create an in-memory zip file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
            for table_name, columns_sql, engine in tables:
                columns = [parse_column_definition(col) for col in columns_sql.strip().split('\n') if parse_column_definition(col)]
                migration_content = generate_migration_content(table_name, columns, engine)
                
                # Generate a filename
                filename = f"create_{table_name}_table.php"
                
                # Write the file to the zip
                zip_file.writestr(filename, migration_content)
        
        # Seek to the beginning of the buffer
        zip_buffer.seek(0)
        
        # Create a temporary file to store the zip
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_zip:
            temp_zip.write(zip_buffer.getvalue())
            temp_zip_path = temp_zip.name

        # Add the cleanup task to background tasks
        background_tasks.add_task(os.unlink, temp_zip_path)

        # Return the zip file as a download
        return FileResponse(
            path=temp_zip_path,
            filename="laravel_migrations.zip",
            media_type='application/zip'
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)