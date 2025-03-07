"""
Module for converting SQL CREATE TABLE statements to Laravel migrations.
"""
import re
import io
import zipfile
import logging
from exceptions import SQLParsingError, ValidationError, ConversionError, FileError
from utils.file_utils import create_temp_zip, cleanup_temp_file
from fastapi.responses import FileResponse

# Configure logging
logger = logging.getLogger(__name__)

def get_line_number(content, position):
    """Helper function to get line number from string position."""
    return content[:position].count('\n') + 1

def parse_sql_file_for_migration(content):
    """
    Parse SQL file to extract CREATE TABLE statements.
    
    Args:
        content (str): SQL content with CREATE TABLE statements
        
    Returns:
        list: List of tuples (table_name, columns_sql, engine)
        
    Raises:
        SQLParsingError: If SQL parsing fails
    """
    # Extract CREATE TABLE statements
    create_table_pattern = r"CREATE TABLE `(\w+)` \(([\s\S]*?)\) ENGINE=(\w+).*?;"
    
    try:
        matches = re.findall(create_table_pattern, content, re.DOTALL)
        
        if not matches:
            # Try to find any CREATE TABLE statement to provide better error
            basic_create_pattern = r"CREATE TABLE.*?;"
            basic_matches = re.findall(basic_create_pattern, content, re.DOTALL)
            
            if basic_matches:
                # Found some CREATE statements but they don't match our expected format
                first_match = basic_matches[0]
                match_position = content.find(first_match)
                line_number = get_line_number(content, match_position)
                snippet = first_match[:50] + "..." if len(first_match) > 50 else first_match
                
                raise SQLParsingError(
                    "Found CREATE TABLE statements but couldn't parse them. Ensure proper MySQL format.",
                    sql_snippet=snippet,
                    line_number=line_number
                )
            else:
                # No CREATE TABLE statements found at all
                raise SQLParsingError("No CREATE TABLE statements found in the SQL file.")
        
        return matches
    except Exception as e:
        if isinstance(e, SQLParsingError):
            raise
        raise SQLParsingError(f"Failed to parse SQL: {str(e)}")

def parse_column_definition(column_def, table_name=None, line_number=None):
    """
    Parse individual column definitions from CREATE TABLE statement.
    
    Args:
        column_def (str): Column definition string
        table_name (str, optional): Table name for error context
        line_number (int, optional): Line number for error context
        
    Returns:
        dict: Column properties or None if parsing fails
        
    Raises:
        SQLParsingError: If column parsing fails
    """
    try:
        # Parse individual column definitions
        # This pattern has been improved to handle more complex column definitions
        column_pattern = r"`(\w+)`\s+([\w()]+)(?:\s+(\w+))?(?:\s+(\w+))?(?:\s+DEFAULT\s+(.*?))?(?:\s+COMMENT\s+'(.*?)')?(?:\s*,)?\s*$"
        match = re.match(column_pattern, column_def.strip())
        
        if match:
            name, type_str, unsigned, nullable, default, comment = match.groups()
            
            # Validate and clean data
            if type_str is None:
                raise SQLParsingError(f"Missing data type for column '{name}'")
                
            # Handle NULL default values
            if default and default.upper() == 'NULL':
                default = 'NULL'
                
            return {
                'name': name,
                'type': type_str,
                'unsigned': unsigned == 'unsigned',
                'nullable': nullable != 'NOT NULL',
                'default': default,
                'comment': comment
            }
        else:
            raise SQLParsingError(
                f"Failed to parse column definition: {column_def.strip()}",
                sql_snippet=column_def.strip()
            )
    except Exception as e:
        if isinstance(e, SQLParsingError):
            raise
        
        error_context = ""
        if table_name:
            error_context = f" in table '{table_name}'"
        if line_number:
            error_context += f" at line {line_number}"
            
        raise SQLParsingError(
            f"Error parsing column definition{error_context}: {str(e)}",
            sql_snippet=column_def.strip()
        )

def type_mapping(sql_type, db_engine="mysql"):
    """
    Map SQL types to Laravel column types.
    
    Args:
        sql_type (str): SQL data type
        db_engine (str): Database engine (mysql, postgres, sqlite)
        
    Returns:
        str: Equivalent Laravel column type
    """
    # Standard type mappings (shared across engines)
    standard_mapping = {
        'int': 'integer',
        'integer': 'integer',
        'bigint': 'bigInteger',
        'smallint': 'smallInteger',
        'tinyint(1)': 'boolean',
        'tinyint': 'tinyInteger',
        'varchar': 'string',
        'char': 'char',
        'text': 'text',
        'mediumtext': 'mediumText',
        'longtext': 'longText',
        'json': 'json',
        'timestamp': 'timestamp',
        'datetime': 'dateTime',
        'date': 'date',
        'time': 'time',
        'decimal': 'decimal',
        'float': 'float',
        'double': 'double',
        'enum': 'enum',
        'blob': 'binary',
        'mediumblob': 'binary',
        'longblob': 'binary'
    }
    
    # Engine-specific mappings
    postgres_mapping = {
        'serial': 'increments',
        'bigserial': 'bigIncrements',
        'uuid': 'uuid',
        'jsonb': 'jsonb',
        'timestamptz': 'timestampTz'
    }
    
    # Select the appropriate mapping based on engine
    mapping = standard_mapping
    if db_engine.lower() == "postgres":
        mapping.update(postgres_mapping)
    
    # Try to find the most specific match
    sql_type_lower = sql_type.lower()
    for sql, laravel in mapping.items():
        # Exact match or starts with (for types with parameters like varchar(255))
        if sql_type_lower == sql or sql_type_lower.startswith(sql + '('):
            return laravel
    
    # Extract size for string fields
    if 'varchar' in sql_type_lower:
        size_match = re.search(r'varchar\((\d+)\)', sql_type_lower)
        if size_match:
            return f"string"  # Laravel automatically handles string length
    
    # Default to string if no match
    logger.warning(f"Unknown SQL type: {sql_type}, defaulting to string")
    return 'string'

def extract_field_size(sql_type):
    """
    Extract size parameter from SQL type definition.
    
    Args:
        sql_type (str): SQL data type with possible size parameter
        
    Returns:
        int or None: Size parameter if found, None otherwise
    """
    size_match = re.search(r'\((\d+)(?:,\s*(\d+))?\)', sql_type)
    if size_match:
        # If there are two numbers (like decimal(8,2)), return both
        if size_match.group(2):
            return int(size_match.group(1)), int(size_match.group(2))
        # Otherwise return just the single number
        return int(size_match.group(1))
    return None

def generate_migration_content(table_name, columns, engine):
    """
    Generate Laravel migration content for a table.
    
    Args:
        table_name (str): Name of the table
        columns (list): List of column definition dictionaries
        engine (str): Database engine
        
    Returns:
        str: PHP code for Laravel migration
        
    Raises:
        ConversionError: If migration generation fails
    """
    try:
        # Convert table_name to StudlyCase for class name
        class_name = "Create" + "".join(word.capitalize() for word in table_name.split('_')) + "Table"
        
        # Start building migration content
        content = [
            "<?php",
            "",
            "use Illuminate\\Database\\Migrations\\Migration;",
            "use Illuminate\\Database\\Schema\\Blueprint;",
            "use Illuminate\\Support\\Facades\\Schema;",
            "",
            f"return new class extends Migration",
            "{",
            "    public function up(): void",
            "    {",
            f"        Schema::create('{table_name}', function (Blueprint $table) {{",
        ]
        
        # Process primary keys and indices
        primary_keys = []
        foreign_keys = []
        indices = []
        
        # Process columns
        for column in columns:
            # Skip if this isn't a real column (e.g., it's a KEY definition)
            if not column or 'name' not in column:
                continue
                
            # Get Laravel column type
            laravel_type = type_mapping(column['type'])
            
            # Start building column definition
            column_def = f"            $table->{laravel_type}('{column['name']}')"
            
            # Extract size if applicable
            size = extract_field_size(column['type'])
            if size is not None:
                if isinstance(size, tuple):
                    # Handle decimal with precision and scale
                    column_def = f"            $table->{laravel_type}('{column['name']}', {size[0]}, {size[1]})"
                elif laravel_type in ['string', 'char']:
                    # Only add size for string/char types
                    column_def = f"            $table->{laravel_type}('{column['name']}', {size})"
                    
            # Add modifiers
            if column['unsigned']:
                column_def += "->unsigned()"
                
            if column['nullable']:
                column_def += "->nullable()"
                
            if column['default'] is not None:
                if column['default'] == 'NULL':
                    column_def += "->default(null)"
                elif column['default'] == 'CURRENT_TIMESTAMP':
                    column_def += "->useCurrent()"
                elif laravel_type == 'boolean':
                    bool_value = '1' in column['default'] or 'true' in column['default'].lower()
                    column_def += f"->default({str(bool_value).lower()})"
                else:
                    # Clean the default value
                    default_val = column['default'].strip("'\"")
                    column_def += f"->default('{default_val}')"
                    
            if column['comment']:
                # Escape single quotes in comment
                escaped_comment = column['comment'].replace("'", "\\'")
                column_def += f"->comment('{escaped_comment}')"
                
            # Add the column definition to the content
            content.append(column_def + ";")
        
        # Add primary keys, indices, etc. if we extracted them
        for pk in primary_keys:
            content.append(f"            $table->primary(['{pk}']);")
            
        for fk in foreign_keys:
            content.append(f"            $table->foreign('{fk['column']}')->references('{fk['references']}')->on('{fk['on']}');")
            
        for idx in indices:
            if idx['unique']:
                content.append(f"            $table->unique(['{idx['column']}']);")
            else:
                content.append(f"            $table->index(['{idx['column']}']);")
        
        # Add engine if specified
        if engine:
            content.append(f"            $table->engine = '{engine}';")
        
        # Close up the migration
        content.extend([
            "        });",
            "    }",
            "",
            "    public function down(): void",
            "    {",
            f"        Schema::dropIfExists('{table_name}');",
            "    }",
            "};"
        ])
        
        return "\n".join(content)
    except Exception as e:
        raise ConversionError(f"Failed to generate migration for table '{table_name}': {str(e)}", converter_type="Laravel")

async def validate_sql_file(file):
    """
    Validate that the uploaded file is a valid SQL file.
    
    Args:
        file: UploadFile object
        
    Returns:
        bool: True if file is valid
        
    Raises:
        ValidationError: If file validation fails
    """
    if not file.filename.endswith('.sql'):
        raise ValidationError("Invalid file type. Please upload an SQL file with .sql extension.")
    
    try:
        file_size = 0
        chunk_size = 8192  # Read in 8kb chunks
        
        # Check file size without reading the entire file into memory
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()  # Get position (file size)
        file.file.seek(0)  # Rewind
        
        # Set a reasonable file size limit (e.g., 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if file_size > max_size:
            raise ValidationError(f"File is too large. Maximum allowed size is {max_size // (1024 * 1024)}MB.")
        
        return True
    except Exception as e:
        if isinstance(e, ValidationError):
            raise
        raise ValidationError(f"Error validating file: {str(e)}")

async def convert_sql_to_laravel_migration(background_tasks, file):
    """
    Convert SQL CREATE TABLE statements to Laravel migrations.
    
    Args:
        background_tasks: FastAPI BackgroundTasks object
        file: UploadFile object
        
    Returns:
        FileResponse: ZIP file to download
        
    Raises:
        ValidationError: If file validation fails
        SQLParsingError: If SQL parsing fails
        ConversionError: If conversion fails
        FileError: If file operations fail
    """
    # Validate the file
    await validate_sql_file(file)
    
    try:
        content = await file.read()
        content = content.decode('utf-8')
        
        # Log parsing start
        logger.info(f"Starting SQL parsing for Laravel migration: {file.filename}")
        
        # Parse SQL content
        tables = parse_sql_file_for_migration(content)
        
        if not tables:
            raise ValidationError("No valid CREATE TABLE statements found in the SQL file.")
        
        logger.info(f"Found {len(tables)} tables to convert to migrations")
        
        # Create a ZIP file to store the migrations
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
            for idx, (table_name, columns_sql, engine) in enumerate(tables):
                try:
                    # Parse column definitions
                    column_defs = columns_sql.strip().split('\n')
                    columns = []
                    
                    for col_idx, col_def in enumerate(column_defs):
                        col_def = col_def.strip()
                        if col_def and not col_def.startswith('KEY') and not col_def.startswith('PRIMARY KEY'):
                            try:
                                line_number = get_line_number(content, content.find(col_def))
                                column = parse_column_definition(col_def, table_name, line_number)
                                if column:
                                    columns.append(column)
                            except SQLParsingError as e:
                                logger.warning(f"Skipping column in table {table_name}: {str(e)}")
                    
                    # Generate migration content
                    migration_content = generate_migration_content(table_name, columns, engine)
                    
                    # Format timestamp for migration filename (Laravel uses timestamps in filenames)
                    timestamp = 1000000000 + idx  # Simple incrementing timestamps
                    filename = f"{timestamp}_create_{table_name}_table.php"
                    
                    # Add the migration to the ZIP file
                    zip_file.writestr(filename, migration_content)
                    logger.info(f"Added migration for table '{table_name}' to ZIP")
                    
                except Exception as e:
                    logger.error(f"Error processing table {table_name}: {str(e)}")
                    if isinstance(e, (ValidationError, SQLParsingError, ConversionError, FileError)):
                        raise
                    raise ConversionError(f"Error generating migration for table '{table_name}': {str(e)}", converter_type="Laravel")
        
        # Create temporary ZIP file
        temp_zip_path = create_temp_zip(zip_buffer)
        background_tasks.add_task(cleanup_temp_file, temp_zip_path)
        
        return FileResponse(
            path=temp_zip_path,
            filename="laravel_migrations.zip",
            media_type='application/zip'
        )
    except UnicodeDecodeError:
        raise ValidationError("The SQL file contains invalid characters. Please ensure it's a valid UTF-8 encoded file.")
    except Exception as e:
        if isinstance(e, (ValidationError, SQLParsingError, ConversionError, FileError)):
            raise
        # Log the unexpected error
        logger.error(f"Unexpected error converting SQL to Laravel migrations: {str(e)}", exc_info=True)
        raise ConversionError(f"An error occurred during conversion: {str(e)}", converter_type="Laravel")