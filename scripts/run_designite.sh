#!/bin/bash


JAR_FILE=$1


# --- SCRIPT LOGIC ---

# 1. Validate Input
# Check if exactly two arguments are provided.
if [ "$#" -ne 2 ]; then
    echo "Error: Invalid number of arguments."
    echo "Usage: $0 <input_directory> <output_directory>"
    exit 1
fi

# Assign arguments to more descriptive variables.
INPUT_DIRECTORY=$2
OUTPUT_DIRECTORY=$3

# Check if the input directory is a valid directory.
if [ ! -d "$INPUT_DIRECTORY" ]; then
    echo "Error: The input path '$INPUT_DIRECTORY' is not a valid directory."
    exit 1
fi

# Check if the output directory exists. If not, create it.
if [ ! -d "$OUTPUT_DIRECTORY" ]; then
    echo "Output directory '$OUTPUT_DIRECTORY' not found. Creating it..."
    mkdir -p "$OUTPUT_DIRECTORY"
    if [ $? -ne 0 ]; then
        echo "Error: Could not create output directory '$OUTPUT_DIRECTORY'."
        exit 1
    fi
fi

# Check if the configured JAR file exists.
if [ ! -f "$JAR_FILE" ]; then
    echo "Error: The JAR file was not found at '$JAR_FILE'."
    echo "Please update the JAR_FILE variable at the top of this script."
    exit 1
fi


# 2. Process Directories
echo "Starting processing..."
echo "Input Directory:  $INPUT_DIRECTORY"
echo "Output Directory: $OUTPUT_DIRECTORY"
echo "JAR File:         $JAR_FILE"
echo "--------------------------------------------------"

# Find all directories within the target directory and loop through them.
find "$INPUT_DIRECTORY" -mindepth 1 -maxdepth 1 -type d | while read -r INPUT_FOLDER_PATH; do
    # Get the base name of the input folder (e.g., "folder1" from "/data/input/folder1").
    FOLDER_NAME=$(basename "$INPUT_FOLDER_PATH")
    
    # Construct the path for the corresponding output folder.
    OUTPUT_FOLDER_PATH="$OUTPUT_DIRECTORY/$FOLDER_NAME"

    echo "Processing folder: '$INPUT_FOLDER_PATH'"

    # Create the corresponding folder in the output directory.
    echo "Creating output folder: '$OUTPUT_FOLDER_PATH'"
    mkdir -p "$OUTPUT_FOLDER_PATH"
    if [ $? -ne 0 ]; then
        echo "Warning: Could not create output folder '$OUTPUT_FOLDER_PATH'. Skipping."
        continue
    fi

    # Execute the Java command, passing both the input and output paths.
    # We wrap the variables in double quotes to handle paths with spaces.
    java -jar "$JAR_FILE" -i "$INPUT_FOLDER_PATH" -o "$OUTPUT_FOLDER_PATH"

    # Optional: Capture the exit code to see if the command was successful.
    if [ $? -eq 0 ]; then
        echo "Successfully processed '$INPUT_FOLDER_PATH'."
    else
        echo "Warning: The command failed for '$INPUT_FOLDER_PATH' with exit code $?."
    fi
    echo "--------------------------------------------------"
done

echo "All folders have been processed."
echo "Script finished."
