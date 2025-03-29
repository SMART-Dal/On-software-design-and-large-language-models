import argparse
import os
import random
import numpy as np
from tokenizers import Tokenizer
from utils.io import read_json_file, read_file_content, save_to_json
from utils.paths import get_absolute_file_paths
from utils.preprocessing import remove_comments_and_docstrings
from utils.tree_sitter_utils import remove_class_bodies
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser
from tqdm import tqdm

NOISE_RATIOS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

def calculate_iqr(data):
    q75, q25 = np.percentile(data, [75 ,25])
    
    return q25, q75

def prompt_template(project_name, project_readme, list_of_classes):
    return f"""
You are given a Java project named {project_name}. Below is the content of its README file to provide context about its purpose:

## README:
{project_readme}

## Classes:
{list_of_classes}

## Task:
Your task is to analyze the dependencies between these classes and identify any tightly coupled classes. Tightly coupled classes are those with strong dependencies on each other, making them difficult to modify or test independently. 

Please provide a list of tuples of classes that you think are tightly coupled. For example, if you think a Java class A is tightly coupled with classes B and C, you should provide the following tuple: [ [A, B] [A, C] ].

Note that you should NOT consider primitive types (e.g., int, float) as classes.

## Response Format:
Please provide your response in the following format:
[
    [Class1, Class2],
    [Class1, Class3],
    [Class5, Class8]
    ...
]
In this case, Class1 is tightly coupled with Class2 and Class3, and Class5 is tightly coupled with Class8. Note that these are arbitrary examples and may not be true for the given project.
If no classes are tightly coupled, please provide an empty list [].
"""

def clean_depedency(content, parser):
    code = remove_comments_and_docstrings(content)
    code = remove_class_bodies(code, parser)

    return code

def main():
    parser = argparse.ArgumentParser(description='Generate a prompt for LLM with project context, perturbed classes, dependencies, and noise.')
    parser.add_argument('--project_name', required=True, help='Name of the Java project')
    parser.add_argument('--perturbed_project_path', required=True, help='Path to the perturbed classes')
    parser.add_argument('--readme_path', required=True, help='Path to the README file of the project')
    parser.add_argument('--disjoint_json', required=True, help='Path to JSON file containing disjoint class pairs')
    parser.add_argument('--perturbed_json', required=True, help='Path to JSON file containing perturbed classes and their dependencies')
    parser.add_argument('--output_prompt', required=True, help='Path to output the generated prompt files')
    parser.add_argument('--seed', type=int, default=42, help='Random seed for reproducibility')
    parser.add_argument('--model_tag', required=True, help='Huggingface model tag for the LLM')
    parser.add_argument('--n_shuffles', type=int, default=1, help='Number of shuffles, i.e., different prompts to generate')
    parser.add_argument('--perturbation_types', nargs='+', default=['did', 'dal', 'gc', 'feii'], help='Types of perturbations that were applied to the classes')
    args = parser.parse_args()

    # Setup tree-sitter parser
    JAVA_LANGUAGE = Language(tsjava.language())
    parser = Parser(JAVA_LANGUAGE)

    tokenizer = Tokenizer.from_pretrained(args.model_tag)

    raw_perturbed_data = read_json_file(args.perturbed_json)
    raw_disjoint_pairs = read_json_file(args.disjoint_json)

    # Set the IQR range based on the token length of the perturbed classes. This range will be used to select noisy classes as well.
    perturbed_data = {}
    for key, value in tqdm(raw_perturbed_data.items(), desc='Reading perturbed classes to determine IQR range'):
        full_path = os.path.join(args.perturbed_project_path, key)
        content, readable = read_file_content(full_path)
        if not readable:
            continue
        content = remove_comments_and_docstrings(content)
        token_count = len(tokenizer.encode(content).ids)
        perturbed_data[key] = {'content': content, 'token_count': token_count, 'dependencies': value}

    perturbed_classes_token_counts = [value['token_count'] for value in perturbed_data.values()]
    q25, q75 = calculate_iqr(perturbed_classes_token_counts)
    # Filter out perturbed classes based on the IQR range
    perturbed_classes = [key for key, value in perturbed_data.items() if q25 <= value['token_count'] <= q75]
    # Continue building the perturbed data by including the content of their dependencies and their inheritence chains
    ground_truth = []
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
            ground_truth.append((perturbed_class_name, dependency_class_name))
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
    noise_candidates = []
    for pair in tqdm(raw_disjoint_pairs, desc='Collecting noise candidates from disjoint pairs'):
        left_path = pair['left']['filePath']
        right_path = pair['right']['filePath']
        if (left_path not in collapsed_paths):
            full_left_path = os.path.join(args.perturbed_project_path, left_path)
            content, readable = read_file_content(full_left_path)
            if not readable:
                continue
            content = remove_comments_and_docstrings(content)
            token_count = len(tokenizer.encode(content).ids)
            if q25 <= token_count <= q75:
                noise_candidates.append({'content': content, 'path': left_path, 'token_count': token_count})
            else:
                continue
        
        if (right_path not in collapsed_paths):
            full_right_path = os.path.join(args.perturbed_project_path, right_path)
            content, readable = read_file_content(full_right_path)
            if not readable:
                continue
            content = remove_comments_and_docstrings(content)
            token_count = len(tokenizer.encode(content).ids)
            if q25 <= token_count <= q75:
                noise_candidates.append({'content': content, 'path': right_path, 'token_count': token_count})
            else:
                continue
    # Sort noise candidates by token count in ascending order
    noise_candidates = sorted(noise_candidates, key=lambda x: x['token_count'])
    # Noise ratio: (normal classes) / total classes where total classes = normal classes + perturbed classes + perturbed classes's dependencies + dep_chain of each dependency
    # Based on this ratio, we will select the number of noisy classes to include in the prompt
    for noise_ratio in NOISE_RATIOS:
        n_noise_classes = int(noise_ratio * num_of_perturbed_classes / (1 - noise_ratio))
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
        # Generate a prompt for each shuffle
        for i in range(args.n_shuffles):
            # Shuffle the classes
            random.shuffle(classes)
            # Generate the prompt
            classes_str = ""
            for path, content in classes:
                classes_str += f"{path}\n"
                classes_str += f"{content}\n"
                classes_str += f"{'=' * 50}\n"
            
            readme_content, _ = read_file_content(args.readme_path)
            prompt = prompt_template(args.project_name, readme_content, classes_str)
            len_prompt = len(tokenizer.encode(prompt).ids)
            # Future idea: Randomly remove the body of classes in the prompt to make it more challenging
            print(f"Number of involved classes: {len(classes)}, Prompt token count: {len_prompt}, R={noise_ratio}, S={i}")
            prompt_file_name = f"{args.project_name}_{'-'.join(args.perturbation_types)}_{noise_ratio}_{i}.txt"
            prompt_file_path = os.path.join(args.output_prompt, prompt_file_name)
            with open(prompt_file_path, 'w') as f:
                f.write(prompt)
            # Save metadata during last shuffle
            if i == args.n_shuffles - 1:
                metadata = {
                    'noise_ratio': noise_ratio,
                    'n_perturbed_classes': num_of_perturbed_classes,
                    'n_noise_classes': n_noise_classes,
                    'total_classes': len(classes),
                    'prompt_token_count': len_prompt,
                    'model_tag': args.model_tag,
                    'classes': [c[0] for c in classes],
                }
                metadata_file_name = f"{args.project_name}_{'-'.join(args.perturbation_types)}_{noise_ratio}_metadata.json"
                metadata_file_path = os.path.join(args.output_prompt, metadata_file_name)
                save_to_json(metadata, metadata_file_path)
    # Save ground truth
    ground_truth_file_name = f"{args.project_name}_{'-'.join(args.perturbation_types)}_ground_truth.json"
    ground_truth_file_path = os.path.join(args.output_prompt, ground_truth_file_name)
    save_to_json(ground_truth, ground_truth_file_path)

if __name__ == "__main__":
    main()