from glob import iglob
import multiprocessing
import os
import pandas as pd
import numpy as np
import random
import uuid
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Union
from transformers import AutoTokenizer
from tqdm import tqdm
from utils.preprocessing import remove_comments_and_docstrings
from utils.io import read_json_file
import concurrent.futures # MODIFICATION: Added import for parallel processing

HELP_LEVELS = ["Binary", "Hybrid", "Retrieval"]
DISTORTION_RATIOS =  [round(i * 1e-1, 1) for i in range(1, 10)]
DISTORTION_LEVELS =  [i for i in range(1, 10)]
NUM_SIZE_BINS = 4  # For quartiles
SAMPLES_PER_CELL = 155  # The number of prompts 'k' to draw from each cell
MAX_WORKERS = multiprocessing.cpu_count() - 2

@dataclass
class CouplingPrompt:
    """Represents a final, ready-to-use coupling prompt for the LLM."""
    artifact_id: str
    prompt_text: str
    token_count: int
    help_level: str
    distortion_ratio: float
    size_bin: str
    metadata: dict
    ground_truth: list

@dataclass
class CohesionPrompt:
    """Represents a final, ready-to-use cohesion prompt for the LLM."""
    artifact_id: str
    prompt_text: str
    token_count: int
    help_level: str
    distortion_level: int
    size_bin: str
    ground_truth: str
    sourceClassName: str
    sourceClassPath: str
    sourceClassContent: str
    targetClassName: str
    targetClassPath: str
    targetClassContent: str

def _beautify_project_name(path: str):
    project_name = path.split(os.sep)[-3]
    project_name = project_name.split("_")[0]
    return project_name


def main(model_tag: str, path: str, task: str, tokenizer: AutoTokenizer):
    """Main function to execute the entire sampling pipeline."""
    print("--- Starting 3-Factor Stratified Sampling ---")

    print(f"\n[STEP 1] Gathering samples for task '{task}'...")
    if task == "coupling":
        all_artifacts = prepare_coupling_data_points(path, tokenizer)
    elif task == "cohesion":
        all_artifacts = prepare_cohesion_data_points(path, tokenizer)
    else:
        raise ValueError(f"Unknown task: {task}")

    if not all_artifacts:
        print("No artifacts were gathered. Exiting.")
        return

    print(f"-> Gathered {len(all_artifacts)} total artifacts.")

    print("\n[STEP 2 & 3] Performing global size analysis and assigning bins...")
    artifacts_df = classify_artifacts_by_size(all_artifacts)
    
    # Check if classification was successful
    if artifacts_df.empty:
        print("Artifact DataFrame is empty after classification. Exiting.")
        return
        
    print("-> Global Size Boundaries (Tokens):")
    boundaries = np.quantile(artifacts_df['token_count'], q=[i / NUM_SIZE_BINS for i in range(1, NUM_SIZE_BINS)])
    print(f"   - Q1 (25%): {boundaries[0]:.0f}")
    print(f"   - Q2 (50%): {boundaries[1]:.0f}")
    print(f"   - Q3 (75%): {boundaries[2]:.0f}")
    print("\n-> Distribution of artifacts across size bins:")
    print(artifacts_df['size_bin'].value_counts().sort_index())

    print("\n[STEP 4] Performing stratified sampling...")
    final_sampled_prompts_df = perform_stratified_sampling(artifacts_df, task)

    print("\n--- Sampling Complete ---")
    print(f"Total prompts selected: {len(final_sampled_prompts_df)}")
    if not final_sampled_prompts_df.empty:
        print("\nSample distribution across Size Bins:")
        if task == 'coupling':
        # Using crosstab for a more readable grid format
            print(pd.crosstab(
                index=[final_sampled_prompts_df.help_level, final_sampled_prompts_df.distortion_ratio],
                columns=final_sampled_prompts_df.size_bin
            ))

            print("\nTotal samples per distortion ratio for each help level:")
            print(final_sampled_prompts_df.groupby(['help_level', 'distortion_ratio']).size())
        else:
            print(pd.crosstab(
                index=[final_sampled_prompts_df.help_level, final_sampled_prompts_df.distortion_level],
                columns=final_sampled_prompts_df.size_bin
            ))

            print("\nTotal samples per distortion ratio for each help level:")
            print(final_sampled_prompts_df.groupby(['help_level', 'distortion_level']).size())   

    return final_sampled_prompts_df


def classify_artifacts_by_size(artifacts: List[Union[CouplingPrompt, CohesionPrompt]]) -> pd.DataFrame:
    """Assigns size bins based on GLOBAL quantiles."""
    if not artifacts:
        return pd.DataFrame()

    df = pd.DataFrame([asdict(a) for a in artifacts])
    bin_labels = [f"SizeBin_{i+1}" for i in range(NUM_SIZE_BINS)]
    
    # Ensure there are enough unique token counts to form quantiles
    if df['token_count'].nunique() < NUM_SIZE_BINS:
        print("WARNING: Not enough unique token values to form all quantile bins. Using fewer bins.")
        # Fallback to binning by rank if qcut fails
        df['size_bin'] = pd.cut(df['token_count'], bins=NUM_SIZE_BINS, labels=bin_labels, duplicates='drop')
    else:
        df['size_bin'] = pd.qcut(df['token_count'], q=NUM_SIZE_BINS, labels=bin_labels, duplicates='drop')
    
    return df


def perform_stratified_sampling(prompt_df: pd.DataFrame, task: str) -> pd.DataFrame:
    """Performs stratified sampling using pandas groupby."""
    if prompt_df.empty:
        return pd.DataFrame()
        
    def sample_group(group):
        n_samples = SAMPLES_PER_CELL
        if len(group) < n_samples:
            # This warning is now more informative.
            group_name = group.name
            print(f"WARNING: Cell {group_name} has only {len(group)} prompts. Required: {n_samples}. Using all available.")
            return group
        return group.sample(n=n_samples, replace=False)

    col_name = 'distortion_ratio' if task == "coupling" else 'distortion_level'
    final_sample_df = prompt_df.groupby(
        ['help_level', col_name, 'size_bin'],
        group_keys=False
    ).apply(sample_group)
    
    return final_sample_df.reset_index(drop=True)


def prepare_coupling_data_points(coupling_dir: str, tokenizer: AutoTokenizer) -> List[CouplingPrompt]:
    templates = ["binary", "hybrid", "retrieval"]
    samples = []
    for t in templates:
        datasets_path = list(iglob(os.path.join(coupling_dir, f"**/{t}/dataset.json"), recursive=True))
        raw_datasets = {_beautify_project_name(p): read_json_file(p) for p in datasets_path}
        filtered_datasets = {k: v for k, v in raw_datasets.items() if len(v['0.1']["ground_truth"]) > 0}
        for dr in DISTORTION_RATIOS:
            for project, dataset in tqdm(filtered_datasets.items()):
                prompts = dataset[str(dr)]["prompts"]
                if not dataset[str(dr)]["ground_truth"]:
                    print(f"Skipping project {project} for DR={dr} due to missing ground truth.")
                for i, p in enumerate(prompts):
                    pid = f"{project}_{t}_{str(dr)}_{i}"
                    token_count = len(tokenizer.tokenize(p))
                    p_instance = CouplingPrompt(
                        artifact_id=pid, 
                        prompt_text=p, 
                        help_level=t, 
                        distortion_ratio=dr, 
                        size_bin="", 
                        metadata=dataset[str(dr)]["metadata"],
                        ground_truth=dataset[str(dr)]["ground_truth"],
                        token_count=token_count
                        )
                    samples.append(p_instance)
    return samples


def _process_cohesion_file(args: tuple) -> List[CohesionPrompt]:
    """
    Processes a single cohesion data file. This is a top-level helper function
    designed to be called by a multiprocessing pool.
    
    Args:
        args: A tuple containing (file_path, template_name, tokenizer).
    
    Returns:
        A list of CohesionPrompt objects extracted from the file.
    """
    d_path, t, tokenizer = args
    file_samples = []

    def _create_cohesion_prompt(instruction, class_body):
        return f"""{instruction}\n ```java\n{class_body}\n```"""

    try:
        d = read_json_file(d_path)
        project_name = d_path.split(os.sep)[-2]
        
        for v in d.values():
            for i, s in enumerate(v):
                src_code = remove_comments_and_docstrings(s.get("sourceCode", ""))
                instruction = s.get("prompt", "")
                ground_turth = s.get("groundTruth", "")
                distortion_level = s.get("distortionLevel")
                
                source_class = s.get("sourceClass", {})
                target_class = s.get("targetClass", {})

                prompt = _create_cohesion_prompt(instruction, src_code)
                cid = f"{project_name}_{t}_{str(distortion_level)}_{i}"
                token_count = len(tokenizer.tokenize(prompt))

                cohesion_instance = CohesionPrompt(
                    artifact_id=cid,
                    prompt_text=prompt,
                    token_count=token_count,
                    help_level=t,
                    distortion_level=distortion_level,
                    size_bin="",
                    ground_truth=ground_turth,
                    sourceClassName=source_class.get("className", ""),
                    sourceClassContent=source_class.get("content", ""),
                    sourceClassPath=source_class.get("filePath", ""),
                    targetClassName=target_class.get("className", ""),
                    targetClassPath=target_class.get("filePath", ""),
                    targetClassContent=target_class.get("content", "")
                )
                file_samples.append(cohesion_instance)
    except Exception as e:
        print(f"Error processing file {d_path}: {e}")
        return []  # Return an empty list on error to not halt the entire process
        
    return file_samples


def prepare_cohesion_data_points(cohesion_dir: str, tokenizer: AutoTokenizer) -> List[CohesionPrompt]:
    """
    Gathers and prepares cohesion data points by processing JSON files in parallel.
    """
    templates = ["binary", "hybrid", "retrieval"]
    all_samples = []

    # 1. Collect all tasks to be processed. Each task is a tuple of arguments for the worker function.
    tasks = []
    for t in templates:
        dataset_paths = iglob(os.path.join(cohesion_dir, "**", f"{t}.json"), recursive=True)
        for d_path in dataset_paths:
            tasks.append((d_path, t, tokenizer))

    if not tasks:
        print("Warning: No cohesion data files found to process.")
        return []

    with concurrent.futures.ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # executor.map applies the worker function to each item in the tasks list.
        # It returns an iterator for the results in the order the tasks were submitted.
        results_iterator = executor.map(_process_cohesion_file, tasks)
        
        # Use tqdm to create a progress bar for the parallel execution.
        for file_samples in tqdm(results_iterator, total=len(tasks), desc="Processing cohesion files"):
            if file_samples:
                all_samples.extend(file_samples)
    
    return all_samples


if __name__ == '__main__':
    model_tag = "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B"
    data_path = ""
    task = "cohesion" # or "coupling"
    code_transformation = "gc"
    tokenizer = AutoTokenizer.from_pretrained(model_tag)

    final_sample = main(
        model_tag=model_tag,
        path=data_path,
        task=task,
        tokenizer=tokenizer
    )
    
    if final_sample is not None and not final_sample.empty:
        print("\n--- First 5 sampled prompts: ---")
        # Displaying relevant columns for brevity
        print(final_sample.head())

    # Save samples as pickled file
    final_sample.to_pickle(f"{task}_{code_transformation}.pkl")