# Script used to clean the results of the experiments. Specifically, it extracts the json portion from the model's response.
from utils.io import get_all_files, read_json_file, save_to_json
from tqdm import tqdm
from argparse import ArgumentParser
import json
import re
import os

def parse_args():
    parser = ArgumentParser()
    parser.add_argument("--input_folder", type=str, required=True, help="Path to the folder containing input files.")
    parser.add_argument("--output_folder", type=str, required=True, help="Path to the folder where output files will be saved.")
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
    json_match = re.search(r"```(?:json)?\n(.*?)\n```", markdown_string, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            return None
    try:
      return json.loads(markdown_string)
    except json.JSONDecodeError:
      return None


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
                'answer': extracted_answer
            }
            save_to_json(data, output_file_path)
        else:
            print(f"No JSON found in file: {file}")

if __name__ == "__main__":
    args = parse_args()
    input_folder = args.input_folder
    output_folder = args.output_folder

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    process_files(input_folder, output_folder)