from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from starlette.requests import Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from converters.php_converter import convert_sql_to_php_array
from converters.laravel_converter import convert_sql_to_laravel_migration

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/convert/php")
async def php_converter(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    return await convert_sql_to_php_array(background_tasks, file)

@app.post("/convert/laravel")
async def laravel_converter(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    return await convert_sql_to_laravel_migration(background_tasks, file)