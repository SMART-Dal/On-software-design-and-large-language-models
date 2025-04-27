import time
from openai import OpenAI
from argparse import ArgumentParser
from typing import List, Union
from utils.io import get_all_files, read_file_content, save_to_json
from tqdm import tqdm
import os

MAX_TOKENS = 8_192

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
    else:
        raise ValueError("Unsupported model type. Supported types are: openai, deepseek.")
    
    return client

def execute_prompt(client: OpenAI, model_name: str, reasoning: bool, prompt: str) -> Union[str, List[str]]:
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=MAX_TOKENS,
        )
        if reasoning:
            reasoning_content = response.choices[0].message.reasoning_content
        
        content = response.choices[0].message.content

        return {'cot': reasoning_content, 'answer': content} if reasoning else {'answer': content}
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

    client = return_client(model_type)
    reasoning = True if args.reasoning else False

    # Read prompts from the prompts_folder
    prompts = get_all_files(prompts_folder)
    pbar = tqdm(prompts, desc="Processing prompts", unit="file")
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