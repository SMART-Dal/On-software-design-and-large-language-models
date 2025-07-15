import argparse
import os
import random
import time
import shutil
import numpy as np
from tokenizers import Tokenizer
from utils.io import read_json_file, read_file_content, save_config_to_yaml, save_to_json, parse_yaml_config
from utils.paths import get_absolute_file_paths
from utils.preprocessing import remove_comments_and_docstrings
from utils.tree_sitter_utils import remove_class_bodies
import tree_sitter_java as tsjava
from tree_sitter import Language, Parser
from prompt.prompt_templates import RETRIEVAL_BASED_COUPLING, BINARY_BASED_COUPLING, HYBRID_PROMPT
from tqdm import tqdm

NOISE_RATIOS = [round(i*1e-1, 1) for i in range(1, 9)]

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
    args = parser.parse_args()

    return args

def generate_loosely_coupled_pairs(noise_ratio, tightly_coupeled_pairs, noise_classes):
    # The distribution of "labels" where 0 refers to not coupled and 1 refers to coupled
    # is determined by the same noise ratio. In other words, the dataset should be composed 
    # of noise_ratio of 0s and (1 - noise_ratio) of 1s.
    # First, we determine the number of loosely coupled classes that can be included in the prompt.
    # tightly_coupeled_pairs currently holds the pairs of classes that are tightly coupled.
    num_of_loosely_coupled_pairs = int(( noise_ratio * len(tightly_coupeled_pairs) )/ (1-noise_ratio) )
    # If the number of the needed loosely coupled classes is less than n_noise_classes X n_noise_classes
    # Then we can create samples from the noise_classes X tightly_coupeled_pairs space.
    loosely_coupled_pairs_indices = list(range(len(noise_classes)))
    # Shuffle the indices
    random.shuffle(loosely_coupled_pairs_indices)
    loosely_coupled_pairs = []
    for i in range(0, len(loosely_coupled_pairs_indices), 2):
        if len(loosely_coupled_pairs) >= num_of_loosely_coupled_pairs: 
            break
        # Add the pair to the loosely coupled pairs
        x, y = loosely_coupled_pairs_indices[i], loosely_coupled_pairs_indices[i+1]
        left_class = noise_classes[x]['path'].split('/')[-1].split('.')[0]
        right_class = noise_classes[y]['path'].split('/')[-1].split('.')[0]
        loosely_coupled_pairs.append((left_class, right_class))
    # Check if we reached the number of loosely coupled pairs that is needed. If
    # not we can create ones by mixing loosely coupled pairs with tightly coupled pairs as follow
    # [noisy_class1, perturbed_class1], [noisy_class2, perturbed_class2] ect until we reach the number of loosely coupled pairs
    # # that is needed.
    if len(loosely_coupled_pairs) < num_of_loosely_coupled_pairs:
        for ns in noise_classes:
            # Get the noisy class and the perturbed class
            noisy_class = ns['path'].split('/')[-1].split('.')[0]
            for p in tightly_coupeled_pairs:
                # Check if the pair is already in the loosely coupled pairs
                if (noisy_class, p[0]) in loosely_coupled_pairs or (p[0], noisy_class) in loosely_coupled_pairs:
                    continue
                # Add the pair to the loosely coupled pairs
                loosely_coupled_pairs.append((noisy_class, p[0]))
                if len(loosely_coupled_pairs) >= num_of_loosely_coupled_pairs:
                    break
            if len(loosely_coupled_pairs) >= num_of_loosely_coupled_pairs:
                break

    return loosely_coupled_pairs

def main():


    arguments = parser_args()
    args = parse_yaml_config(arguments.config_file)
    epoch_time = int(time.time_ns())
    output_dir = f"{args.project_name}_{'-'.join(args.perturbation_types)}_{args.prompt_template}_{epoch_time}"
    output_dir = os.path.join(args.output_dir, output_dir)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Setup tree-sitter parser
    JAVA_LANGUAGE = Language(tsjava.language())
    parser = Parser(JAVA_LANGUAGE)

    tokenizer = Tokenizer.from_pretrained(args.model_tag)

    raw_perturbed_data = read_json_file(args.perturbed_json)
    raw_disjoint_pairs = read_json_file(args.disjoint_json)

    # Print the experiment configuration using for loop
    print(f"Experiment configuration:")
    for key, value in vars(args).items():
        print(f"{key}: {value}")

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

        if args.prompt_template == 'binary':
            loosely_coupled_pairs = generate_loosely_coupled_pairs(noise_ratio, tightly_coupeled_pairs, noise_classes)
            all_class_pairs = loosely_coupled_pairs + tightly_coupeled_pairs

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
            
            readme_content, _ = read_file_content(args.readme_path)
            # prompt = prompt_template(args.project_name, readme_content, classes_str)
            if args.prompt_template == 'retrieval':
                prompt_template = RETRIEVAL_BASED_COUPLING
                prompt = RETRIEVAL_BASED_COUPLING.format(
                    project_name=args.project_name, 
                    project_readme=readme_content, 
                    list_of_classes=classes_str
                    )
            elif args.prompt_template == 'binary':
                prompt_template = BINARY_BASED_COUPLING
                # Shuffle the class pairs
                random.shuffle(all_class_pairs)
                prompt = BINARY_BASED_COUPLING.format(
                        project_name=args.project_name,
                        project_readme=readme_content,
                        class_pair=all_class_pairs,
                        list_of_classes=classes_str
                    )
            elif args.prompt_template == 'hybrid':
                prompt_template = HYBRID_PROMPT
                # Get the first element of each class pair of tightly_coupled_pairs
                classes_under_analysis = set(pair[0] for pair in tightly_coupeled_pairs)
                classes_under_analysis = list(classes_under_analysis)
                # Get the noisy classes
                _noisy_classes = set(n_class['className'] for n_class in noise_classes)
                # Add the noisy classes to the classes under analysis
                classes_under_analysis.extend(_noisy_classes)
                # Shuffle the classes
                random.shuffle(classes_under_analysis)
                # Generate the prompt
                prompt = HYBRID_PROMPT.format(
                    project_name=args.project_name,
                    project_readme=readme_content,
                    classes_under_analysis=classes_under_analysis,
                    list_of_classes=classes_str
                )

            len_prompt = len(tokenizer.encode(prompt).ids)
            # Future idea: Randomly remove the body of classes in the prompt to make it more challenging
            print(f"Number of involved classes: {len(classes)}, Prompt token count: {len_prompt}, R={noise_ratio}, S={shuff}")
            prompt_file_name = f"prompt_R_{noise_ratio}_S_{shuff}.txt"
            prompt_file_path = os.path.join(output_dir, prompt_file_name)
            with open(prompt_file_path, 'w') as f:
                f.write(prompt)
            # Save metadata during last shuffle
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
                project_name = args.project_name
                metadata_file_name = f"{project_name}_prompt_R_{noise_ratio}_metadata.json"
                metadata_file_path = os.path.join(output_dir, metadata_file_name)
                # Save the class pairs to a file that represent the ground truth
                class_pairs_file_name = f"{project_name}_prompt_R_{noise_ratio}_ground_truth.json"
                class_pairs_file_path = os.path.join(output_dir, class_pairs_file_name)
                if args.prompt_template == 'retrieval_based' or args.prompt_template == 'hybrid':
                    ground_truth_file_name = f"{project_name}_prompt_R_{noise_ratio}_ground_truth.json"
                    ground_truth_file_path = os.path.join(output_dir, ground_truth_file_name)
                    ground_truth_pairs = tightly_coupeled_pairs
                    if args.prompt_template == 'hybrid':
                        non_coupled_pairs = [(_cls, None) for _cls in _noisy_classes]
                        ground_truth_pairs.extend(non_coupled_pairs)
                    save_to_json(ground_truth_pairs, ground_truth_file_path)
                
                elif args.prompt_template == 'binary_based':
                    print(f"Number of tightly coupled pairs: {len(tightly_coupeled_pairs)}, Number of loosely coupled pairs: {len(loosely_coupled_pairs)}")
                    ground_truth_tightly_coupeled_pairs = [ {"pair": p, "coupled": True} for p in tightly_coupeled_pairs]
                    ground_truth_loosely_coupled_pairs = [ {"pair": p, "coupled": False} for p in loosely_coupled_pairs]
                    ground_truth_results = ground_truth_loosely_coupled_pairs + ground_truth_tightly_coupeled_pairs
                    save_to_json(ground_truth_results, class_pairs_file_path)

                save_to_json(metadata, metadata_file_path)
    # Include the content of the prompt template in the config file
    args.template = prompt_template
    # Copy the config file to the output directory for reproducibility
    config_file_name = os.path.basename(arguments.config_file)
    config_file_path = os.path.join(output_dir, config_file_name)
    # Save to YML at prompt directory
    save_config_to_yaml(args, config_file_path)
    print(f"Prompt generation completed. Output directory: {output_dir}")


        

if __name__ == "__main__":
    main()