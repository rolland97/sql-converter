import re
from fastapi import HTTPException
from utils.file_utils import create_temp_file, cleanup_temp_file
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse

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

async def convert_sql_to_php_array(background_tasks, file):
    if not file.filename.endswith('.sql'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an SQL file.")
    
    content = await file.read()
    content = content.decode('utf-8')
    
    try:
        result = parse_sql_content(content)
        php_array = format_as_php_array(result)
        
        temp_path, output_filename = create_temp_file(file.filename, php_array, '.php')
        background_tasks.add_task(cleanup_temp_file, temp_path)

        return FileResponse(
            path=temp_path, 
            filename=output_filename, 
            media_type='application/php'
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")