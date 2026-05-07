"""
Module for converting SQL INSERT statements to Excel files.
"""
import re
import io
import logging
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from exceptions import SQLParsingError, ValidationError, ConversionError, FileError
from converters.insert_parser import (
    get_line_number,
    parse_insert_statements,
    process_sql_escapes,
)

# Configure logging
logger = logging.getLogger(__name__)

def parse_sql_insert_statements(content):
    """
    Parse SQL content to extract INSERT statements and convert to structured data.
    
    Args:
        content (str): SQL content with INSERT statements
        
    Returns:
        dict: Dictionary with table names as keys and lists of row dictionaries as values
        
    Raises:
        SQLParsingError: If SQL parsing fails
    """
    parsed_tables = parse_insert_statements(content)
    result = {}

    for table_name, table_data in parsed_tables.items():
        columns = table_data["columns"]
        result.setdefault(table_name, {"columns": columns, "rows": []})
        result[table_name]["columns"] = columns

        for row_idx, raw_values in enumerate(table_data["rows"]):
            processed_values = [_convert_excel_value(value) for value in raw_values]

            if len(processed_values) < len(columns):
                logger.warning(
                    f"Row {row_idx+1} in table {table_name} has fewer values than columns. "
                    f"Expected {len(columns)}, got {len(processed_values)}. Filling with None."
                )
                processed_values.extend([None] * (len(columns) - len(processed_values)))

            if len(processed_values) > len(columns):
                logger.warning(
                    f"Row {row_idx+1} in table {table_name} has more values than columns. "
                    f"Expected {len(columns)}, got {len(processed_values)}. Extra values will be ignored."
                )
                processed_values = processed_values[:len(columns)]

            result[table_name]["rows"].append(processed_values)

    if not result:
        raise ValidationError("No valid data found in the SQL file.")

    return result

def _convert_excel_value(value):
    if value is None:
        return None

    if isinstance(value, str) and re.fullmatch(r"-?\d+", value):
        return int(value)

    if isinstance(value, str) and re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)

    return value

def create_excel_workbook(parsed_data, table_filters=None):
    """
    Create an Excel workbook from parsed SQL data.
    
    Args:
        parsed_data (dict): Dictionary with table data
        table_filters (dict, optional): Dictionary of tables and column filters
        
    Returns:
        openpyxl.Workbook: Excel workbook object
        
    Raises:
        ConversionError: If Excel creation fails
    """
    try:
        # Create a new workbook
        workbook = openpyxl.Workbook()
        
        # Remove default sheet
        default_sheet = workbook.active
        workbook.remove(default_sheet)
        
        # Define styles
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="3F51B5", end_color="3F51B5", fill_type="solid")
        header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        
        # Define borders
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # Create sheets for each table
        for table_name, table_data in parsed_data.items():
            # Skip tables not in the filter if filter is provided
            if table_filters and table_name not in table_filters:
                continue
                
            # Create a sheet for this table (limit to 31 chars, Excel sheet name limit)
            sheet = workbook.create_sheet(title=table_name[:31])
            
            # Get columns and rows
            columns = table_data['columns']
            rows = table_data['rows']
            
            # Apply column filtering if specified
            if table_filters and table_name in table_filters:
                # Get the indices of columns to include
                included_columns = table_filters[table_name]
                
                # Filter columns
                column_indices = [i for i, col in enumerate(columns) if col in included_columns]
                
                # Create new filtered columns list
                filtered_columns = [columns[i] for i in column_indices]
                
                # Create new filtered rows
                filtered_rows = []
                for row in rows:
                    filtered_row = [row[i] for i in column_indices]
                    filtered_rows.append(filtered_row)
                    
                # Replace original columns and rows
                columns = filtered_columns
                rows = filtered_rows
            
            # Add header row
            for col_idx, column in enumerate(columns, start=1):
                cell = sheet.cell(row=1, column=col_idx, value=column)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_alignment
                cell.border = thin_border
                
                # Auto-size columns by setting an appropriate width
                sheet.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = max(len(column) + 2, 12)
            
            # Add data rows
            for row_idx, row_data in enumerate(rows, start=2):
                for col_idx, cell_value in enumerate(row_data, start=1):
                    cell = sheet.cell(row=row_idx, column=col_idx, value=cell_value)
                    cell.border = thin_border
                    
                    # If it's a long string, enable text wrapping
                    if isinstance(cell_value, str) and len(cell_value) > 50:
                        cell.alignment = Alignment(wrap_text=True)
            
            # Freeze the header row
            sheet.freeze_panes = "A2"
            
            # Apply auto-filter to the header row
            sheet.auto_filter.ref = sheet.dimensions
        
        return workbook
    except Exception as e:
        logger.error(f"Error creating Excel workbook: {str(e)}", exc_info=True)
        raise ConversionError(f"Failed to create Excel file: {str(e)}", converter_type="Excel")

async def validate_sql_file(file):
    """
    Validate that the uploaded file is a valid SQL file.
    
    Args:
        file: UploadFile object
        
    Returns:
        bool: True if file is valid
        
    Raises:
        ValidationError: If file validation fails
    """
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

async def analyze_sql_file_for_excel(file):
    """
    Analyze SQL file and return table names and columns for Excel export.
    
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
        
        parsed_data = parse_sql_insert_statements(content)
        
        # Create dictionary of tables and columns
        table_columns = {}
        for table_name, table_data in parsed_data.items():
            table_columns[table_name] = table_data['columns']
            
        return table_columns
    except UnicodeDecodeError:
        raise ValidationError("The SQL file contains invalid characters. Please ensure it's a valid UTF-8 encoded file.")
    except Exception as e:
        if isinstance(e, (ValidationError, SQLParsingError)):
            raise
        # Log the unexpected error
        logger.error(f"Unexpected error analyzing SQL file: {str(e)}", exc_info=True)
        raise SQLParsingError(f"An error occurred while analyzing the SQL file: {str(e)}")

async def convert_sql_to_excel(background_tasks, file, table_filters=None):
    """
    Convert SQL INSERT statements to Excel workbook.
    
    Args:
        background_tasks: FastAPI BackgroundTasks object
        file: UploadFile object
        table_filters (dict, optional): Dictionary of tables and column filters
        
    Returns:
        StreamingResponse: Excel file to download
        
    Raises:
        ValidationError: If file validation fails
        SQLParsingError: If SQL parsing fails
        ConversionError: If conversion fails
        FileError: If file operations fail
    """
    # Validate the file
    await validate_sql_file(file)
    
    try:
        content = await file.read()
        content = content.decode('utf-8')
        
        # Log parsing start
        logger.info(f"Starting SQL parsing for Excel conversion: {file.filename}")
        
        # Parse SQL content
        parsed_data = parse_sql_insert_statements(content)
        
        # Create Excel workbook
        workbook = create_excel_workbook(parsed_data, table_filters)
        
        # Save workbook to memory
        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)
        
        # Get base filename without extension
        base_filename = file.filename.rsplit('.', 1)[0]
        output_filename = f"{base_filename}_excel.xlsx"
        
        # Return streaming response
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={output_filename}"}
        )
    except UnicodeDecodeError:
        raise ValidationError("The SQL file contains invalid characters. Please ensure it's a valid UTF-8 encoded file.")
    except Exception as e:
        if isinstance(e, (ValidationError, SQLParsingError, ConversionError, FileError)):
            raise
        # Log the unexpected error
        logger.error(f"Unexpected error converting SQL to Excel: {str(e)}", exc_info=True)
        raise ConversionError(f"An error occurred during conversion: {str(e)}", converter_type="Excel")
