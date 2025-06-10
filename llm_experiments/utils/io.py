import json
import os
import yaml
from typing import Dict
from types import SimpleNamespace

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
            return f.read(), True
    except IOError:
        return "File content unavailable.", False
    
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

def parse_yaml_config(file_path: str) -> SimpleNamespace:
    
    try:
        with open(file_path, 'r', encoding='utf-8') as yaml_file:
            config = yaml.safe_load(yaml_file)
            return _dict_to_namespace(config)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Config file not found: {file_path}") from e
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Error parsing YAML file: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Error reading config file: {e}") from e
    
def _dict_to_namespace(data):
    """Recursively convert nested dictionaries to SimpleNamespace"""
    if isinstance(data, dict):
        return SimpleNamespace(**{
            k: _dict_to_namespace(v) for k, v in data.items()
        })
    elif isinstance(data, list):
        return [_dict_to_namespace(i) for i in data]
    return data

def _namespace_to_dict(obj):
    # If the object is a SimpleNamespace, convert it to a dictionary
    if isinstance(obj, SimpleNamespace):
        return {key: _namespace_to_dict(value) for key, value in obj.__dict__.items()}
    # If the object is a list, recursively convert its elements
    elif isinstance(obj, list):
        return [_namespace_to_dict(item) for item in obj]
    # If the object is a dictionary, recursively convert its values
    elif isinstance(obj, dict):
        return {key: _namespace_to_dict(value) for key, value in obj.items()}
    # For all other types (e.g., strings, numbers), return as is
    else:
        return obj
    
def save_config_to_yaml(config: SimpleNamespace, file_path: str) -> None:
    """
    Save a modified SimpleNamespace object to a YAML file.
    
    Args:
        config (SimpleNamespace): The modified SimpleNamespace object.
        file_path (str): The path to the output YAML file.
    """
    try:
        # Convert the SimpleNamespace object to a dictionary
        config_dict = _namespace_to_dict(config)
        # Write the dictionary to the YAML file
        with open(file_path, 'w', encoding='utf-8') as yaml_file:
            yaml.safe_dump(config_dict, yaml_file)
    except Exception as e:
        raise RuntimeError(f"Error saving config to YAML file: {e}") from e