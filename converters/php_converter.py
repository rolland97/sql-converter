"""
Module for converting SQL INSERT statements to PHP arrays.
"""
from utils.file_utils import create_temp_file, cleanup_temp_file
from fastapi.responses import FileResponse
from exceptions import SQLParsingError, ValidationError, ConversionError, FileError
from converters.insert_parser import (
    get_line_number,
    parse_insert_statements,
    process_sql_escapes,
)
import logging

# Configure logging
logger = logging.getLogger(__name__)

def parse_sql_content(content):
    """
    Parse SQL content to extract INSERT statements and convert to structured data.
    
    Args:
        content (str): SQL content with INSERT statements
        
    Returns:
        tuple: (data_dict, table_columns) where data_dict is a dictionary of tables and their rows,
               and table_columns is a dictionary of tables and their column names
               
    Raises:
        SQLParsingError: If SQL parsing fails
    """
    parsed_tables = parse_insert_statements(content)
    result = {}
    table_columns = {}

    for table_name, table_data in parsed_tables.items():
        columns = table_data["columns"]
        table_columns[table_name] = columns
        result.setdefault(table_name, [])

        for row_idx, raw_values in enumerate(table_data["rows"]):
            processed_values = [
                "null" if value is None else value
                for value in raw_values
            ]

            if len(processed_values) < len(columns):
                logger.warning(
                    f"Row {row_idx+1} in table {table_name} has fewer values than columns. "
                    f"Expected {len(columns)}, got {len(processed_values)}. Filling with nulls."
                )
                processed_values.extend(["null"] * (len(columns) - len(processed_values)))

            if len(processed_values) > len(columns):
                logger.warning(
                    f"Row {row_idx+1} in table {table_name} has more values than columns. "
                    f"Expected {len(columns)}, got {len(processed_values)}. Extra values will be ignored."
                )
                processed_values = processed_values[:len(columns)]

            result[table_name].append(
                dict(zip(columns, processed_values))
            )

    if not result:
        raise ValidationError("No valid data found in the SQL file.")

    return result, table_columns

def format_as_php_array(data, selected_columns=None, renamed_columns=None):
    """
    Format the parsed data as PHP arrays.
    
    Args:
        data (dict): Dictionary of tables and their rows
        selected_columns (dict, optional): Dictionary of tables and columns to include
        renamed_columns (dict, optional): Dictionary of tables, columns and their new names
        
    Returns:
        str: PHP code representing the data as arrays
    """
    try:
        output = ["<?php", ""]  # Start with PHP tag and empty line
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
                        # Escape single quotes in string values
                        escaped_v = v.replace("'", "\\'")
                        row_items.append(f"'{k}' => '{escaped_v}'")
                    else:
                        row_items.append(f"'{k}' => {v}")
                row_str += ", ".join(row_items)
                row_str += "],"
                output.append(row_str)
            output.append("];")
            output.append("")  # Add an empty line between tables
        
        return "\n".join(output)
    except Exception as e:
        raise ConversionError(f"Failed to format PHP array: {str(e)}", converter_type="PHP")

async def validate_sql_file(file):
    """Validate that the uploaded file is a valid SQL file."""
    if not file.filename.endswith('.sql'):
        raise ValidationError("Invalid file type. Please upload an SQL file with .sql extension.")
    
    try:
        file_size = 0
        chunk_size = 8192  # Read in 8kb chunks
        
        # Check file size without reading the entire file into memory
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()  # Get position (file size)
        file.file.seek(0)  # Rewind
        
        # Set a reasonable file size limit (e.g., 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if file_size > max_size:
            raise ValidationError(f"File is too large. Maximum allowed size is {max_size // (1024 * 1024)}MB.")
        
        return True
    except Exception as e:
        if isinstance(e, ValidationError):
            raise
        raise ValidationError(f"Error validating file: {str(e)}")

async def analyze_sql_file(file):
    """
    Analyze SQL file and return table names and columns.
    
    Args:
        file: UploadFile object
        
    Returns:
        dict: Dictionary of tables and their columns
        
    Raises:
        ValidationError: If file validation fails
        SQLParsingError: If SQL parsing fails
    """
    await validate_sql_file(file)
    
    try:
        content = await file.read()
        content = content.decode('utf-8')
        
        _, table_columns = parse_sql_content(content)
        return table_columns
    except UnicodeDecodeError:
        raise ValidationError("The SQL file contains invalid characters. Please ensure it's a valid UTF-8 encoded file.")
    except Exception as e:
        if isinstance(e, (ValidationError, SQLParsingError)):
            raise
        # Log the unexpected error
        logger.error(f"Unexpected error analyzing SQL file: {str(e)}", exc_info=True)
        raise SQLParsingError(f"An error occurred while analyzing the SQL file: {str(e)}")

async def convert_sql_to_php_array(background_tasks, file, selected_columns=None, renamed_columns=None):
    """
    Convert SQL INSERT statements to PHP arrays.
    
    Args:
        background_tasks: FastAPI BackgroundTasks object
        file: UploadFile object
        selected_columns (dict, optional): Dictionary of tables and columns to include
        renamed_columns (dict, optional): Dictionary of tables, columns and their new names
        
    Returns:
        FileResponse: PHP file to download
        
    Raises:
        ValidationError: If file validation fails
        SQLParsingError: If SQL parsing fails
        ConversionError: If conversion fails
        FileError: If file operations fail
    """
    # Only validate if it's a direct file upload (not from column select)
    if hasattr(file, 'filename') and file.filename:
        await validate_sql_file(file)
    
    try:
        content = await file.read()
        content = content.decode('utf-8')
        
        # Log parsing start
        logger.info(f"Starting SQL parsing for file: {getattr(file, 'filename', 'unknown')}")
        
        # Parse SQL content
        result, _ = parse_sql_content(content)
        
        # Format as PHP array
        php_array = format_as_php_array(result, selected_columns, renamed_columns)
        
        # Create temporary file
        try:
            temp_path, output_filename = create_temp_file(
                getattr(file, 'filename', 'sql_data'), 
                php_array, 
                '.php'
            )
            background_tasks.add_task(cleanup_temp_file, temp_path)
        except Exception as e:
            raise FileError(f"Failed to create output file: {str(e)}", operation="File creation")

        return FileResponse(
            path=temp_path, 
            filename=output_filename, 
            media_type='application/php'
        )
    except UnicodeDecodeError:
        raise ValidationError("The SQL file contains invalid characters. Please ensure it's a valid UTF-8 encoded file.")
    except Exception as e:
        if isinstance(e, (ValidationError, SQLParsingError, ConversionError, FileError)):
            raise
        # Log the unexpected error
        logger.error(f"Unexpected error converting SQL to PHP: {str(e)}", exc_info=True)
        raise ConversionError(f"An error occurred during conversion: {str(e)}", converter_type="PHP")
