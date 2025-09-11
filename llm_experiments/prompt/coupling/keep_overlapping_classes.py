import os
import json
from collections import defaultdict

def analyze_project_keys_and_values(directory_path):
    """
    Analyzes JSON files in a directory to find common keys with identical
    values for each project. The common data is then saved to a new JSON file.

    Args:
        directory_path (str): The path to the directory containing the JSON files.
    """
    # Use a defaultdict to conveniently group file paths by project name.
    project_files = defaultdict(list)

    # --- 1. Group files by project ---
    try:
        # Get a list of all files in the specified directory.
        filenames = os.listdir(directory_path)
    except FileNotFoundError:
        print(f"Error: The directory '{directory_path}' was not found.")
        return
    except Exception as e:
        print(f"An error occurred while accessing the directory: {e}")
        return

    for filename in filenames:
        # We are only interested in JSON files that follow the specified naming pattern.
        if filename.endswith(('.json')) and '_mutated_classes_' in filename:
            # The project name is the part of the filename before the known suffix.
            project_name = filename.split('_mutated_classes_')[0]
            full_path = os.path.join(directory_path, filename)
            project_files[project_name].append(full_path)

    if not project_files:
        print("No projects found. Please check the filenames and directory path.")
        return

    print(f"Found {len(project_files)} project(s). Analyzing...\n")

    # --- 2. Process each project to find common keys with matching values ---
    for project_name, files in sorted(project_files.items()):
        print(f"--- Project: {project_name} ---")
        # We are looking for projects that have exactly three associated files.
        if len(files) != 3:
            print(f"  Skipping: Expected 3 JSON files, but found {len(files)}.\n")
            continue

        project_data = []
        has_error = False
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    # Load the entire JSON object to compare values later.
                    project_data.append(json.load(f))
            except json.JSONDecodeError:
                print(f"  Error: Could not parse JSON from '{os.path.basename(file_path)}'. It may be malformed.")
                has_error = True
                break
            except IOError as e:
                print(f"  Error reading file '{os.path.basename(file_path)}': {e}")
                has_error = True
                break
        
        if has_error:
            print(f"Could not process '{project_name}' due to errors.\n")
            continue

        # --- 3. Find keys that are present in all three files ---
        key_sets = [set(d.keys()) for d in project_data]
        common_keys = key_sets[0].intersection(*key_sets[1:])
        
        # --- 4. Filter common keys to find those with identical values ---
        keys_with_matching_values = set()
        if common_keys:
            for key in common_keys:
                reference_value = project_data[0][key]
                values_are_identical = all(other_data[key] == reference_value for other_data in project_data[1:])
                
                if values_are_identical:
                    keys_with_matching_values.add(key)

        # --- 5. Print the results ---
        print(f"  Files considered: {[os.path.basename(f) for f in files]}")
        print(f"  Number of overlapping keys with identical values: {len(keys_with_matching_values)}")

        # --- 6. Create and save the new JSON file with common data if it's not empty ---
        if keys_with_matching_values:
            output_filename = f"{project_name}_coupling_common.json"
            output_filepath = os.path.join(directory_path, output_filename)
            
            common_data_to_save = {
                key: project_data[0][key] for key in sorted(list(keys_with_matching_values))
            }

            try:
                with open(output_filepath, 'w', encoding='utf-8') as f:
                    json.dump(common_data_to_save, f, indent=4)
                print(f"  Successfully saved common data to '{output_filename}'")
            except IOError as e:
                print(f"  Error: Could not write to file '{output_filename}': {e}")
        else:
            print("  No common data to save. File not created.")
        
        print("-" * 30 + "\n")



# --- Main execution block ---
if __name__ == '__main__':
    # Change target_directory to the output directory of the data generation process.
    target_directory = ''

    analyze_project_keys_and_values(target_directory)

