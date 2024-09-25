import os
import tempfile
import zipfile
import datetime
from typing import Dict

def read_html_template(template_name: str) -> str:
    template_path = os.path.join('app', 'templates', template_name)
    with open(template_path, 'r') as file:
        return file.read()

def create_temp_file(content: str, suffix: str, prefix: str = "main") -> str:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}{suffix}"
    temp_path = os.path.join('/app/temp', filename)
    
    with open(temp_path, 'wb') as temp_file:
        temp_file.write(content.encode('utf-8') if isinstance(content, str) else content)
    
    return temp_path

def create_zip_file(files: Dict[str, str]) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_zip:
        with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for filename, content in files.items():
                zip_file.writestr(filename, content)
        return temp_zip.name