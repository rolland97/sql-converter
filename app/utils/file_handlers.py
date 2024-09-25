import os
import tempfile
import zipfile
from typing import Dict

def read_html_template(template_name: str) -> str:
    template_path = os.path.join('app', 'templates', template_name)
    with open(template_path, 'r') as file:
        return file.read()

def create_temp_file(content: str, suffix: str) -> str:
    with tempfile.NamedTemporaryFile(mode='w+b', delete=False, suffix=suffix) as temp_file:
        temp_file.write(content.encode('utf-8') if isinstance(content, str) else content)
        return temp_file.name

def create_zip_file(files: Dict[str, str]) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_zip:
        with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for filename, content in files.items():
                zip_file.writestr(filename, content)
        return temp_zip.name