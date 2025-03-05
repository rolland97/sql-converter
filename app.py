from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from starlette.requests import Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from converters.php_converter import convert_sql_to_php_array, analyze_sql_file
from converters.laravel_converter import convert_sql_to_laravel_migration
import json
from typing import List, Dict
import tempfile
import os

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/analyze/php")
async def analyze_php(request: Request, file: UploadFile = File(...)):
    # Analyze SQL file and get table columns
    table_columns = await analyze_sql_file(file)
    
    # Create a temporary file to store the table_columns data
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json', mode='w') as temp_file:
        json.dump(table_columns, temp_file)
        temp_path = temp_file.name
    
    # Store the file content in a session or temp storage
    temp_content_path = tempfile.NamedTemporaryFile(delete=False, suffix='.sql').name
    file.file.seek(0)  # Rewind the file
    content = await file.read()
    with open(temp_content_path, 'wb') as f:
        f.write(content)
    
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

@app.post("/convert/php")
async def php_converter(
    background_tasks: BackgroundTasks, 
    request: Request,
    file: UploadFile = File(None),
    temp_path: str = Form(None),
    temp_content_path: str = Form(None),
    filename: str = Form(None)
):
    # If we have form data with selected columns
    if temp_path and temp_content_path:
        try:
            # Get selected columns from form data
            form_data = await request.form()
            selected_columns = {}
            renamed_columns = {}
            
            # Check if temp files exist
            if not os.path.exists(temp_path) or not os.path.exists(temp_content_path):
                return templates.TemplateResponse(
                    "error.html",
                    {
                        "request": request,
                        "error_message": "Session expired. Please restart the column selection process."
                    },
                    status_code=400
                )
            
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
            except Exception:
                # Ignore cleanup errors
                pass
                
            return result
            
        except FileNotFoundError:
            return templates.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "error_message": "Session expired. Please restart the column selection process."
                },
                status_code=400
            )
        except Exception as e:
            return templates.TemplateResponse(
                "error.html",
                {
                    "request": request,
                    "error_message": f"An error occurred: {str(e)}"
                },
                status_code=500
            )
    else:
        # Regular direct conversion (no column selection)
        return await convert_sql_to_php_array(background_tasks, file)

@app.post("/convert/laravel")
async def laravel_converter(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    return await convert_sql_to_laravel_migration(background_tasks, file)