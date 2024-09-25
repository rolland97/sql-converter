# app/routers/converter.py

import os
import tempfile
import io
import zipfile
import logging
import datetime
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
        result, total_rows = sql_parser.parse_sql_content(content)
        php_array, large_files = php_formatter.format_as_php_array(result, total_rows)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if large_files:
            zip_filename = os.path.join('/app/temp', f"php_arrays_{timestamp}.zip")
            with zipfile.ZipFile(zip_filename, 'w') as zipf:
                main_file = file_handlers.create_temp_file(f"<?php\n\n{php_array}\n?>", '.php')
                zipf.write(main_file, os.path.basename(main_file))
                for large_file in large_files:
                    zipf.write(large_file, os.path.basename(large_file))
                    os.remove(large_file)  # Clean up individual files
            
            background_tasks.add_task(os.unlink, zip_filename)
            
            return FileResponse(
                path=zip_filename,
                filename=os.path.basename(zip_filename),
                media_type='application/zip'
            )
        else:
            # If no large files, proceed with the original method
            base_name = os.path.splitext(file.filename)[0]
            output_filename = f"{base_name}_{settings.DEFAULT_PHP_FILENAME}"
            
            temp_path = file_handlers.create_temp_file(
                content=f"<?php\n\n{php_array}\n?>",
                suffix='.php',
                prefix='php_array'
            )

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