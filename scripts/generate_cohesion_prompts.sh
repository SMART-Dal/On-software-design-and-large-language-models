#!/bin/bash

# --- Configuration ---
# Set the paths to your main directories here.
# IMPORTANT: Replace these placeholder paths with the actual paths on your system.
JAR_FILE=$1
DJ_OUTPUT_DIR=$2
RAW_PROJECTS_DIR=$3
OUTPUT_DIR=$4
# Set the path to your Java .jar file.


# --- Script Logic ---

# Check if the main directories exist to prevent errors.
if [ ! -d "$DJ_OUTPUT_DIR" ]; then
    echo "Error: Designite Java output directory not found at: $DJ_OUTPUT_DIR"
    exit 1
fi

if [ ! -d "$RAW_PROJECTS_DIR" ]; then
    echo "Error: Raw projects directory not found at: $RAW_PROJECTS_DIR"
    exit 1
fi

if [ ! -f "$JAR_FILE" ]; then
    echo "Error: Jar file not found at: $JAR_FILE"
    exit 1
fi


# Create the main output directory if it doesn't already exist.
# The '-p' flag ensures no error is thrown if the directory already exists.
mkdir -p "$OUTPUT_DIR"

# Loop through each immediate subdirectory within the X_DIR.
# The '*/' pattern ensures we only match directories.
for subdir_path in "$DJ_OUTPUT_DIR"/*/; do
    # Check if it is a directory before processing
    if [ -d "$subdir_path" ]; then
        # Get the base name of the subdirectory (e.g., "subdir1")
        subdir_name=$(basename "$subdir_path")

        # Define the full paths for the inputs and output for the current subdirectory.
        raw_project="$RAW_PROJECTS_DIR/$subdir_name"
        project_type_metrics="$DJ_OUTPUT_DIR/$subdir_name/TypeMetrics.csv"
        current_output_dir="$OUTPUT_DIR/$subdir_name"

        # Check if the required input file and directory for this iteration exist.
        if [ ! -f "$project_type_metrics" ]; then
            echo "Skipping: TypeMetrics.csv not found in $DJ_OUTPUT_DIR/$subdir_name"
            continue # Skip to the next iteration
        fi

        if [ ! -d "$raw_project" ]; then
            echo "Skipping: Corresponding directory not found in raw projects directory: $raw_project"
            continue # Skip to the next iteration
        fi

        # Create the specific output subdirectory for this iteration.
        echo "Creating output directory: $current_output_dir"
        mkdir -p "$current_output_dir"

        # Announce which subdirectory is being processed.
        echo "--------------------------------------------------"
        echo "Processing subdirectory: $subdir_name"
        echo "Raw Project : $raw_project"
        echo "TypeMetrics : $project_type_metrics"
        echo "Output Dir:  $current_output_dir"
        echo "--------------------------------------------------"

        # Execute the Java .jar file with the specified arguments.
        # We use quotes around the paths to handle names with spaces.
        java -cp "$JAR_FILE" org.smart.CohesionDatasetGenerator "$raw_project" "$project_type_metrics" "$current_output_dir"
    fi
done

echo "Script finished."
