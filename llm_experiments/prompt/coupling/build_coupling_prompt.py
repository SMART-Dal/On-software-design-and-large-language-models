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
from utils.tree_sitter_utils import remove_class_bodies
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser
from prompt.coupling.prompt_templates import RETRIEVAL_BASED_COUPLING, BINARY_BASED_COUPLING, HYBRID_PROMPT
from tqdm import tqdm
import itertools

NOISE_RATIOS = [round(i*1e-1, 1) for i in range(1, 9)]
TEMPLATES = [
    'retrieval', 
    'binary', 
    'hybrid'
    ]

def calculate_iqr(data):
    q75, q25 = np.percentile(data, [75 ,25])
    
    return q25, q75


def clean_depedency(content, parser):
    code = remove_comments_and_docstrings(content)
    code = remove_class_bodies(code, parser)

    return code

def parser_args():
    parser = argparse.ArgumentParser(description='Generate a prompt for LLM with project context, perturbed classes, dependencies, and noise.')
    parser.add_argument('--config_file', type=str, required=True, help='Path to the config file.')
    parser.add_argument('--with_iqr', action='store_true', help='Whether to use IQR to filter perturbed classes.')
    args = parser.parse_args()

    return args

def generate_none_coupled_pairs(tightly_coupeled_pairs, noise_classes):
    # The number of none coupled pairs == number of noise classes
    num_of_none_coupled_pairs = len(noise_classes)
    if num_of_none_coupled_pairs == 0:
        print("No none coupled pairs needed. Returning empty list.")
        return []
    if num_of_none_coupled_pairs == 1:
        # Randomly select a class from the tightly coupled pairs and use it to generate a noisy pair
        random_class = random.choice(tightly_coupeled_pairs)
        noise_class_name = noise_classes[0]['path'].split('/')[-1].split('.')[0]
        return [(random_class[0], noise_class_name)]
    

    noise_classes = list(map(lambda x: x['path'].split('/')[-1].split('.')[0], noise_classes))
    none_coupled_pairs = []
    all_possible_pairs = list(itertools.combinations(noise_classes, 2))
    # Shuffle the pairs
    try:
        none_coupled_pairs = random.sample(all_possible_pairs, num_of_none_coupled_pairs)
    except ValueError:
        print(f"Not enough noise classes to generate {num_of_none_coupled_pairs} none coupled pairs. Using all possible pairs.")
        none_coupled_pairs = all_possible_pairs

    return none_coupled_pairs

def main():

    arguments = parser_args()
    args = parse_yaml_config(arguments.config_file)
    epoch_time = int(time.time_ns())

    
    
    # Setup tree-sitter parser
    JAVA_LANGUAGE = Language(tsjava.language())
    parser = Parser(JAVA_LANGUAGE)

    tokenizer = Tokenizer.from_pretrained(args.model_tag)

    raw_perturbed_data = read_json_file(args.perturbed_json)
    raw_disjoint_pairs = read_json_file(args.disjoint_json)

    # Where the dataset will be stored
    dataset = {}

    # Print the experiment configuration using for loop
    print(f"Experiment configuration:")
    for key, value in vars(args).items():
        print(f"{key}: {value}")
    # In some cases, the class might be defined within another class. For instance Foo$Bar, the class Bar will be in Foo.java and not Bar.java
    print("Fixing nested class paths in the perturbed data...")
    raw_perturbed_data = {key: fix_nested_class_paths(value) for key, value in raw_perturbed_data.items()}
    # Set the IQR range based on the token length of the perturbed classes. This range will be used to select noisy classes as well.
    perturbed_data = {}
    for key, value in tqdm(raw_perturbed_data.items(), desc='Reading perturbed classes to determine IQR range'):
        full_path = os.path.join(args.perturbed_project_path, key)
        content, readable = read_file_content(full_path)
        if not readable:
            continue
        # Remove the dependency if it has no dependency chain
        new_value = []
        for v in value:
            if len(v['dependencyChain']) > 1:
                new_value.append(v)
        content = remove_comments_and_docstrings(content)
        token_count = len(tokenizer.encode(content).ids)
        perturbed_data[key] = {'content': content, 'token_count': token_count, 'dependencies': new_value}

    perturbed_classes_token_counts = [value['token_count'] for value in perturbed_data.values()]
    if arguments.with_iqr:
        # Calculate the IQR range of the perturbed classes token counts
        q25, q75 = calculate_iqr(perturbed_classes_token_counts)
        # Filter out perturbed classes based on the IQR range
        perturbed_classes = [key for key, value in perturbed_data.items() if q25 <= value['token_count'] <= q75]
        # If perturbed_classes is empty, use one perturbed class
        if not perturbed_classes:
            perturbed_classes = [list(perturbed_data.keys())[0]]
    else:
        # Use all perturbed classes
        perturbed_classes = list(perturbed_data.keys())
        q25, q75 = min(perturbed_classes_token_counts), max(perturbed_classes_token_counts)
    # Continue building the perturbed data by including the content of their dependencies and their inheritence chains
    tightly_coupeled_pairs = []
    collapsed_paths = {} # We will use this to avoid duplicate paths when picking noisy classes
    num_of_perturbed_classes = 0 # Holds the number of perturbed classes, plus the number of their dependencies, plus the number of the dependency chains of each dependency
    for key in tqdm(perturbed_classes, desc='Initializing collapsed paths with perturbed classes and their dependencies'):
        dependencies = perturbed_data[key]['dependencies']
        perturbed_class_name = key.split('/')[-1].split('.')[0]
        collapsed_paths[key] = perturbed_data[key]['content']
        for dep in dependencies:
            dep_path = os.path.join(args.perturbed_project_path, dep['dependencyClassFilePath'])
            dep_content, readable = read_file_content(dep_path)
            if not readable:
                continue
            dep_content = clean_depedency(dep_content, parser)
            collapsed_paths[dep['dependencyClassFilePath']] = dep_content
            # Interate over the dependency chain
            dependency_class_name = dep['dependencyClassName'].split('.')[-1]
            # Update ground truth
            tightly_coupeled_pairs.append((perturbed_class_name, dependency_class_name))
            for chain_entry in dep['dependencyChain']:
                chain_path = os.path.join(args.perturbed_project_path, chain_entry['filePath'])
                chain_content, readable = read_file_content(chain_path)
                if not readable:
                    continue
                if chain_entry['className'] == dependency_class_name:
                    continue
                chain_content = clean_depedency(chain_content, parser)
                collapsed_paths[chain_entry['filePath']] = chain_content
        
    num_of_perturbed_classes = len(collapsed_paths)
    noise_candidates = {}
    for pair in tqdm(raw_disjoint_pairs, desc='Collecting noise candidates from disjoint pairs'):
        left_path = pair['left']['filePath']
        right_path = pair['right']['filePath']
        if (left_path not in collapsed_paths):
            full_left_path = os.path.join(args.noisy_project_path, left_path)
            content, readable = read_file_content(full_left_path)
            if not readable:
                continue
            content = remove_comments_and_docstrings(content)
            token_count = len(tokenizer.encode(content).ids)
            if q25 <= token_count <= q75:
                lefClassName = pair['left']['className'].split('.')[-1]
                # Check if the dollar sign is in the class name, if so, it means it is an inner class
                if '$' in lefClassName:
                    lefClassName = lefClassName.split('$')[-1]
                noise_candidates[left_path] = {'content': content, 'className': lefClassName , 'token_count': token_count}
            else:
                continue
        
        if (right_path not in collapsed_paths):
            full_right_path = os.path.join(args.noisy_project_path, right_path)
            content, readable = read_file_content(full_right_path)
            if not readable:
                continue
            content = remove_comments_and_docstrings(content)
            token_count = len(tokenizer.encode(content).ids)
            if q25 <= token_count <= q75:
                rightClassName = pair['right']['className'].split('.')[-1]
                # Check if the dollar sign is in the class name, if so, it means it is an inner class
                if '$' in rightClassName:
                    rightClassName = rightClassName.split('$')[-1]
                noise_candidates[right_path] = {'content': content, 'className': rightClassName , 'token_count': token_count}
            else:
                continue
    # Revert the dictionary to a list
    noise_candidates = [{'path': k, 'content': v['content'], 'className': v['className'], 'token_count': v['token_count']} for k, v in noise_candidates.items()]
    # Sort noise candidates by token count in ascending order
    noise_candidates = sorted(noise_candidates, key=lambda x: x['token_count'])
    # Noise ratio: (normal classes) / total classes where total classes = normal classes + perturbed classes + perturbed classes's dependencies + dep_chain of each dependency
    # Based on this ratio, we will select the number of noisy classes to include in the prompt
    for template_name in TEMPLATES:
        print(f"Generating prompts for template: {template_name}")
        for noise_ratio in NOISE_RATIOS:
            n_noise_classes = int(noise_ratio * num_of_perturbed_classes / (1 - noise_ratio))
            print(f"Number of noise classes: {n_noise_classes}, Noise ratio: {noise_ratio}")
            # Select the noise_classes-th classes given that noise_candidates are sorted by token count
            noise_classes = noise_candidates[:n_noise_classes]
            # Collect classes to include in the prompt
            classes = []
            for n_class in noise_classes:
                content = n_class['content']
                path = n_class['path']
                classes.append((path, content))
            
            for path, content in collapsed_paths.items():
                classes.append((path, content))

            if template_name == 'binary':
                non_coupeled_pairs = generate_none_coupled_pairs(tightly_coupeled_pairs, noise_classes)
                all_class_pairs = non_coupeled_pairs + tightly_coupeled_pairs

            elif template_name == 'hybrid':
                # Get the first element of each class pair of tightly_coupled_pairs
                classes_under_analysis = set(pair[0] for pair in tightly_coupeled_pairs)
                classes_under_analysis = list(classes_under_analysis)
                # Get the noisy classes
                _noisy_classes = set(n_class['className'] for n_class in noise_classes)
                # Add the noisy classes to the classes under analysis
                classes_under_analysis.extend(_noisy_classes)

            # Build the groundtruth for the prompt
            if template_name == 'retrieval' or template_name == 'hybrid':
                ground_truth = deepcopy(tightly_coupeled_pairs)
                if template_name == 'hybrid':
                    non_coupled_pairs = [(_cls, None) for _cls in _noisy_classes]
                    ground_truth.extend(non_coupled_pairs)
            
            
            elif template_name == 'binary':
                print(f"Number of tightly coupled pairs: {len(tightly_coupeled_pairs)}, Number of none coupled pairs: {len(non_coupeled_pairs)}")
                ground_truth_tightly_coupeled_pairs = [ {"pair": p, "coupled": True} for p in tightly_coupeled_pairs]
                ground_truth_non_coupeled_pairs = [ {"pair": p, "coupled": False} for p in non_coupeled_pairs]
                ground_truth = ground_truth_non_coupeled_pairs + ground_truth_tightly_coupeled_pairs

            all_prompts = []
            # Generate a prompt for each shuffle
            for shuff in range(args.n_shuffles):
                # Shuffle the classes
                random.shuffle(classes)
                # Generate the prompt
                classes_str = ""
                for path, content in classes:
                    classes_str += f"{path}\n"
                    classes_str += f"{content}\n"
                    classes_str += f"{'=' * 50}\n"
                
                if template_name == 'retrieval':
                    prompt_template = RETRIEVAL_BASED_COUPLING
                    prompt = RETRIEVAL_BASED_COUPLING.format(
                        project_name=args.project_name, 
                        list_of_classes=classes_str
                        )
                elif template_name == 'binary':
                    prompt_template = BINARY_BASED_COUPLING
                    # Shuffle the class pairs
                    random.shuffle(all_class_pairs)
                    prompt = BINARY_BASED_COUPLING.format(
                            project_name=args.project_name,
                            class_pair=all_class_pairs,
                            list_of_classes=classes_str
                        )
                elif template_name == 'hybrid':
                    prompt_template = HYBRID_PROMPT
                    # Shuffle the classes
                    random.shuffle(classes_under_analysis)
                    # Generate the prompt
                    prompt = HYBRID_PROMPT.format(
                        project_name=args.project_name,
                        classes_under_analysis=classes_under_analysis,
                        list_of_classes=classes_str
                    )

                len_prompt = len(tokenizer.encode(prompt).ids)
                # Future idea: Randomly remove the body of classes in the prompt to make it more challenging
                print(f"Number of involved classes: {len(classes)}, Prompt token count: {len_prompt}, R={noise_ratio}, S={shuff}")
                all_prompts.append(prompt)
                if shuff == args.n_shuffles - 1:
                    metadata = {
                        'noise_ratio': noise_ratio,
                        'n_perturbed_classes': num_of_perturbed_classes,
                        'n_noise_classes': n_noise_classes,
                        'total_classes': len(classes),
                        'prompt_token_count': len_prompt,
                        'model_tag': args.model_tag,
                        'classes': [c[0] for c in classes],
                    }
                    noise_ratio_data = {
                        'metadata': metadata,
                        'ground_truth': ground_truth,
                        'prompts': all_prompts,
                    }

                    # Save the ground truth to the dataset
                    dataset[noise_ratio] = noise_ratio_data
        
        
        output_dir = f"{args.project_name}_{'-'.join(args.perturbation_types)}_{epoch_time}"
        output_dir = os.path.join(args.output_dir, output_dir)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        # Create a subdirectory for the current template
        output_dir = os.path.join(output_dir, template_name)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        # Include the content of the prompt template in the config file
        args.template = prompt_template
        # Copy the config file to the output directory for reproducibility
        config_file_name = os.path.basename(arguments.config_file)
        config_file_path = os.path.join(output_dir, config_file_name)
        # Save the dataset to a JSON file
        dataset_file_name = f"dataset.json"
        dataset_file_path = os.path.join(output_dir, dataset_file_name)
        save_to_json(dataset, dataset_file_path)
        # Save to YML at prompt directory
        save_config_to_yaml(args, config_file_path)
        print(f"Prompt generation completed. Output directory: {output_dir}")


        

if __name__ == "__main__":
    main()