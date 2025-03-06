"""
SQL Converter - A tool to convert SQL to various formats.
"""

# Version information
__version__ = '1.0.0'

# Import custom exceptions for easy access
from .exceptions import (
    SQLConverterError,
    SQLParsingError,
    ValidationError,
    FileError,
    ConversionError
)

# Package information
__author__ = 'SQL Converter Team'
__description__ = 'Convert SQL dumps to PHP arrays and Laravel migrations'