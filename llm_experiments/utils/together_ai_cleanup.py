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

def is_valid_think_tags(text):
    """Validates that <think> tags are properly structured and nested."""
    tags = re.findall(r'</?think>', text)
    stack = []
    for tag in tags:
        if tag == '<think>':
            # Prevent nested thinks
            if stack:
                return False
            stack.append(tag)
        elif tag == '</think>':
            if not stack:
                return False  # Closing tag without opening
            stack.pop()
    return len(stack) == 0  # All tags must be closed

def separate_thoughts(text):
    """
    Separates reasoning traces wrapped in <think> tags with validation.
    Returns tuple (thoughts, cleaned_output) if valid, None otherwise.
    """
    if not is_valid_think_tags(text):
        return None
    
    # Count opening tags for validation
    num_think = text.count('<think>')
    
    # Extract and clean thoughts
    thoughts = re.findall(r'<think>(.*?)</think>', text, flags=re.DOTALL)
    thoughts = [t.strip() for t in thoughts]
    
    # Verify extraction count matches tag count
    if len(thoughts) != num_think:
        return None
    
    # Clean the final output
    cleaned_output = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    
    return (thoughts, cleaned_output)


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
        if content is None:
            data = {
                'cot': '',
                'answer': []
            }
            output_file_path = os.path.join(output_folder, os.path.basename(file))
            save_to_json(data, output_file_path)
            continue

        answer = content['answer']
        if type(answer) == list:
            print(f"Answer is a list in file: {file}")
            print(f"Answer: {answer}")
        processed_answer = separate_thoughts(answer)
        if not processed_answer:
            data = {
                'cot': answer,
                'answer': []
            }
            output_file_path = os.path.join(output_folder, os.path.basename(file))
            save_to_json(data, output_file_path)
            continue

        thoughts, cleaned_output = processed_answer
        json_answer = extract_json_from_markdown(cleaned_output)
        if json_answer:
            output_file_path = os.path.join(output_folder, os.path.basename(file))
            data = {
                'cot': thoughts,
                'answer': json_answer
            }
            save_to_json(data, output_file_path)
        else:
            print(f"No JSON found in file: {file}")
            data = {
                'cot': thoughts,
                'answer': []
            }
            output_file_path = os.path.join(output_folder, os.path.basename(file))
            save_to_json(data, output_file_path)

if __name__ == "__main__":
    args = parse_args()
    input_folder = args.input_folder
    output_folder = args.output_folder

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    process_files(input_folder, output_folder)
