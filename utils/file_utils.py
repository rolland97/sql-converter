import os
import tempfile

def create_temp_file(original_filename, content, suffix):
    base_name = os.path.splitext(original_filename)[0]
    output_filename = f"{base_name}_converted{suffix}"
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=suffix) as temp_file:
        temp_file.write(content)
        temp_path = temp_file.name

    return temp_path, output_filename

def create_temp_zip(zip_buffer):
    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_zip:
        temp_zip.write(zip_buffer.getvalue())
        return temp_zip.name

def cleanup_temp_file(file_path):
    os.unlink(file_path)