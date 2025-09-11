from .metrics import BinaryPromptEval, RetrievalPromptEval, calculate_jaccard_for_pairs
from utils.io import read_json_file, get_all_files, save_to_json
from utils.eval_utils import get_unique_invariant_pairs
from argparse import ArgumentParser
import numpy as np
import os



NOISE_RATIOS = [round(i*1e-1, 1) for i in range(1, 9)]

def parse_args():
    parser = ArgumentParser(description="Evaluate LLM output")
    parser.add_argument(
        "--ground_truth",
        type=str,
        required=True,
        help="Path to the ground truth file (JSON format)",
    )
    parser.add_argument(
        "--answers_folder",
        type=str,
        required=True,
        help="Path to the answers files (JSON format)",
    )
    parser.add_argument(
        "--model_name",
        type=str,
        required=True,
        help="Name of the model used for evaluation",
    )
    parser.add_argument(
        "--eval_type",
        type=str,
        choices=["binary", "retrieval", "hybrid"],
        required=True,
        help="Type of evaluation: binary or retrieval",
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()

    # Perform evaluation based on the specified type
    if args.eval_type == "binary":
        evaluator = BinaryPromptEval
    elif args.eval_type == "retrieval" or args.eval_type == "hybrid":
        evaluator = RetrievalPromptEval


    # Load the answers from the specified folder
    all_files = get_all_files(args.answers_folder)
    final_results = [] # CSV rows: [model, noise_ratio, precision, recall, f1, suffle_num]
    for noise_ratio in NOISE_RATIOS:
        # Get all files in that corresponding noise ratio folder
        noise_ratio_files = [f for f in all_files if f"{noise_ratio}" in f]
        # Load the ground truth file of the corresponding noise ratio
        ground_truth_file = os.path.join(args.ground_truth, f"prompt_R_{noise_ratio}_ground_truth.json")
        ground_truth = read_json_file(ground_truth_file)
        f1_scores = []
        precision_scores = []
        recall_scores = []
        aggregated_shuffle_answers = []
        for file in noise_ratio_files:
            answers = read_json_file(file)
            

        # print(f"Recall: {np.mean(recall_scores):.4f} (std: {np.std(recall_scores):.4f})")
        # print(f"F1: {np.mean(f1_scores):.4f} (std: {np.std(f1_scores):.4f})")
        print("-" * 30)
    # Save the final results to a JSON file if output_file is provided
    # save_to_json(final_results, os.path.join(args.answers_folder, "evaluation_results.json"))