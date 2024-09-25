# app/routers/converter.py

import os
import tempfile
import io
import zipfile
import logging
from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from app.services import sql_parser, php_formatter, migration_generator
from app.utils import file_handlers
from app.config import settings
from app.exceptions import FileTooLargeException, InvalidFileTypeException

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/", response_class=HTMLResponse)
async def home():
    return file_handlers.read_html_template("index.html")

@router.post("/convert/php")
async def convert_sql_to_php_array(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.endswith(tuple(settings.ALLOWED_EXTENSIONS)):
        raise InvalidFileTypeException()
    
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise FileTooLargeException()
    
    content = content.decode('utf-8')
    
    try:
        result = sql_parser.parse_sql_content(content)
        php_array = php_formatter.format_as_php_array(result)
        
        base_name = os.path.splitext(file.filename)[0]
        output_filename = f"{base_name}_{settings.DEFAULT_PHP_FILENAME}"
        
        temp_path = file_handlers.create_temp_file(f"<?php\n\n{php_array}\n?>", '.php')

        background_tasks.add_task(os.unlink, temp_path)

        return FileResponse(
            path=temp_path, 
            filename=output_filename, 
            media_type='application/php'
        )

    except Exception as e:
        logger.error(f"Error processing file {file.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@router.post("/convert/laravel")
async def convert_sql_to_laravel_migration(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.endswith(tuple(settings.ALLOWED_EXTENSIONS)):
        raise InvalidFileTypeException()
    
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise FileTooLargeException()
    
    content = content.decode('utf-8')
    
    try:
        tables = sql_parser.parse_sql_file_for_migration(content)
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
            for table_name, columns_sql, engine in tables:
                columns = [sql_parser.parse_column_definition(col) for col in columns_sql.strip().split('\n') if sql_parser.parse_column_definition(col)]
                migration_content = migration_generator.generate_migration_content(table_name, columns, engine)
                
                filename = f"create_{table_name}_table.php"
                zip_file.writestr(filename, migration_content)
        
        zip_buffer.seek(0)
        
        temp_zip_path = file_handlers.create_temp_file(zip_buffer.getvalue(), '.zip')

        background_tasks.add_task(os.unlink, temp_zip_path)

        return FileResponse(
            path=temp_zip_path,
            filename=settings.DEFAULT_MIGRATION_FILENAME,
            media_type='application/zip'
        )

    except Exception as e:
        logger.error(f"Error processing file {file.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")