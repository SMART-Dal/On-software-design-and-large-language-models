#!/bin/bash

# A script to run a data generator JAR on a set of projects and apply several mutations.
# It verifies the success of each mutation based on specific output criteria and
# logs the results.

# --- USAGE ---
# ./run_mutations.sh /path/to/input/projects /path/to/output/folder
#
# Arguments:
#   $1: The directory containing the unzipped project folders.
#   $2: The directory where mutation outputs will be stored.

# --- Configuration ---
# IMPORTANT: Set the path to your data generator JAR file here.
DATA_GENERATOR_JAR="../data-generator/target/data-generator-1.0-SNAPSHOT-jar-with-dependencies.jar"

# --- Main Script ---

# 1. Argument and Path Validation
if [ "$#" -ne 2 ]; then
    echo "❌ Error: Invalid number of arguments."
    echo "Usage: $0 <input_directory> <output_directory>"
    exit 1
fi

INPUT_DIR=$1
OUTPUT_DIR=$2

if [ ! -d "$INPUT_DIR" ]; then
    echo "❌ Error: Input directory '$INPUT_DIR' not found."
    exit 1
fi

if [ ! -f "$DATA_GENERATOR_JAR" ]; then
    echo "❌ Error: Data generator JAR not found at '$DATA_GENERATOR_JAR'."
    echo "Please update the DATA_GENERATOR_JAR variable in the script."
    exit 1
fi

# 2. Setup
# Ensure the output directory exists
mkdir -p "$OUTPUT_DIR"

# Define the list of mutations
mutations=('dependencygraph' 'instantiationremover' 'directinstantiation' 'unusedinjecteddependency')

# Prepare log files
SUCCESS_LOG="successful_mutations.txt"
FAIL_LOG="failed_mutations.txt"
> "$SUCCESS_LOG"
> "$FAIL_LOG"
echo "Log files '$SUCCESS_LOG' and '$FAIL_LOG' have been reset."

# Array to hold projects that pass all mutations
all_successful_projects=()

echo -e "\n--- Starting Mutation Process ---\n"

# 3. Iterate Over Each Project Directory
for subdir in "$INPUT_DIR"/*/; do
    # Remove trailing slash to get a clean directory path
    project_path="${subdir%/}"
    project_name=$(basename "$project_path")
    echo "Processing Project: $project_name"

    project_fully_successful=true # Assume success until a failure occurs

    # 4. Iterate Over and Apply Each Mutation
    for mutation in "${mutations[@]}"; do
        echo "  Applying mutation: $mutation..."

        # Execute the JAR file
        java -jar "$DATA_GENERATOR_JAR" "$project_path" "$OUTPUT_DIR" "$mutation"

        # 5. Verify Mutation Success
        mutation_successful=false
        # NOTE: The check for 'unusedinjecteddependency' assumes it has the same success criteria
        # as 'directinstantiation' based on the prompt's structure.
        case $mutation in
            dependencygraph)
                if [ -f "$OUTPUT_DIR/${project_name}_disjointPairs.json" ]; then
                    mutation_successful=true
                fi
                ;;
            instantiationremover)
                if [ -d "$OUTPUT_DIR/${project_name}_instantiationremover" ] && \
                   [ -n "$(ls -A "$OUTPUT_DIR/${project_name}_instantiationremover")" ]; then
                    mutation_successful=true
                fi
                ;;
            directinstantiation)
                if [ -d "$OUTPUT_DIR/${project_name}_directinstantiation" ] && \
                   [ -n "$(ls -A "$OUTPUT_DIR/${project_name}_directinstantiation")" ] && \
                   [ -f "$OUTPUT_DIR/${project_name}_mutated_classes.json" ]; then
                    mutation_successful=true
                fi
                ;;
            unusedinjecteddependency)
                if [ -d "$OUTPUT_DIR/${project_name}_unusedinjecteddependency" ] && \
                   [ -n "$(ls -A "$OUTPUT_DIR/${project_name}_unusedinjecteddependency")" ] && \
                   [ -f "$OUTPUT_DIR/${project_name}_mutated_classes.json" ]; then
                    mutation_successful=true
                fi
                ;;
        esac

        # 6. Log the Result
        if [ "$mutation_successful" = true ]; then
            echo "    ✅ SUCCESS"
            echo "$project_name - $mutation" >> "$SUCCESS_LOG"
        else
            echo "    ❌ FAILURE"
            echo "$project_name - $mutation" >> "$FAIL_LOG"
            project_fully_successful=false # Mark project as not fully successful
        fi
    done

    # Add project to the final success list if all mutations passed
    if [ "$project_fully_successful" = true ]; then
        all_successful_projects+=("$project_name")
    fi
    echo "----------------------------------------"
done


# 7. Final Report
echo -e "\n--- Mutation Process Complete ---"
echo "✅ Successful mutations logged to: $SUCCESS_LOG"
echo "❌ Failed mutations logged to: $FAIL_LOG"
echo ""
echo "🏆 Projects with ALL successful mutations:"
if [ ${#all_successful_projects[@]} -eq 0 ]; then
    echo "  None"
else
    for proj in "${all_successful_projects[@]}"; do
        echo "  - $proj"
    done
fi