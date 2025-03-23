import argparse
import os
import random
import seedir as sd
from tokenizers import Tokenizer
from utils.io import read_json_file, read_file_content, save_to_json
from utils.paths import get_absolute_file_paths
from utils.preprocessing import remove_comments_and_docstrings

def prompt_template(project_name, project_readme, file_structure, list_of_classes):
    return f"""
You are given a Java project named {project_name}. Below is the content of its README file to provide context about its purpose:

## README:
{project_readme}

## Classes:
{list_of_classes}

## Task:
Your task is to analyze the dependencies between these classes and identify any tightly coupled classes. Tightly coupled classes are those with strong dependencies on each other, making them difficult to modify or test independently. 

Please provide a list of tuples of classes that you think are tightly coupled. For example, if you think a Java class A is tightly coupled with classes B and C, you should provide the following tuple: [A, B, C].

Note that you should NOT consider primitive types (e.g., int, float) as classes.

## Response Format:
Please provide your response in the following format:
[
    [Class1, Class2, Class3],
    [Class4, Class5],
    ...
]

If no classes are tightly coupled, please provide an empty list [].

"""

def main():
    parser = argparse.ArgumentParser(description='Generate a prompt for LLM with project context, perturbed classes, dependencies, and noise.')
    parser.add_argument('--project_name', required=True, help='Name of the Java project')
    parser.add_argument('--perturbed_project_path', required=True, help='Path to the perturbed classes')
    parser.add_argument('--readme_path', required=True, help='Path to the README file of the project')
    parser.add_argument('--disjoint_json', required=True, help='Path to JSON file containing disjoint class pairs')
    parser.add_argument('--perturbed_json', required=True, help='Path to JSON file containing perturbed classes and their dependencies')
    parser.add_argument('--noise_ratio', type=float, required=True, help='Noise ratio (Perturbed+Dependencies / Total)')
    parser.add_argument('--output_prompt', required=True, help='Path to output the generated prompt files')
    parser.add_argument('--seed', type=int, default=42, help='Random seed for reproducibility')
    parser.add_argument('--model_tag', required=True, help='Huggingface model tag for the LLM')
    parser.add_argument('--n_shuffles', type=int, default=1, help='Number of shuffles, i.e., different prompts to generate')
    parser.add_argument('--perturbation_types', nargs='+', default=['did', 'dal', 'gc', 'feii'], help='Types of perturbations that were applied to the classes')
    args = parser.parse_args()

    tokenizer = Tokenizer.from_pretrained(args.model_tag)

    perturbed_data = read_json_file(args.perturbed_json)
    disjoint_pairs = read_json_file(args.disjoint_json)

    # Collect perturbed files
    perturbed_files = set(perturbed_data.keys())
    # Add path prefix to perturbed files
    perturbed_files = set([os.path.join(args.perturbed_project_path, file) for file in perturbed_files])
    
    # Collect direct dependencies and dependency chains
    print(f"""
Project: {args.project_name}
Perturbed classes: {len(perturbed_files)}
Disjoint pairs: {len(disjoint_pairs)}
Perturbed data: {len(perturbed_data)}
Noise ratio: {args.noise_ratio}
Seed: {args.seed}
Model tag: {args.model_tag}
Perturbation types: {args.perturbation_types}
Shuffles: {args.n_shuffles}
""")
    direct_deps_files = set()
    dependency_chain_files = set()
    ground_truth = [] # List of tuples of tightly coupled classes: [(class1, dep1, dep2), (class2, dep3, dep4, dep5), ...]
    for classname, deps in perturbed_data.items():
        _deps = []
        perturbed_class_name = classname.split('/')[-1].split('.')[0]
        _deps.append(perturbed_class_name)
        for dep in deps:
            full_dep_path = os.path.join(args.perturbed_project_path, dep['dependencyClassFilePath'])
            direct_deps_files.add(full_dep_path)
            dependency_class_name = dep['dependencyClassName'].split('.')[-1]
            _deps.append(dependency_class_name)
            for chain_entry in dep['dependencyChain']:
                full_dep_chain_path = os.path.join(args.perturbed_project_path, chain_entry['filePath'])
                dependency_chain_files.add(full_dep_chain_path)
                _deps.append(chain_entry['className'])
        ground_truth.append(_deps)


    # Collect noise candidates from disjoint pairs
    noise_candidates = set()
    for pair in disjoint_pairs:
        left_path = pair['left']['filePath']
        right_path = pair['right']['filePath']
        if (left_path not in perturbed_files) \
            and (left_path not in direct_deps_files) \
            and (left_path not in dependency_chain_files):
            full_left_path = os.path.join(args.perturbed_project_path, left_path)
            noise_candidates.add(full_left_path)
        
        if (right_path not in perturbed_files) \
            and (right_path not in direct_deps_files) \
            and (right_path not in dependency_chain_files):
            full_right_path = os.path.join(args.perturbed_project_path, right_path)
            noise_candidates.add(full_right_path)

    # Calculate required noise count
    p = len(perturbed_files)
    d = len(direct_deps_files)
    numerator = p + d
    if args.noise_ratio <= 0 or args.noise_ratio > 1:
        raise ValueError("Noise ratio must be between 0 and 1 (exclusive)")
    total = numerator / args.noise_ratio
    noise_count = int(total - numerator)
    noise_count = max(noise_count, 0)

    # Select noise files
    noise_files = list(noise_candidates)[:noise_count]

    # Collect all files (Shuffling should happen here)
    all_files = perturbed_files.union(direct_deps_files).union(dependency_chain_files).union(noise_files)
    all_files_map = {file: remove_comments_and_docstrings(read_file_content(file)) for file in all_files}
    def _create_input(keys, file_map):
        input_text = ""
        for key in keys:
            content = file_map[key]
            input_text += f"{key}\n {content}\n"
            input_text += "\n" + "=" * 50 + "\n\n"
        return input_text

    # Get the file tree
    excluded_files = get_absolute_file_paths(args.perturbed_project_path) - set(all_files)
    excluded_files = list(map(lambda x: os.path.basename(x), excluded_files))
    # Seprate excluded_files into directories and files
    _excluded_files = [x for x in excluded_files if "." in x]
    _excluded_dirs = [x for x in excluded_files if "." not in x]
    # Generate file tree
    file_tree = sd.seedir(
        args.perturbed_project_path,
        style='lines',
        exclude_files=_excluded_files,
        exclude_folders=_excluded_dirs,
        printout=False
        )
    for i in range(args.n_shuffles):
        print(f"Generating prompt {i+1}/{args.n_shuffles}")
        _all_files = list(all_files_map.keys())
        random.shuffle(_all_files)
        all_files_string = _create_input(_all_files, all_files_map)
        prompt = prompt_template(args.project_name, read_file_content(args.readme_path), file_tree, all_files_string)
        # Save pormpt on disk
        # Prompt file name: project_name_perturbations_ratio_idx_seed.txt
        prompt_file_name = f"{args.project_name}_{'-'.join(args.perturbation_types)}_{args.noise_ratio}_{i}_{args.seed}.txt"
        prompt_file_path = os.path.join(args.output_prompt, prompt_file_name)
        with open(prompt_file_path, 'w') as f:
            f.write(prompt)
   
    # Save ground truth on disk
    # Ground truth file name: project_name_ground_truth_ratio_seed.json
    print("Saving ground truth")
    ground_truth_file_name = f"{args.project_name}_{'-'.join(args.perturbation_types)}_{args.noise_ratio}_{args.seed}.json"
    ground_truth_file_path = os.path.join(args.output_prompt, ground_truth_file_name)
    save_to_json(ground_truth, ground_truth_file_path)

if __name__ == "__main__":
    main()