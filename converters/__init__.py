"""
Converters package for SQL Converter application.
"""

# Import main converter functions for easy access
from .php_converter import (
    convert_sql_to_php_array,
    analyze_sql_file,
    parse_sql_content,
    format_as_php_array,
)

from .laravel_converter import (
    convert_sql_to_laravel_migration,
    parse_sql_file_for_migration,
    generate_migration_content,
)

# Import SQL dialect utilities
from .sql_dialect import SQLDialect

# Package information
__all__ = [
    'convert_sql_to_php_array',
    'analyze_sql_file',
    'convert_sql_to_laravel_migration',
    'SQLDialect',
]