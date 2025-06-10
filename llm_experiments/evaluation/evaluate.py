from .metrics import BinaryPromptEval, RetrievalPromptEval
from utils.io import read_json_file, get_all_files, save_to_json
from argparse import ArgumentParser
import numpy as np



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
        choices=["binary", "retrieval"],
        required=True,
        help="Type of evaluation: binary or retrieval",
    )
    parser.add_argument(
        "--output_file",
        type=str,
        default=None,
        help="Path to save the evaluation results (optional)",
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()

    # Load ground truth
    ground_truth = read_json_file(args.ground_truth)

    # Perform evaluation based on the specified type
    if args.eval_type == "binary":
        evaluator = BinaryPromptEval
    elif args.eval_type == "retrieval":
        evaluator = RetrievalPromptEval


    # Load the answers from the specified folder
    all_files = get_all_files(args.answers_folder)
    final_results = [] # CSV rows: [model, noise_ratio, precision, recall, f1, suffle_num]
    for noise_ratio in NOISE_RATIOS:
        # Get all files in that corresponding noise ratio folder
        noise_ratio_files = [f for f in all_files if f"{noise_ratio}" in f]
        # Load the answers from the files
        f1_scores = []
        precision_scores = []
        recall_scores = []
        for file in noise_ratio_files:
            answers = read_json_file(file)
            # Initialize the evaluator with the ground truth and answers
            eval_instance = evaluator(ground_truth, answers['answer'])
            # Calculate precision and recall
            scores = eval_instance.calculate_metrics()
            precision = scores['precision'] * 100
            recall = scores['recall'] * 100
            f1 = scores['f1'] * 100
            precision_scores.append(precision) 
            recall_scores.append(recall)
            f1_scores.append(f1)
            # Store the results in the final results dictionary
            final_results.append({
                "model": args.model_name,
                "noise_ratio": noise_ratio,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "suffle_num": file.split("/")[-1].split("_")[4].split(".")[0]
            })
        # Calculate the average scores
        avg_precision = np.mean(precision_scores)
        avg_recall = np.mean(recall_scores)
        avg_f1 = np.mean(f1_scores)

        # Print the max of each metric
        print(f"Noise Ratio: {noise_ratio}")
        print(f"Precision: {np.max(precision_scores):.4f}")
        print(f"Recall: {np.max(recall_scores):.4f}")
        print(f"F1: {np.max(f1_scores):.4f}")
        print("-" * 30)
    # Save the final results to a JSON file if output_file is provided
    if args.output_file:
        save_to_json(final_results, args.output_file)
    else:
        print("No output file specified. Results not saved.")