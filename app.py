from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from starlette.requests import Request
import re
import os
import tempfile

app = FastAPI()

def parse_sql_content(content):
    # Extract INSERT statements
    insert_pattern = r"INSERT INTO `(\w+)` \((.*?)\) VALUES\s*([\s\S]*?)(?:;|\Z)"
    matches = re.findall(insert_pattern, content, re.DOTALL)
    
    result = {}
    for match in matches:
        table_name = match[0]
        columns = [col.strip('`') for col in match[1].split(',')]
        values_block = match[2]
        
        if table_name not in result:
            result[table_name] = []
        
        # Extract individual rows
        row_pattern = r"\((.*?)\)"
        rows = re.findall(row_pattern, values_block)
        
        for row in rows:
            values = re.findall(r'"([^"]*)"|\b(NULL)\b|(\d+)|\'([^\']*)\'', row)
            # Process values
            processed_values = []
            for v in values:
                if v[1] == 'NULL':
                    processed_values.append('null')  # PHP null
                elif v[0] == '' and v[1] == '' and v[2] == '' and v[3] == '':
                    processed_values.append("None")  # Python "None" for empty values
                else:
                    processed_values.append(v[0] or v[2] or v[3])  # Non-empty string or number
            
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
                if v == "None":
                    row_items.append(f"'{k}' => \"None\"")
                elif v == 'null':
                    row_items.append(f"'{k}' => null")
                elif isinstance(v, str):
                    row_items.append(f"'{k}' => '{v}'")
                else:
                    row_items.append(f"'{k}' => {v}")
            row_str += ", ".join(row_items)
            row_str += "],"
            output.append(row_str)
        output.append("];")
        output.append("")  # Add an empty line between tables
    return "\n".join(output)

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SQL to PHP Array Converter</title>
    </head>
    <body>
        <h1>SQL to PHP Array Converter</h1>
        <form action="/convert/" method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept=".sql">
            <input type="submit" value="Convert">
        </form>
    </body>
    </html>
    """

@app.post("/convert/")
async def convert_sql_to_array(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)