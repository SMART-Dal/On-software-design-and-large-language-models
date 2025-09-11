import os
import time
from glob import iglob
from argparse import ArgumentParser
from typing import List, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing
import pandas as pd
import numpy as np
from tqdm import tqdm
from openai.types.chat import ChatCompletion
from transformers import AutoTokenizer
from .model_map import MODELS_INFO


import requests, json, random

prng = np.random.RandomState(42)

URL = "https://openrouter.ai/api/v1/chat/completions"
API_KEY = os.environ.get("OPENROUTER_API_KEY")
HEADERS = {
  "Authorization": f"Bearer {API_KEY}",
  "Content-Type": "application/json"
}
TEMPEATURE = 0
ALPHA = 1
TEMPLATE_TYPES = [
    # "binary", "hybrid",
     "retrieval"]
NOISE_RATIOS = [round(i*1e-1, 1) for i in range(1, 10)]
# Set a reasonable number of parallel workers
MAX_WORKERS = multiprocessing.cpu_count() - 2
BUFFER = 2024  # Buffer for the model context length
CTX = 128_000  # Context length for the model.
SAMPLE_SIZE = 450  # Number of samples to process in each nosie ratio.


def calculate_range(data):
    mean, std = np.mean(data), np.std(data)
    return mean, std

def execute_prompt(tokenizer: AutoTokenizer, model_name: str, prompt: str) -> Union[str, List[str], ChatCompletion]:
    try:
        payload = {
                "model": model_name,
                "messages": [
                    {
                    "role": "user",
                    "content": prompt
                    }
                ]
                }
        params = {"temperature": TEMPEATURE}
        response = requests.post(URL, headers=HEADERS, json=payload, params=params)
        parsed_response = response.json()
        content =parsed_response.get('choices', [{}])[0].get('message', {}).get('content', '')
        reasoning_content = parsed_response.get('choices', [{}])[0].get('message', {}).get('reasoning', '')
        finish_reason = parsed_response.get('choices', [{}])[0].get('finish_reason', None)
        native_finish_reason = parsed_response.get('choices', [{}])[0].get('native_finish_reason', None)            

        return {
            'answer': content,
            'reasoning': reasoning_content,
            'openrouter_model': model_name,
            'hf_slug': tokenizer.name_or_path,
            'finish_reason': finish_reason,
            'native_finish_reason': native_finish_reason,
        }
        
    
    except Exception as e:

        return {'error': str(e), 'prompt': prompt}
    

def run_experiment_in_parallel(
    sampled_df: pd.DataFrame,
    tokenizer: AutoTokenizer,
    model_name: str,
    ctx_len: int,
    output_path: str,
    max_workers: int = 10
) -> None:
    """
    Executes prompts from a DataFrame in parallel, appends the results to the original
    row data, and saves everything to a JSON file.
    """
    print(f"--- Starting parallel execution for {len(sampled_df)} prompts ---")
    print(f"Using model: {model_name}")
    print(f"Max workers: {max_workers}")

    all_results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # The future is now mapped to the original row dictionary
        futures = {
            executor.submit(
                execute_prompt,
                tokenizer,
                model_name,
                row['prompt_text']
            ): row.to_dict() for index, row in sampled_df.iterrows()
        }

        for future in tqdm(as_completed(futures), total=len(futures), desc="Executing Prompts"):
            original_row_data = futures[future]
            try:
                model_response = future.result()
                original_row_data.update(model_response)
                all_results.append(original_row_data)

            except Exception as e:
                # This catches exceptions from the future itself
                print(f"A critical error occurred for artifact {original_row_data.get('artifact_id')}: {e}")
                original_row_data.update({
                    'answer': None,
                    'reasoning': f"CRITICAL_ERROR: {str(e)}"
                })
                all_results.append(original_row_data)

    print(f"\n--- Execution Complete. Saving {len(all_results)} enriched results to {output_path} ---")

    # Save the list of enriched dictionaries to a JSON file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print("--- Done. ---")

def parse_args():
    parser = ArgumentParser(description="Parse model type and API key.")
    parser.add_argument("--provider", type=str, required=True, help="Provider to use.", choices=["openai", "deepseek", "together_ai", "openrouter"])
    parser.add_argument("--reasoning", action="store_true", help="Indicate whether this is a reasoning model or not.")
    parser.add_argument("--model_name", type=str, required=True, help="Name of the model to use.")
    parser.add_argument("--prompts_file", type=str, required=True, help="Path to the pickled dataset file.")
    parser.add_argument("--output_folder", type=str, required=True, help="Path to save the results.")
    args = parser.parse_args()
    return args



if __name__ == "__main__":
    args = parse_args()
    openrouter_model = MODELS_INFO[args.model_name]["openrouter_model"]
    hf_slug = MODELS_INFO[args.model_name]["hf_slug"]
    hf_tokenizer = AutoTokenizer.from_pretrained(hf_slug)
    
    try:
        sampled_prompts_df = pd.read_pickle(args.prompts_file)
    except FileNotFoundError:
        print(f"Error: Input file not found at {args.prompts_file}")
        exit(1)
     
    print(f"Loaded {len(sampled_prompts_df)} prompts for the experiment from '{args.prompts_file}'.")
    # Create folder for the current model
    model_name = openrouter_model.split("/")[-1]
    output_path = os.path.join(args.output_folder, model_name)
    os.makedirs(output_path, exist_ok=True)
    results_file = os.path.join(output_path, "results.json")
    # --- Run the experiment ---
    run_experiment_in_parallel(
        sampled_df=sampled_prompts_df,
        tokenizer=hf_tokenizer,
        model_name=openrouter_model,
        ctx_len=CTX,
        output_path=results_file,
        max_workers=MAX_WORKERS
    )
