from glob import iglob
from openai import OpenAI
from openai.types.chat import ChatCompletion
from argparse import ArgumentParser
from typing import List, Union
from utils.io import get_all_files, read_file_content, save_to_json, read_json_file
from tqdm import tqdm
from transformers import AutoTokenizer
import numpy as np
import os

TEMPEATURE = 0
ALPHA = 1
TEMPLATE_TYPES = ["hybrid", "retrieval", "binary"]
NOISE_RATIOS = [round(i*1e-1, 1) for i in range(1, 9)]
TOKENIZER = "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"

def _beautify_project_name(path: str):
    project_name = path.split(os.sep)[-3]
    project_name = project_name.split("_")[0]
    return project_name

def calculate_range(data):
    mean, std = np.mean(data), np.std(data)
    
    return mean, std

def fetch_by_noise_ratio(dataset, noise_ratio):
    """Fetch dataset entries by noise ratio"""
    if noise_ratio not in NOISE_RATIOS:
        raise ValueError(f"Noise ratio {noise_ratio} is not supported. Supported ratios are: {NOISE_RATIOS}")
    
    filtered_dataset = []
    for entry in dataset:
        filtered_dataset.append(entry[str(noise_ratio)])
    
    return filtered_dataset

def is_already_processed(output_dir, input_file):
    """Check if a response file already exists for this input file"""
    base_name = os.path.basename(input_file)
    response_path = os.path.join(output_dir, f"{base_name}_response.json")
    return os.path.exists(response_path)

def return_client(type: str) -> OpenAI:
    if type == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("API key for OpenAI not found in environment variables.")
        client = OpenAI(api_key=api_key)
    elif type == "deepseek":
        api_key = os.environ.get("DS_API_KEY")
        if not api_key:
            raise ValueError("API key for DeepSeek not found in environment variables.")
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/")
    elif type == "together_ai":
        api_key = os.environ.get("TOGETHER_AI_API_KEY")
        if not api_key:
            raise ValueError("API key for Together AI not found in environment variables.")
        client = OpenAI(api_key=api_key, base_url="https://api.together.xyz/v1")
    elif type == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("API key for OpenRouter not found in environment variables.")
        client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
    else:
        raise ValueError("Unsupported model type. Supported types are: openai, deepseek.")
    
    return client

def execute_prompt(client: OpenAI, tokenizer: AutoTokenizer, ctx_len: int , model_name: str, reasoning: bool, prompt: str) -> Union[str, List[str], ChatCompletion]:
    try:
        # Calculate max tokens based on the model
        prompt_len = len(tokenizer.tokenize(prompt))
        if prompt_len > ctx_len:
            raise ValueError(f"Prompt length {prompt_len} exceeds model context length {ctx_len}. Please shorten the prompt.")
        max_tokens = ctx_len - prompt_len
        if max_tokens == 0:
            raise ValueError("Max tokens is 0, please shorten the prompt.")
        print(f"Prompt length: {prompt_len}, Max tokens for response: {max_tokens}")
        response: ChatCompletion = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=TEMPEATURE,
            max_tokens=max_tokens,
        )
        reasoning_content = None
        if reasoning:
            reasoning_content = response.choices[0].message.reasoning
        
        content = response.choices[0].message.content

        return {'answer': content, 'reasoning': reasoning_content, 'openrouter_model': model_name, 'hf_slug': tokenizer.name_or_path, 'prompt': prompt, 'prompt_len': prompt_len, 'max_tokens': max_tokens}
    
    except Exception as e:
        print(f"Error executing prompt: {e}")
        return None

def parse_args():
    parser = ArgumentParser(description="Parse model type and API key.")
    parser.add_argument("--model_type", type=str, required=True, help="Type of model to use (openai or deepseek).", choices=["openai", "deepseek", "together_ai", "openrouter"])
    parser.add_argument("--reasoning", action="store_true", help="Indicate whether this is a reasoning model or not.")
    parser.add_argument("--model_name", type=str, required=True, help="Name of the model to use. Example: gpt-3.5-turbo, deepseek-reaonser.")
    parser.add_argument("--max_tokens", type=float, default=4096, help="Maximum number of tokens for the model. Default is 4096.")
    parser.add_argument("--prompts_folder", type=str, required=True, help="Path to the folder containing dataset files.")
    parser.add_argument("--output_folder", type=str, required=True, help="Path to the folder where output files will be saved.")
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_args()
    model_type = args.model_type
    model_name = args.model_name
    prompts_folder = args.prompts_folder
    max_tokens = int(args.max_tokens)
    output_folder = args.output_folder
    reasoning = args.reasoning

    client = return_client(model_type)
    hf_tokenizer = AutoTokenizer.from_pretrained(TOKENIZER)

    # Create master dataset with keys being the project's name
    for prompt_method in TEMPLATE_TYPES:
        # Load all JSON files
        datasets = list(iglob(os.path.join(prompts_folder, f"**/{prompt_method}/dataset.json"), recursive=True))
        # Read the JSON files
        raw_datasets = {_beautify_project_name(dataset): read_json_file(dataset) for dataset in datasets} 
        # Execute for each noise ratio
        for nr in NOISE_RATIOS:
            # Get IQR range
            all_prompts = fetch_by_noise_ratio(raw_datasets.values(), nr)
            all_prompts = list(map(lambda x: x["prompts"], all_prompts))
            # Flatten the list of prompts
            all_prompts = [item for sublist in all_prompts for item in sublist]
            # Map prompt -> length
            print(f"Calculating IQR range for noise ratio {nr} and prompt method {prompt_method}...")
            prompt_lengths = list(map(lambda x: len(hf_tokenizer.tokenize(x)), all_prompts))
            mean, std = calculate_range(prompt_lengths)
            # lower_bound = mean - ALPHA * std
            # upper_bound = mean + ALPHA * std
            lower_bound = 0
            upper_bound = mean
            # Iterate over each prompt
            for project, dataset in tqdm(raw_datasets.items()):
                prompts = dataset[str(nr)]["prompts"]
                # Create output folder if it doesn't exist
                output_folder = os.path.join(output_folder, project, prompt_method, str(nr))
                # Check if the output folder exists. If it does, the prompts have already been processed
                if not os.path.exists(output_folder):
                    os.makedirs(output_folder)
                else:
                    print(f"Output folder {output_folder} already exists. Skipping processing for this project and noise ratio.")
                    continue
                # Prompt the model using the prompts
                for prompt in tqdm(prompts, desc=f"Processing prompts for project {project} with noise ratio {nr}"):
                    response = execute_prompt(client, hf_tokenizer, max_tokens, model_name, reasoning, prompt)
                    if response:
                        # Save the response and the original prompts and their metadata to a JSON file
                        data = {
                            'metadata': dataset[str(nr)]["metadata"], 
                            "prompts":  dataset[str(nr)]["prompts"],
                            'response': response,
                            'ground_truth': dataset[str(nr)]["ground_truth"],
                            }
                        output_path = os.path.join(output_folder, f"response.json")
                        save_to_json(data, output_path)
                    else:
                        print(f"Failed to process prompt: {prompt}")