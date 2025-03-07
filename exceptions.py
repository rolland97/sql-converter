"""
Custom exceptions for the SQL Converter application.
"""

class SQLConverterError(Exception):
    """Base exception for all SQL Converter errors."""
    def __init__(self, message, status_code=500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class SQLParsingError(SQLConverterError):
    """Raised when SQL parsing fails."""
    def __init__(self, message, sql_snippet=None, line_number=None):
        self.sql_snippet = sql_snippet
        self.line_number = line_number
        detail = message
        if line_number:
            detail += f" (at line {line_number})"
        if sql_snippet:
            detail += f"\nProblematic SQL: {sql_snippet}"
        super().__init__(detail, status_code=400)

class ValidationError(SQLConverterError):
    """Raised when input validation fails."""
    def __init__(self, message):
        super().__init__(message, status_code=400)

class FileError(SQLConverterError):
    """Raised when file operations fail."""
    def __init__(self, message, operation=None):
        detail = message
        if operation:
            detail = f"{operation} operation failed: {message}"
        super().__init__(detail, status_code=500)

class ConversionError(SQLConverterError):
    """Raised when the conversion process fails."""
    def __init__(self, message, converter_type=None):
        detail = message
        if converter_type:
            detail = f"{converter_type} conversion failed: {message}"
        super().__init__(detail, status_code=500)