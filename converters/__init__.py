"""
Converters package for SQL Converter application.
"""

# Import main converter functions for easy access
from .php_converter import (
    convert_sql_to_php_array,
    analyze_sql_file,
)

from .laravel_converter import (
    convert_sql_to_laravel_migration,
)

# Package information
__all__ = [
    'convert_sql_to_php_array',
    'analyze_sql_file',
    'convert_sql_to_laravel_migration',
    'SQLDialect',
]