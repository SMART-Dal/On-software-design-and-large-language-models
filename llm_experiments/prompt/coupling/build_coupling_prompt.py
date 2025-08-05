import argparse
from copy import deepcopy
import os
import random
import time
import numpy as np
from tokenizers import Tokenizer
from utils.io import read_json_file, read_file_content, save_config_to_yaml, save_to_json, parse_yaml_config
from utils.paths import get_absolute_file_paths
from utils.preprocessing import remove_comments_and_docstrings, fix_nested_class_paths
from utils.tree_sitter_utils import remove_class_bodies, remove_method_bodies
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser
from prompt.coupling.prompt_templates import RETRIEVAL_BASED_COUPLING, BINARY_BASED_COUPLING, HYBRID_PROMPT
from tqdm import tqdm
import itertools

# --- Constants ---
ALPHA = 0.5
NOISE_RATIOS = [round(i * 1e-1, 1) for i in range(1, 9)]
TEMPLATES = [
    'retrieval',
    'binary',
    'hybrid'
]

# --- Helper Functions (Unchanged) ---
def calculate_range(data):
    """Calculates the mean and standard deviation of a list of numbers."""
    mean = np.mean(data)
    std = np.std(data)
    return mean, std

def clean_dependency(content, parser, _remove_method_bodies=True):
    """Cleans the java code by removing comments, docstrings, and optionally method/class bodies."""
    code = remove_comments_and_docstrings(content)
    if _remove_method_bodies:
        code = remove_method_bodies(code, parser, excluded_methods={"createInstance"})
    else:
        code = remove_class_bodies(code, parser)
    return code

def generate_none_coupled_pairs(tightly_coupled_pairs, noise_classes):
    """Generates pairs of classes that are not coupled."""
    num_of_none_coupled_pairs = len(noise_classes)
    if num_of_none_coupled_pairs == 0:
        return []

    # Use the pre-processed 'className' field
    noise_class_names = [n['className'].split('.')[-1].split('$')[-1] for n in noise_classes]
    
    if num_of_none_coupled_pairs == 1:
        # Note: This edge case logic is still questionable (see below)
        random_class = random.choice(tightly_coupled_pairs)
        return [(random_class[0], noise_class_names[0])]

    all_possible_pairs = list(itertools.combinations(noise_class_names, 2))
    
    try:
        none_coupled_pairs = random.sample(all_possible_pairs, num_of_none_coupled_pairs)
    except ValueError:
        print(f"Warning: Not enough noise classes to generate {num_of_none_coupled_pairs} unique non-coupled pairs. Using all possible pairs.")
        none_coupled_pairs = all_possible_pairs
        
    return none_coupled_pairs

# --- Extracted Functions ---

def setup():
    """Parses command-line arguments, loads YAML config, and initializes parser and tokenizer."""
    parser = argparse.ArgumentParser(description='Generate a prompt for LLM with project context.')
    parser.add_argument('--config_file', type=str, required=True, help='Path to the config file.')
    parser.add_argument('--with_iqr', action='store_true', help='Whether to use IQR to filter perturbed classes.')
    parser.add_argument('--rm_bodies', action='store_true', help='Whether to remove method bodies (not constructor).')
    
    arguments = parser.parse_args()
    args = parse_yaml_config(arguments.config_file)
    
    print("Experiment configuration:")
    for key, value in vars(args).items():
        print(f"{key}: {value}")
        
    # Setup tree-sitter parser
    java_language = Language(tsjava.language())
    ts_parser = Parser(java_language)
    
    tokenizer = Tokenizer.from_pretrained(args.model_tag)
    
    return arguments, args, ts_parser, tokenizer

def load_and_prepare_data(args):
    """Loads raw perturbed and disjoint pair data and fixes nested class paths."""
    raw_perturbed_data = read_json_file(args.perturbed_json)
    raw_disjoint_pairs = read_json_file(args.disjoint_json)

    print("Fixing nested class paths...")
    raw_perturbed_data = {key: fix_nested_class_paths(value) for key, value in raw_perturbed_data.items()}
    raw_disjoint_pairs = fix_nested_class_paths(raw_disjoint_pairs)
    
    return raw_perturbed_data, raw_disjoint_pairs

def filter_perturbed_classes(raw_data, args, parser, tokenizer, rm_bodies, with_iqr):
    """Processes perturbed classes, filters them based on IQR if enabled."""
    perturbed_data = {}
    for key, value in tqdm(raw_data.items(), desc='Processing perturbed classes'):
        full_path = os.path.join(args.perturbed_project_path, key)
        content, readable = read_file_content(full_path)
        if not readable:
            continue
        
        new_value = [v for v in value if len(v['dependencyChain']) > 1]
        content = clean_dependency(content, parser, _remove_method_bodies=rm_bodies)
        token_count = len(tokenizer.encode(content).ids)
        perturbed_data[key] = {'content': content, 'token_count': token_count, 'dependencies': new_value}

    token_counts = [value['token_count'] for value in perturbed_data.values()]
    
    if with_iqr and token_counts:
        print("Calculating and applying IQR filter for perturbed classes...")
        mean, std = calculate_range(token_counts)
        lower_bound = mean - ALPHA * std
        upper_bound = mean + ALPHA * std
        filtered_keys = [key for key, value in perturbed_data.items() if lower_bound <= value['token_count'] <= upper_bound]
        if not filtered_keys: # Fallback if filter is too aggressive
             filtered_keys = list(perturbed_data.keys())
    else:
        filtered_keys = list(perturbed_data.keys())
        
    return filtered_keys, perturbed_data

def build_dependency_context(class_keys, data, args, parser, rm_bodies):
    """Builds a map of all relevant class contents and identifies tightly coupled pairs."""
    collapsed_paths = {}
    tightly_coupled_pairs = []
    
    for key in tqdm(class_keys, desc='Building dependency context'):
        dependencies = data[key]['dependencies']
        perturbed_class_name = key.split('/')[-1].split('.')[0]
        collapsed_paths[key] = data[key]['content']

        for dep in dependencies:
            dep_path = os.path.join(args.perturbed_project_path, dep['dependencyClassFilePath'])
            dep_content, readable = read_file_content(dep_path)
            if not readable:
                continue
            
            dep_content = clean_dependency(dep_content, parser, _remove_method_bodies=rm_bodies)
            collapsed_paths[dep['dependencyClassFilePath']] = dep_content
            
            dependency_class_name = dep['dependencyClassName'].split('.')[-1]
            tightly_coupled_pairs.append((perturbed_class_name, dependency_class_name))

            for chain_entry in dep['dependencyChain']:
                if chain_entry['className'] == dependency_class_name:
                    continue
                chain_path = os.path.join(args.perturbed_project_path, chain_entry['filePath'])
                chain_content, readable = read_file_content(chain_path)
                if readable:
                    chain_content = clean_dependency(chain_content, parser, _remove_method_bodies=rm_bodies)
                    collapsed_paths[chain_entry['filePath']] = chain_content
                    
    return collapsed_paths, tightly_coupled_pairs

def collect_and_filter_noise_candidates(disjoint_pairs, existing_paths, args, parser, tokenizer, rm_bodies, with_iqr):
    """Collects and filters noise candidates from disjoint pairs."""
    noise_candidates = {}
    
    for pair in tqdm(disjoint_pairs, desc='Collecting noise candidates'):
        for item in [pair['left'], pair['right']]:
            path = item['filePath']
            if path not in existing_paths:
                full_path = os.path.join(args.noisy_project_path, path)
                content, readable = read_file_content(full_path)
                if readable:
                    content = clean_dependency(content, parser, _remove_method_bodies=rm_bodies)
                    token_count = len(tokenizer.encode(content).ids)
                    class_name = item['className'].split('.')[-1].replace('$', '.')
                    noise_candidates[path] = {'content': content, 'className': class_name, 'token_count': token_count}

    candidate_list = [{'path': k, **v} for k, v in noise_candidates.items()]
    token_counts = [n['token_count'] for n in candidate_list]

    if with_iqr and token_counts:
        print("Calculating and applying IQR filter for noise candidates...")
        mean, std = calculate_range(token_counts)
        lower_bound = mean - ALPHA * std
        upper_bound = mean + ALPHA * std
        candidate_list = [n for n in candidate_list if lower_bound <= n['token_count'] <= upper_bound]

    print(f"Number of noise candidates after filtering: {len(candidate_list)}")
    return sorted(candidate_list, key=lambda x: x['token_count'])

def generate_and_save_prompts(template_name, args, arguments, epoch_time, num_perturbed_classes, collapsed_paths, tightly_coupled_pairs, noise_candidates, tokenizer):
    """Generates and saves prompts for a given template across all noise ratios."""
    dataset = {}
    prompt_template_content = ""

    for noise_ratio in NOISE_RATIOS:
        n_noise_classes = int(noise_ratio * num_perturbed_classes / (1 - noise_ratio))
        selected_noise = noise_candidates[:n_noise_classes]
        
        # Combine perturbed context with noise
        classes = list(collapsed_paths.items()) + [(n['path'], n['content']) for n in selected_noise]
        
        # Prepare template-specific data
        non_coupled_pairs = []
        classes_under_analysis = []
        if template_name == 'binary':
            non_coupled_pairs = generate_none_coupled_pairs(tightly_coupled_pairs, selected_noise)
        elif template_name == 'hybrid':
            classes_under_analysis = list(set(pair[0] for pair in tightly_coupled_pairs))
            noisy_class_names = [n['className'] for n in selected_noise]
            classes_under_analysis.extend(noisy_class_names)

        # Build ground truth
        if template_name in ['retrieval', 'hybrid']:
            ground_truth = deepcopy(tightly_coupled_pairs)
            if template_name == 'hybrid':
                ground_truth.extend([(cls, None) for cls in noisy_class_names])
        else: # binary
            ground_truth = [{"pair": p, "coupled": True} for p in tightly_coupled_pairs]
            ground_truth.extend([{"pair": p, "coupled": False} for p in non_coupled_pairs])

        all_prompts = []
        for shuff in range(args.n_shuffles):
            random.shuffle(classes)
            classes_str = "".join(f"{path}\n{content}\n{'=' * 50}\n" for path, content in classes)
            
            # Format the prompt
            if template_name == 'retrieval':
                prompt_template_content = RETRIEVAL_BASED_COUPLING
                prompt = prompt_template_content.format(project_name=args.project_name, list_of_classes=classes_str)
            elif template_name == 'binary':
                prompt_template_content = BINARY_BASED_COUPLING
                all_class_pairs = non_coupled_pairs + tightly_coupled_pairs
                random.shuffle(all_class_pairs)
                prompt = prompt_template_content.format(project_name=args.project_name, class_pair=all_class_pairs, list_of_classes=classes_str)
            else: # hybrid
                prompt_template_content = HYBRID_PROMPT
                random.shuffle(classes_under_analysis)
                prompt = prompt_template_content.format(project_name=args.project_name, classes_under_analysis=classes_under_analysis, list_of_classes=classes_str)
            all_prompts.append(prompt)

        # Create metadata and store results for this noise ratio
        len_prompt = len(tokenizer.encode(all_prompts[0]).ids)
        print(f"R={noise_ratio}: Total Classes={len(classes)}, Perturbed Context={num_perturbed_classes}, Noise={len(selected_noise)}, Token Count={len_prompt}")
        
        metadata = {
            'noise_ratio': noise_ratio, 'n_perturbed_classes': num_perturbed_classes,
            'n_noise_classes': n_noise_classes, 'total_classes': len(classes),
            'prompt_token_count': len_prompt, 'model_tag': args.model_tag,
            'perturbed_data_file': args.perturbed_json,
            'disjoint_data_file': args.disjoint_json,
            'classes': [c[0] for c in classes]
        }
        dataset[noise_ratio] = {'metadata': metadata, 'ground_truth': ground_truth, 'prompts': all_prompts}

    # Save all artifacts for this template
    output_dir = os.path.join(args.output_dir, f"{args.project_name}_{'-'.join(args.perturbation_types)}_{epoch_time}", template_name)
    os.makedirs(output_dir, exist_ok=True)
    
    save_to_json(dataset, os.path.join(output_dir, "dataset.json"))
    
    args.template = prompt_template_content
    save_config_to_yaml(args, os.path.join(output_dir, os.path.basename(arguments.config_file)))
    
    print(f"Prompt generation completed for template '{template_name}'. Output directory: {output_dir}")

# --- Main Orchestrator ---
def main():
    """Main function to orchestrate the prompt generation process."""
    arguments, args, parser, tokenizer = setup()
    epoch_time = int(time.time_ns())

    raw_perturbed_data, raw_disjoint_pairs = load_and_prepare_data(args)

    perturbed_class_keys, perturbed_data = filter_perturbed_classes(
        raw_perturbed_data, args, parser, tokenizer, arguments.rm_bodies, arguments.with_iqr
    )

    collapsed_paths, tightly_coupled_pairs = build_dependency_context(
        perturbed_class_keys, perturbed_data, args, parser, arguments.rm_bodies
    )
    
    noise_candidates = collect_and_filter_noise_candidates(
        raw_disjoint_pairs, collapsed_paths, args, parser, tokenizer, arguments.rm_bodies, arguments.with_iqr
    )
    
    for template_name in TEMPLATES:
        generate_and_save_prompts(
            template_name=template_name,
            args=args,
            arguments=arguments,
            epoch_time=epoch_time,
            num_perturbed_classes=len(collapsed_paths),
            collapsed_paths=deepcopy(collapsed_paths),
            tightly_coupled_pairs=deepcopy(tightly_coupled_pairs),
            noise_candidates=noise_candidates,
            tokenizer=tokenizer
        )

if __name__ == "__main__":
    main()