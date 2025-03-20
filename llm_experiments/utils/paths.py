import os

def get_absolute_file_paths(root_dir):
    absolute_paths = set()
    root_dir = os.path.abspath(root_dir)  # Ensure the root is an absolute path
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            absolute_paths.add(full_path)
    return absolute_paths

