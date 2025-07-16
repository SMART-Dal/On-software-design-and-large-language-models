import os
import argparse
from tqdm import tqdm

def parse_args():
    """
    Parses command-line arguments for the script.

    Returns:
        An argparse.Namespace object containing the parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Generate a YML configuration file for LLM experiments.")
    
    parser.add_argument('--root_dir', type=str, required=True, help='Root directory where the projects are located.')
    parser.add_argument('--output_dir', type=str, required=True, help='Directory where prompts will be saved.')
    parser.add_argument('--ymls_output_dir', type=str, required=True, help='Directory to save the output YML files.')
    parser.add_argument('--seed', type=int, default=42, help='Random seed for reproducibility.')
    parser.add_argument('--n_shuffles', type=int, default=10, help='Number of shuffles to perform.')
    parser.add_argument('--perturbation_types', nargs='+', required=True, help='List of perturbation types.')

    return parser.parse_args()

def get_folders(directory_path):
  """
  Gets a list of all folders within a specified directory.

  Args:
    directory_path: The absolute or relative path to the directory.

  Returns:
    A list of strings, where each string is the name of a folder
    in the specified directory.
    Returns an empty list if the path is not valid or contains no folders.
  """
  # Check if the provided path is a valid directory
  if not os.path.isdir(directory_path):
    print(f"Error: The path '{directory_path}' is not a valid directory.")
    return []

  try:
    # Get all entries in the directory and filter for folders
    folders = [item for item in os.listdir(directory_path)
               if os.path.isdir(os.path.join(directory_path, item))]
    return folders
  except OSError as e:
    print(f"Error accessing the directory: {e}")
    return []

def generate_yml_config(
    project_name: str,
    output_dir: str,
    root_dir: str,
    seed: int,
    n_shuffles: int,
    perturbation_types: list[str],
    output_filename: str
) -> None:
    """
    Generates a YML configuration file from a predefined template.

    Args:
        project_name (str): The name of the project.
        output_dir (str): The directory where output will be stored.
        seed (int): The random seed for the process.
        n_shuffles (int): The number of shuffles to perform.
        perturbation_types (list[str]): A list of perturbation types.
        output_filename (str): The path and name of the output .yml file.
    """
    # Format the list of perturbation types into a YAML-friendly string
    perturbations_str = "\n".join([f"  - {ptype}" for ptype in perturbation_types])

    # Define the YML content using an f-string as a template
    yml_content = f"""
project_name: {project_name}
perturbed_project_path: "{root_dir}/{project_name}-transformed_directinstantiation"
noisy_project_path: "{root_dir}/{project_name}-transformed_instantiationremover"
disjoint_json: "{root_dir}/{project_name}_disjointPairs.json"
perturbed_json: "{root_dir}/{project_name}_mutated_classes_did.json"
output_dir: {output_dir}
seed: {seed}
model_tag: "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B"
n_shuffles: {n_shuffles}
perturbation_types:
{perturbations_str}
"""

    try:
        # Write the generated content to the specified file
        with open(output_filename, 'w') as f:
            f.write(yml_content.strip())
        print(f"Successfully generated YML config: '{output_filename}'")
    except IOError as e:
        print(f"Error writing to file '{output_filename}': {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    args = parse_args()
    folders = get_folders(args.root_dir)
    projects = set()
    for folder in folders:
        project = folder.split('transformed')[0][:-1]
        projects.add(project)
    
    pbar = tqdm(projects, desc="Generating YML configs")
    output_directory = args.output_dir
    random_seed = args.seed
    shuffles = args.n_shuffles
    perturbations = args.perturbation_types
    for project in pbar:
        pbar.set_description(f"Generating YML config for {project}")
        yml_file_name = os.path.join(output_directory, f"{project}_config.yml")
        generate_yml_config(
           root_dir=args.root_dir,
            project_name=project,
            output_dir=output_directory,
            seed=random_seed,
            n_shuffles=shuffles,
            perturbation_types=perturbations,
            output_filename=yml_file_name
        )

    print("All YML configurations generated successfully.")


