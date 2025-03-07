"""
Module for detecting and handling different SQL dialects.
"""
import re
import logging

# Configure logging
logger = logging.getLogger(__name__)

class SQLDialect:
    """
    Class for detecting and handling different SQL dialects.
    """
    # SQL Dialect Types
    MYSQL = 'mysql'
    POSTGRESQL = 'postgresql'
    SQLITE = 'sqlite'
    SQLSERVER = 'sqlserver'
    ORACLE = 'oracle'
    UNKNOWN = 'unknown'
    
    @staticmethod
    def detect_dialect(sql_content):
        """
        Detect the SQL dialect from the content.
        
        Args:
            sql_content (str): SQL content to analyze
            
        Returns:
            str: Detected dialect (mysql, postgresql, sqlite, sqlserver, oracle) or unknown
        """
        # Convert to lowercase for case-insensitive matching
        sql_lower = sql_content.lower()
        
        # MySQL specific patterns
        if re.search(r'engine\s*=\s*(?:innodb|myisam)', sql_lower) or \
           re.search(r'auto_increment', sql_lower) or \
           re.search(r'character set utf8', sql_lower):
            return SQLDialect.MYSQL
            
        # PostgreSQL specific patterns
        if re.search(r'serial\b', sql_lower) or \
           re.search(r'bigserial\b', sql_lower) or \
           re.search(r'returning\b', sql_lower) or \
           re.search(r'::(?:text|int|bool|timestamp)', sql_lower):
            return SQLDialect.POSTGRESQL
            
        # SQLite specific patterns
        if re.search(r'sqlite_sequence', sql_lower) or \
           re.search(r'pragma', sql_lower) or \
           re.search(r'autoincrement', sql_lower):
            return SQLDialect.SQLITE
            
        # SQL Server specific patterns
        if re.search(r'nvarchar', sql_lower) or \
           re.search(r'datetime2', sql_lower) or \
           re.search(r'identity\(\d+,\d+\)', sql_lower) or \
           re.search(r'go\s*$', sql_lower, re.MULTILINE):
            return SQLDialect.SQLSERVER
            
        # Oracle specific patterns
        if re.search(r'varchar2', sql_lower) or \
           re.search(r'number\(\d+,\d+\)', sql_lower) or \
           re.search(r'sysdate', sql_lower) or \
           re.search(r'dual', sql_lower):
            return SQLDialect.ORACLE
            
        # If no specific dialect detected, look for common SQL patterns
        # and make best guess
        if 'insert into' in sql_lower and 'values' in sql_lower:
            # Default to MySQL for INSERT statements if no specific signals
            logger.info("No specific dialect detected for INSERT statements. Defaulting to MySQL.")
            return SQLDialect.MYSQL
            
        if 'create table' in sql_lower:
            # Default to MySQL for CREATE TABLE if no specific signals
            logger.info("No specific dialect detected for CREATE TABLE statements. Defaulting to MySQL.")
            return SQLDialect.MYSQL
            
        # If nothing detected
        logger.warning("Could not detect SQL dialect. Using generic SQL parsing.")
        return SQLDialect.UNKNOWN
    
    @staticmethod
    def normalize_type(sql_type, dialect):
        """
        Normalize SQL types across different dialects.
        
        Args:
            sql_type (str): SQL data type
            dialect (str): SQL dialect
            
        Returns:
            str: Normalized SQL type
        """
        sql_type = sql_type.lower()
        
        # MySQL types normalization
        if dialect == SQLDialect.MYSQL:
            if sql_type == 'tinyint(1)':
                return 'boolean'
            elif sql_type.startswith('int'):
                return 'integer'
            # Other MySQL specific normalizations
            elif sql_type.startswith('varchar'):
                return 'string'
                
        # PostgreSQL types normalization
        elif dialect == SQLDialect.POSTGRESQL:
            if sql_type == 'serial':
                return 'integer'
            elif sql_type == 'bigserial':
                return 'biginteger'
            elif sql_type == 'text':
                return 'text'
            elif sql_type == 'numeric':
                return 'decimal'
                
        # SQLite types normalization (very simplified type system)
        elif dialect == SQLDialect.SQLITE:
            if sql_type in ('integer', 'int'):
                return 'integer'
            elif sql_type in ('text', 'varchar', 'char'):
                return 'string'
            elif sql_type == 'real':
                return 'float'
            elif sql_type == 'blob':
                return 'binary'
                
        # SQL Server types normalization
        elif dialect == SQLDialect.SQLSERVER:
            if sql_type.startswith('nvarchar'):
                return 'string'
            elif sql_type == 'bit':
                return 'boolean'
            elif sql_type == 'uniqueidentifier':
                return 'uuid'
                
        # Oracle types normalization
        elif dialect == SQLDialect.ORACLE:
            if sql_type.startswith('varchar2'):
                return 'string'
            elif sql_type == 'number' or sql_type.startswith('number('):
                return 'decimal'
            elif sql_type == 'clob':
                return 'text'
                
        # Return the original type if no normalization applied
        return sql_type
    
    @staticmethod
    def get_type_mapping(dialect):
        """
        Get the type mapping dictionary for a specific dialect.
        
        Args:
            dialect (str): SQL dialect
            
        Returns:
            dict: Dictionary mapping SQL types to normalized types
        """
        # Base type mappings (shared across dialects)
        base_mapping = {
            'int': 'integer',
            'integer': 'integer',
            'bigint': 'biginteger',
            'smallint': 'smallinteger',
            'tinyint': 'tinyinteger',
            'varchar': 'string',
            'char': 'string',
            'text': 'text',
            'date': 'date',
            'datetime': 'datetime',
            'timestamp': 'timestamp',
            'decimal': 'decimal',
            'numeric': 'decimal',
            'float': 'float',
            'double': 'double',
            'boolean': 'boolean',
            'blob': 'binary'
        }
        
        # MySQL specific types
        mysql_mapping = {
            'tinyint(1)': 'boolean',
            'mediumtext': 'text',
            'longtext': 'text',
            'mediumblob': 'binary',
            'longblob': 'binary',
            'enum': 'enum'
        }
        
        # PostgreSQL specific types
        postgresql_mapping = {
            'serial': 'integer',
            'bigserial': 'biginteger',
            'jsonb': 'json',
            'uuid': 'uuid',
            'timestamptz': 'timestamptz'
        }
        
        # SQLite specific types (very limited type system)
        sqlite_mapping = {
            'integer': 'integer',
            'text': 'string',
            'real': 'float',
            'blob': 'binary'
        }
        
        # SQL Server specific types
        sqlserver_mapping = {
            'nvarchar': 'string',
            'nchar': 'string',
            'uniqueidentifier': 'uuid',
            'datetime2': 'datetime',
            'bit': 'boolean'
        }
        
        # Oracle specific types
        oracle_mapping = {
            'varchar2': 'string',
            'number': 'decimal',
            'clob': 'text',
            'nclob': 'text',
            'raw': 'binary'
        }
        
        # Select appropriate mapping dictionary
        mapping = base_mapping.copy()
        
        if dialect == SQLDialect.MYSQL:
            mapping.update(mysql_mapping)
        elif dialect == SQLDialect.POSTGRESQL:
            mapping.update(postgresql_mapping)
        elif dialect == SQLDialect.SQLITE:
            mapping.update(sqlite_mapping)
        elif dialect == SQLDialect.SQLSERVER:
            mapping.update(sqlserver_mapping)
        elif dialect == SQLDialect.ORACLE:
            mapping.update(oracle_mapping)
            
        return mapping