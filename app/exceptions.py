# app/exceptions.py

from fastapi import HTTPException

class SQLConverterException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail)

class FileTooLargeException(SQLConverterException):
    def __init__(self):
        super().__init__(detail="File too large")

class InvalidFileTypeException(SQLConverterException):
    def __init__(self):
        super().__init__(detail="Invalid file type. Please upload an SQL file.")