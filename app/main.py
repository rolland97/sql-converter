# app/main.py

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from app.routers import converter
from app.config import settings
from app.exceptions import SQLConverterException
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(converter.router)

@app.exception_handler(SQLConverterException)
async def sql_converter_exception_handler(request: Request, exc: SQLConverterException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting {settings.APP_NAME}")
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)