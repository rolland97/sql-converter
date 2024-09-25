# app/config.py

import os
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    APP_NAME: str = "SQL Converter"
    DEBUG: bool = Field(default=False, env="DEBUG")
    
    MAX_UPLOAD_SIZE: int = Field(default=5 * 1024 * 1024, env="MAX_UPLOAD_SIZE")  # 5 MB
    ALLOWED_EXTENSIONS: set = {".sql"}
    
    DEFAULT_PHP_FILENAME: str = "converted_sql.php"
    DEFAULT_MIGRATION_FILENAME: str = "laravel_migrations.zip"
    
    MAX_INSERT_ROWS: int = Field(default=1000, env="MAX_INSERT_ROWS")
    
    PHP_ARRAY_INDENT: str = "    "
    
    MIGRATION_TEMPLATE_PATH: str = "app/templates/migration_template.php"
    
    ENABLE_LARAVEL_MIGRATION: bool = Field(default=True, env="ENABLE_LARAVEL_MIGRATION")
    ENABLE_PHP_ARRAY: bool = Field(default=True, env="ENABLE_PHP_ARRAY")
    
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8001, env="PORT")

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()