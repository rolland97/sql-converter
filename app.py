"""
SQL Converter FastAPI Application
"""
from fastapi import FastAPI, File, UploadFile, BackgroundTasks, Form, Request, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

# Import converters
from converters.php_converter import convert_sql_to_php_array, analyze_sql_file
from converters.laravel_converter import convert_sql_to_laravel_migration
from exceptions import SQLConverterError, ValidationError, SQLParsingError, FileError, ConversionError

import json
import tempfile
import os
import logging
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="SQL Converter",
    description="Converts SQL dumps to PHP arrays and Laravel migrations",
    version="1.0.0",
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Custom exception handlers
@app.exception_handler(SQLConverterError)
async def sql_converter_exception_handler(request: Request, exc: SQLConverterError):
    """Handle custom SQL Converter exceptions."""
    logger.error(f"SQL Converter error: {exc.message}")
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "error_message": exc.message
        },
        status_code=exc.status_code
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions."""
    logger.error(f"HTTP error {exc.status_code}: {exc.detail}")
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "error_message": exc.detail
        },
        status_code=exc.status_code
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors."""
    logger.error(f"Validation error: {str(exc)}")
    error_detail = "Invalid request parameters. Please check your inputs and try again."
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "error_message": error_detail
        },
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle any uncaught exceptions."""
    logger.error(f"Uncaught exception: {str(exc)}", exc_info=True)
    error_message = "An unexpected error occurred. Please try again later."
    
    # In development mode, show more details
    import os
    if os.getenv("DEBUG", "false").lower() == "true":
        error_message = f"{str(exc)}\n\n{traceback.format_exc()}"
    
    return templates.TemplateResponse(
        "error.html",
        {
            "request": request,
            "error_message": error_message
        },
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the home page."""
    logger.info("Serving home page")
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/analyze/php")
async def analyze_php(request: Request, file: UploadFile = File(...)):
    """
    Analyze SQL file and redirect to column selection page.
    
    Args:
        request: FastAPI Request object
        file: Uploaded SQL file
        
    Returns:
        HTMLResponse: Column selection page
    """
    logger.info(f"Analyzing SQL file: {file.filename}")
    
    try:
        # Analyze SQL file and get table columns
        table_columns = await analyze_sql_file(file)
        
        # Create a temporary file to store the table_columns data
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json', mode='w') as temp_file:
            json.dump(table_columns, temp_file)
            temp_path = temp_file.name
        
        # Store the file content in a temp storage
        temp_content_path = tempfile.NamedTemporaryFile(delete=False, suffix='.sql').name
        file.file.seek(0)  # Rewind the file
        content = await file.read()
        with open(temp_content_path, 'wb') as f:
            f.write(content)
        
        logger.info(f"SQL analysis complete for {file.filename}. Found {len(table_columns)} tables.")
        
        # Redirect to the column selection page
        return templates.TemplateResponse(
            "column_select.html", 
            {
                "request": request,
                "table_columns": table_columns,
                "temp_path": temp_path,
                "temp_content_path": temp_content_path,
                "filename": file.filename
            }
        )
    except Exception as e:
        # Delete temp files if they were created
        for path_var in ['temp_path', 'temp_content_path']:
            if path_var in locals() and os.path.exists(locals()[path_var]):
                try:
                    os.unlink(locals()[path_var])
                except Exception:
                    pass
        
        # Re-raise exception for the exception handler
        raise

@app.post("/convert/php")
async def php_converter(
    background_tasks: BackgroundTasks, 
    request: Request,
    file: UploadFile = File(None),
    temp_path: str = Form(None),
    temp_content_path: str = Form(None),
    filename: str = Form(None)
):
    """
    Convert SQL to PHP array.
    
    Args:
        background_tasks: FastAPI BackgroundTasks object
        request: FastAPI Request object
        file: Uploaded SQL file (direct conversion)
        temp_path: Path to temporary JSON file with table_columns data (from column selection)
        temp_content_path: Path to temporary SQL file (from column selection)
        filename: Original filename (from column selection)
        
    Returns:
        FileResponse: PHP file to download
    """
    # If we have form data with selected columns (from column selection page)
    if temp_path and temp_content_path:
        logger.info(f"Converting SQL with column selection. Original file: {filename}")
        
        try:
            # Check if temp files exist
            for path, desc in [(temp_path, "column data"), (temp_content_path, "SQL content")]:
                if not os.path.exists(path):
                    logger.error(f"Temp file not found: {path}")
                    raise ValidationError(f"Session expired. Please restart the column selection process. (Missing {desc})")
            
            # Get selected columns from form data
            form_data = await request.form()
            selected_columns = {}
            renamed_columns = {}
            
            # Load the table columns from the temporary file
            with open(temp_path, 'r') as f:
                table_columns = json.load(f)
            
            # Process selected columns and renamed columns from form data
            for table, columns in table_columns.items():
                selected_for_table = []
                renamed_for_table = {}
                
                for column in columns:
                    checkbox_name = f"{table}_{column}"
                    rename_name = f"{table}_{column}_rename"
                    
                    # Check if the column is selected (checkbox is checked)
                    # Form data will only contain the checkbox if it's checked
                    if checkbox_name in form_data:
                        selected_for_table.append(column)
                        
                        # Check if the column is renamed
                        if rename_name in form_data and form_data[rename_name].strip():
                            renamed_for_table[column] = form_data[rename_name].strip()
                
                if selected_for_table:  # Only add if at least one column is selected
                    selected_columns[table] = selected_for_table
                
                if renamed_for_table:  # Only add if at least one column is renamed
                    renamed_columns[table] = renamed_for_table
            
            # Create a synthetic UploadFile
            synthetic_file = UploadFile(
                filename=filename,
                file=open(temp_content_path, 'rb')
            )
            
            # Convert with selected columns and renamed columns
            result = await convert_sql_to_php_array(background_tasks, synthetic_file, selected_columns, renamed_columns)
            
            # Clean up temp files after processing is complete
            try:
                background_tasks.add_task(os.unlink, temp_path)
                background_tasks.add_task(os.unlink, temp_content_path)
            except Exception as e:
                # Log but don't fail on cleanup errors
                logger.warning(f"Failed to clean up temp files: {str(e)}")
                
            return result
            
        except Exception as e:
            # Clean up temp files if there was an error
            for path in [temp_path, temp_content_path]:
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                    except Exception:
                        pass
            
            # Re-raise for the exception handler
            raise
    else:
        # Regular direct conversion (no column selection)
        logger.info(f"Direct SQL to PHP conversion for file: {file.filename}")
        return await convert_sql_to_php_array(background_tasks, file)

@app.post("/convert/laravel")
async def laravel_converter(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    Convert SQL to Laravel migration.
    
    Args:
        background_tasks: FastAPI BackgroundTasks object
        file: Uploaded SQL file
        
    Returns:
        FileResponse: ZIP file with Laravel migrations
    """
    logger.info(f"Converting SQL to Laravel migration: {file.filename}")
    return await convert_sql_to_laravel_migration(background_tasks, file)