import re
from fastapi import HTTPException
from utils.file_utils import create_temp_file, cleanup_temp_file
from fastapi.responses import FileResponse

def parse_sql_content(content):
    # Extract INSERT statements
    insert_pattern = r"INSERT INTO `(\w+)` \((.*?)\) VALUES\s*([\s\S]*?)(?:;|\Z)"
    matches = re.findall(insert_pattern, content, re.DOTALL)
    
    result = {}
    table_columns = {}  # Store columns for each table
    
    for match in matches:
        table_name = match[0]
        
        # Clean column names - strip backticks and whitespace
        columns = []
        for col in match[1].split(','):
            # Remove backticks and strip whitespace
            clean_col = col.strip().strip('`')
            columns.append(clean_col)
            
        values_block = match[2]
        
        # Store columns for the table
        table_columns[table_name] = columns
        
        if table_name not in result:
            result[table_name] = []
        
        # Extract individual rows with a more robust pattern
        # This pattern supports nested parentheses and complex strings
        row_pattern = r"\(((?:[^()]|\([^()]*\))*)\)"
        rows = re.findall(row_pattern, values_block)
        
        for row in rows:
            # Improved value parsing
            # Use a more robust regex pattern that can handle complex strings and special characters
            values_pattern = r"'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"|\b(NULL)\b|(-?\d+(?:\.\d+)?)"
            matches = re.findall(values_pattern, row, re.IGNORECASE)
            
            # Process values
            processed_values = []
            for match in matches:
                single_quote_str, double_quote_str, null_val, num_val = match
                
                if null_val.upper() == 'NULL':
                    processed_values.append('null')  # PHP null
                elif num_val:
                    processed_values.append(num_val)  # Number
                elif single_quote_str != '':
                    processed_values.append(single_quote_str)  # String in single quotes
                elif double_quote_str != '':
                    processed_values.append(double_quote_str)  # String in double quotes
                else:
                    processed_values.append("None")  # Fallback, shouldn't happen
            
            # Ensure the number of values matches the number of columns
            if len(processed_values) < len(columns):
                # If there are missing values, fill with nulls
                processed_values.extend(['null'] * (len(columns) - len(processed_values)))
            
            # Create a dictionary for this row
            row_dict = dict(zip(columns, processed_values))
            result[table_name].append(row_dict)

    return result, table_columns

def format_as_php_array(data, selected_columns=None, renamed_columns=None):
    output = []
    for table, rows in data.items():
        # Skip tables that aren't in selected_columns if we're filtering
        if selected_columns is not None and table not in selected_columns:
            continue
            
        output.append(f"${table} = [")
        for row in rows:
            row_str = "    ["
            row_items = []
            
            # If selected_columns is provided, use only those columns
            if selected_columns and table in selected_columns:
                # We'll build a filtered row with potentially renamed keys
                filtered_row = {}
                
                for orig_key in selected_columns[table]:
                    if orig_key in row:  # Ensure the key exists in the row
                        # Check if this column should be renamed
                        new_key = orig_key
                        if renamed_columns and table in renamed_columns and orig_key in renamed_columns[table]:
                            new_key = renamed_columns[table][orig_key]
                        
                        # Add to the filtered row with possibly renamed key
                        filtered_row[new_key] = row[orig_key]
            else:
                filtered_row = row
                
            for k, v in filtered_row.items():
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

async def analyze_sql_file(file):
    """Analyze SQL file and return table names and columns"""
    if not file.filename.endswith('.sql'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an SQL file.")
    
    content = await file.read()
    content = content.decode('utf-8')
    
    try:
        _, table_columns = parse_sql_content(content)
        return table_columns
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

async def convert_sql_to_php_array(background_tasks, file, selected_columns=None, renamed_columns=None):
    if not file.filename.endswith('.sql'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an SQL file.")
    
    content = await file.read()
    content = content.decode('utf-8')
    
    try:
        result, _ = parse_sql_content(content)
        php_array = format_as_php_array(result, selected_columns, renamed_columns)
        
        temp_path, output_filename = create_temp_file(file.filename, php_array, '.php')
        background_tasks.add_task(cleanup_temp_file, temp_path)

        return FileResponse(
            path=temp_path, 
            filename=output_filename, 
            media_type='application/php'
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")