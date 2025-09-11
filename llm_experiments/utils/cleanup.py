# Script used to clean the results of the experiments. Specifically, it extracts the json portion from the model's response.
from utils.io import get_all_files, read_json_file, save_to_json
from tqdm import tqdm
from argparse import ArgumentParser
import json
import re
import os

def convert_string_none(obj):
    if isinstance(obj, list):
        return [convert_string_none(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: convert_string_none(value) for key, value in obj.items()}
    elif obj == "None":  # Check for exact string match
        return None
    else:
        return obj
    
def parse_args():
    parser = ArgumentParser()
    parser.add_argument("--input_folder", type=str, required=True, help="Path to the folder containing input files.")
    args = parser.parse_args()
    return args


def extract_json_from_markdown(markdown_string):
    """
    Extracts JSON from a Markdown string.

    Args:
        markdown_string: The Markdown string to extract JSON from.

    Returns:
        A Python dictionary representing the extracted JSON, or None if no JSON is found.
    """
    json_pattern = re.compile(r"```json\n(.*?)\n```", re.DOTALL)
    
    # Find all non-overlapping matches in the string
    json_blocks = json_pattern.findall(markdown_string)
    
    parsed_json_list = []
    for block in json_blocks:
        # Avoid trying to parse empty or whitespace-only blocks
        if not block.strip():
            continue
        try:
            # Parse the extracted string into a Python object
            parsed_json = json.loads(block)
            parsed_json_list.append(parsed_json)
        except json.JSONDecodeError as e:
            # Handle cases where a block contains invalid JSON
            print(f"Skipping a block due to a JSON parsing error: {e}")
            
    return parsed_json_list


def process_files(input_folder, output_folder):
    """
    Processes all files in the input folder, extracts JSON from each file, and saves the results to the output folder.

    Args:
        input_folder: The folder containing the input files.
        output_folder: The folder where the output files will be saved.
    """
    files = get_all_files(input_folder)
    for file in tqdm(files):
        content = read_json_file(file)
        extracted_answer = extract_json_from_markdown(content['answer'])
        if extracted_answer:
            output_file_path = os.path.join(output_folder, os.path.basename(file))
            data = {
                'cot': content['cot'] if 'cot' in content else None,
                'answer': convert_string_none(extracted_answer),
            }
            save_to_json(data, output_file_path)
        else:
            print(f"No JSON found in file: {file}")

if __name__ == "__main__":
    args = parse_args()
    input_folder_path = args.input_folder
    input_folder = os.path.basename(input_folder_path)
    output_folder_name = f"{input_folder}_cleaned"
    output_folder = os.path.join(os.path.dirname(input_folder_path), output_folder_name)
    # Create output folder if it does not exist
    os.makedirs(output_folder, exist_ok=True)

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    process_files(input_folder_path, output_folder)