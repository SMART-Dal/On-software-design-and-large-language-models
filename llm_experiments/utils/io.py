import json
import os
from typing import Dict

def read_json_file(file_path: str) -> Dict:
    with open(file_path, 'r') as f:
        return json.load(f)
    
def get_all_files(root_dir):
    root_dir = os.path.abspath(root_dir)
    all_files = []
    
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            all_files.append(full_path)
    
    return all_files

def read_file_content(file):
    try:
        with open(file, 'r') as f:
            return f.read()
    except IOError:
        return "File content unavailable."
    
def write_to_file(data, filename, mode='w', verbose=False):
    try:
        with open(filename, mode) as file:
            # Handle both string and list data
            if isinstance(data, list):
                file.writelines(f"{line}\n" for line in data)
            else:
                file.write(str(data))
                
        if verbose:
            print(f"Successfully wrote to {filename}")
        return True
            
    except Exception as e:
        if verbose:
            print(f"Error writing to {filename}: {e}")
        return False
    
def save_to_json(data, file_path, indent=None, sort_keys=False):
    
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=indent, sort_keys=sort_keys)
