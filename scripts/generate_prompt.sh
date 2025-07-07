#!/bin/bash



# Usage:
#   ./process_yaml_files.sh <search_directory>



PYTHON_SCRIPT="prompt.build_prompt"
SEARCH_DIR=$1

# --- Main Logic ---
echo "Starting YAML file processing..."


# Find all files ending in .yml or .yaml in the current directory.
# The `find` command is robust and handles filenames with spaces.
# The `-maxdepth 1` option prevents it from searching in subdirectories.
find "$SEARCH_DIR" -maxdepth 1 -type f \( -name "*.yml" -o -name "*.yaml" \) -print0 | while IFS= read -r -d $'\0' yaml_file; do
    # Check if the file exists and is a regular file to avoid errors
    if [ -f "$yaml_file" ]; then
        echo "----------------------------------------"
        echo "Processing file: $yaml_file"

        python3 -m "$PYTHON_SCRIPT" --config_file="$yaml_file"

        echo "Finished processing $yaml_file"
        echo "----------------------------------------"
    fi
done

echo "All YAML files have been processed."
