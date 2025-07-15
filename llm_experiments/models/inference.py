import time
from openai import OpenAI
from openai.types.chat import ChatCompletion
from argparse import ArgumentParser
from typing import List, Union
from utils.io import get_all_files, read_file_content, save_to_json
from tqdm import tqdm
from transformers import AutoTokenizer
import os

MAX_TOKENS = 8_192
TEMPEATURE = 0 # Based on the recommendation of: https://api-docs.deepseek.com/quick_start/parameter_settings

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
    parser.add_argument("--model_type", type=str, required=True, help="Type of model to use (openai or deepseek).", choices=["openai", "deepseek", "together_ai"])
    parser.add_argument("--reasoning", action="store_true", help="Indicate whether this is a reasoning model or not.")
    parser.add_argument("--model_name", type=str, required=True, help="Name of the model to use. Example: gpt-3.5-turbo, deepseek-reaonser.")
    parser.add_argument("--prompts_folder", type=str, required=True, help="Path to the folder containing prompt files.")
    parser.add_argument("--output_folder", type=str, required=True, help="Path to the folder where output files will be saved.")
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_args()
    model_type = args.model_type
    model_name = args.model_name
    prompts_folder = args.prompts_folder
    output_folder = args.output_folder
    # Extract the folder name from the prompts_folder and create it inside the output_folder
    basename = os.path.basename(prompts_folder)
    output_folder = os.path.join(output_folder, basename)
    # Create the output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)

    client = return_client(model_type)
    reasoning = True if args.reasoning else False

    # Read prompts from the prompts_folder
    prompts = get_all_files(prompts_folder)
    # Only keep txt files
    prompts = [p for p in prompts if p.endswith(".txt")]
    # Filter out already processed files
    filtered_prompts = [p for p in prompts if not is_already_processed(output_folder, p)]
    print(f"Found {len(filtered_prompts)} prompts to process out of total {len(prompts)}.")
    pbar = tqdm(filtered_prompts, desc="Processing prompts", unit="file")
    for p_path in pbar:
        prompt_name = os.path.basename(p_path)
        prompt_content, _ = read_file_content(p_path)
        
        pbar.set_description(f"Processing {prompt_name}")
        # Execute the prompt
        response = execute_prompt(client, model_name, reasoning, prompt_content)
        # Save the response to the output folder
        output_file = os.path.join(output_folder, f"{prompt_name}_response.json")
        save_to_json(response, output_file)
        print(f"Response for {prompt_name} saved to {output_file}")