"""
Utility functions for file operations.
"""
import os
import tempfile
import logging
from exceptions import FileError

# Configure logging
logger = logging.getLogger(__name__)

def create_temp_file(original_filename, content, suffix):
    """
    Create a temporary file and write content to it.
    
    Args:
        original_filename (str): Original filename to base output name on
        content (str): Content to write to the file
        suffix (str): File suffix/extension with dot (e.g., '.php')
        
    Returns:
        tuple: (temp_path, output_filename) where temp_path is the path to the temporary file
               and output_filename is the suggested filename for download
               
    Raises:
        FileError: If file creation fails
    """
    try:
        # Extract base name without extension
        base_name = os.path.splitext(os.path.basename(original_filename))[0]
        output_filename = f"{base_name}_converted{suffix}"
        
        # Sanitize filename to remove problematic characters
        output_filename = "".join(c for c in output_filename if c.isalnum() or c in "._-")
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=suffix) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name

        logger.info(f"Created temporary file: {temp_path} (download as: {output_filename})")
        return temp_path, output_filename
    except Exception as e:
        logger.error(f"Failed to create temporary file: {str(e)}", exc_info=True)
        raise FileError(f"Failed to create output file: {str(e)}", operation="file creation")

def create_temp_zip(zip_buffer):
    """
    Create a temporary ZIP file from a buffer.
    
    Args:
        zip_buffer (BytesIO): Buffer containing ZIP data
        
    Returns:
        str: Path to the temporary ZIP file
        
    Raises:
        FileError: If file creation fails
    """
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_zip:
            temp_zip.write(zip_buffer.getvalue())
            temp_path = temp_zip.name
            
        logger.info(f"Created temporary ZIP file: {temp_path}")
        return temp_path
    except Exception as e:
        logger.error(f"Failed to create temporary ZIP file: {str(e)}", exc_info=True)
        raise FileError(f"Failed to create ZIP file: {str(e)}", operation="ZIP creation")

def cleanup_temp_file(file_path):
    """
    Delete a temporary file.
    
    Args:
        file_path (str): Path to the file to delete
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
            logger.info(f"Cleaned up temporary file: {file_path}")
            return True
        else:
            logger.warning(f"Temporary file not found during cleanup: {file_path}")
            return False
    except Exception as e:
        logger.error(f"Failed to clean up temporary file {file_path}: {str(e)}", exc_info=True)
        return False