"""
Utility module for handling large files with streaming.
"""
import os
import asyncio
import tempfile
import logging
from fastapi import UploadFile
from exceptions import FileError, ValidationError

# Configure logging
logger = logging.getLogger(__name__)

class StreamingFile:
    """
    Helper class for handling large files with streaming.
    """
    def __init__(self, file_obj, max_memory_size=10 * 1024 * 1024):
        """
        Initialize a StreamingFile.
        
        Args:
            file_obj: File-like object or UploadFile
            max_memory_size (int): Maximum size to keep in memory (default: 10MB)
        """
        self.file_obj = file_obj
        self.max_memory_size = max_memory_size
        self.temp_file = None
        self.temp_file_path = None
        self.size = 0
        self.in_memory_data = None
        self.encoding = 'utf-8'  # Default encoding
    
    async def process(self):
        """
        Process the file, either keeping it in memory or writing to disk.
        
        Returns:
            bool: True if successful
            
        Raises:
            FileError: If file processing fails
        """
        try:
            if isinstance(self.file_obj, UploadFile):
                # Rewind the file
                await self.file_obj.seek(0)
                
                # Get file size
                await self.file_obj.seek(0, 2)  # Seek to end
                self.size = await self.file_obj.tell()
                await self.file_obj.seek(0)  # Rewind
                
                # Decide whether to keep in memory or write to disk
                if self.size <= self.max_memory_size:
                    # Small file, keep in memory
                    self.in_memory_data = await self.file_obj.read()
                    logger.info(f"File {getattr(self.file_obj, 'filename', 'unknown')} kept in memory ({self.size} bytes)")
                else:
                    # Large file, write to disk
                    self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.tmp')
                    self.temp_file_path = self.temp_file.name
                    
                    chunk_size = 64 * 1024  # 64KB chunks
                    while True:
                        chunk = await self.file_obj.read(chunk_size)
                        if not chunk:
                            break
                        self.temp_file.write(chunk)
                        
                    self.temp_file.close()
                    logger.info(f"File {getattr(self.file_obj, 'filename', 'unknown')} written to temp file {self.temp_file_path} ({self.size} bytes)")
            else:
                # Regular file object
                self.file_obj.seek(0, 2)  # Seek to end
                self.size = self.file_obj.tell()
                self.file_obj.seek(0)  # Rewind
                
                if self.size <= self.max_memory_size:
                    # Small file, keep in memory
                    self.in_memory_data = self.file_obj.read()
                    logger.info(f"File kept in memory ({self.size} bytes)")
                else:
                    # Large file, write to disk
                    self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.tmp')
                    self.temp_file_path = self.temp_file.name
                    
                    chunk_size = 64 * 1024  # 64KB chunks
                    while True:
                        chunk = self.file_obj.read(chunk_size)
                        if not chunk:
                            break
                        self.temp_file.write(chunk)
                        
                    self.temp_file.close()
                    logger.info(f"File written to temp file {self.temp_file_path} ({self.size} bytes)")
            
            return True
        except Exception as e:
            # Clean up temp file if created
            self.cleanup()
            logger.error(f"Error processing file: {str(e)}", exc_info=True)
            raise FileError(f"Failed to process file: {str(e)}", operation="file processing")
    
    def get_content(self):
        """
        Get the file content.
        
        Returns:
            bytes: File content
            
        Raises:
            FileError: If content retrieval fails
        """
        try:
            if self.in_memory_data is not None:
                return self.in_memory_data
            elif self.temp_file_path:
                with open(self.temp_file_path, 'rb') as f:
                    return f.read()
            else:
                raise FileError("No file content available", operation="content retrieval")
        except Exception as e:
            logger.error(f"Error retrieving file content: {str(e)}", exc_info=True)
            raise FileError(f"Failed to retrieve file content: {str(e)}", operation="content retrieval")
    
    def get_text(self, encoding=None):
        """
        Get the file content as text.
        
        Args:
            encoding (str, optional): Text encoding (default: utf-8)
            
        Returns:
            str: File content as text
            
        Raises:
            FileError: If content retrieval fails
            UnicodeDecodeError: If text decoding fails
        """
        if encoding:
            self.encoding = encoding
            
        try:
            content = self.get_content()
            return content.decode(self.encoding)
        except UnicodeDecodeError as e:
            logger.error(f"Unicode decode error with encoding {self.encoding}: {str(e)}")
            raise ValidationError(f"The file contains invalid characters for {self.encoding} encoding.")
        except Exception as e:
            logger.error(f"Error getting text content: {str(e)}", exc_info=True)
            raise FileError(f"Failed to get text content: {str(e)}", operation="text retrieval")
    
    def get_stream(self, chunk_size=8192):
        """
        Get a generator that yields chunks of the file.
        
        Args:
            chunk_size (int): Size of chunks to yield
            
        Yields:
            bytes: Chunks of file content
            
        Raises:
            FileError: If stream creation fails
        """
        try:
            if self.in_memory_data is not None:
                # Stream from memory
                data = self.in_memory_data
                for i in range(0, len(data), chunk_size):
                    yield data[i:i + chunk_size]
            elif self.temp_file_path:
                # Stream from temp file
                with open(self.temp_file_path, 'rb') as f:
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk
            else:
                raise FileError("No file content available for streaming", operation="stream creation")
        except Exception as e:
            logger.error(f"Error creating file stream: {str(e)}", exc_info=True)
            raise FileError(f"Failed to create file stream: {str(e)}", operation="stream creation")
    
    async def read_lines(self, encoding=None):
        """
        Read the file line by line.
        
        Args:
            encoding (str, optional): Text encoding (default: utf-8)
            
        Yields:
            str: Lines from the file
            
        Raises:
            FileError: If line reading fails
        """
        if encoding:
            self.encoding = encoding
            
        try:
            text = self.get_text(self.encoding)
            for line in text.splitlines():
                yield line
        except Exception as e:
            if isinstance(e, (ValidationError, FileError)):
                raise
            logger.error(f"Error reading lines: {str(e)}", exc_info=True)
            raise FileError(f"Failed to read lines: {str(e)}", operation="line reading")
    
    def cleanup(self):
        """
        Clean up temporary resources.
        
        Returns:
            bool: True if cleanup was successful
        """
        try:
            if self.temp_file_path and os.path.exists(self.temp_file_path):
                os.unlink(self.temp_file_path)
                self.temp_file_path = None
                logger.info(f"Temporary file {self.temp_file_path} deleted")
            
            self.in_memory_data = None
            return True
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {str(e)}", exc_info=True)
            return False

async def stream_large_sql_file(file, processor_func, max_memory_size=10 * 1024 * 1024):
    """
    Process a large SQL file in streaming mode.
    
    Args:
        file: UploadFile object
        processor_func: Function to process each SQL statement
        max_memory_size (int): Maximum size to keep in memory
        
    Returns:
        dict: Processing results
        
    Raises:
        FileError: If file processing fails
        ValidationError: If file validation fails
    """
    # Validate file first
    if not file.filename.endswith('.sql'):
        raise ValidationError("Invalid file type. Please upload an SQL file with .sql extension.")
    
    streaming_file = StreamingFile(file, max_memory_size)
    try:
        await streaming_file.process()
        
        # For SQL files, we need to collect statements that might span multiple lines
        current_statement = []
        results = []
        
        async for line in streaming_file.read_lines():
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith('--') or line.startswith('#'):
                continue
                
            current_statement.append(line)
            
            # If line ends with semicolon, we have a complete statement
            if line.endswith(';'):
                statement = ' '.join(current_statement)
                try:
                    result = await processor_func(statement)
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.error(f"Error processing SQL statement: {str(e)}", exc_info=True)
                    # Continue processing other statements
                
                # Reset for next statement
                current_statement = []
        
        # Process any remaining statement (in case of missing semicolon)
        if current_statement:
            statement = ' '.join(current_statement)
            try:
                result = await processor_func(statement)
                if result:
                    results.append(result)
            except Exception as e:
                logger.error(f"Error processing final SQL statement: {str(e)}", exc_info=True)
        
        return results
    finally:
        # Clean up resources
        streaming_file.cleanup()