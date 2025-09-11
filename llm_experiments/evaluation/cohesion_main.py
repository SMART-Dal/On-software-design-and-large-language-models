import sys  
from sklearn.metrics.cluster import adjusted_rand_score
from itertools import chain
from utils.io import read_json_file
from utils.cleanup import extract_json_from_markdown
from tqdm import tqdm
import pandas as pd
import os
from sklearn.metrics import f1_score
import json

model_maps = {
    "deepseek-r1-distill-llama-70b": "DS-R1 (70B)",
    "deepseek-r1-distill-qwen-32b": "DS-R1 (32B)",
    "deepseek-r1-distill-qwen-14b": "DS-R1 (14B)"
}
mutation = "god_class"
ROOT_RESULTS_FOLDER = ""
OUTPUT_FOLDER = "s"

dfs = []
for model in tqdm(model_maps):
    samples = read_json_file(os.path.join(ROOT_RESULTS_FOLDER, mutation, model, "results.json"))
    model_name_col = [model_maps[model]] * len(samples)
    _df = pd.DataFrame(samples)
    _df["Model"] = model_name_col
    dfs.append(_df)

df = pd.concat(dfs)
valid_df = df[df['error'].isna()]

def process_binary(df):
    binary_df = df[df['help_level'] == 'binary']
    is_valid_mask = binary_df['answer'].str.lower().isin(['yes', 'no'])
    binary_df = binary_df[is_valid_mask].copy()

    binary_df['numerical_gt'] = binary_df['ground_truth'].str.lower().map({'yes': 1, 'no': 0})
    binary_df['numerical_answer'] = binary_df['answer'].str.lower().map({'yes': 1, 'no': 0})

    return binary_df

def calculate_f1_by_distortion(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filters for the binary task and calculates a single F1 score for each
    Model-DistortionRatio group.

    Args:
        df (pd.DataFrame): The main DataFrame containing all experiment results.
                           Must have 'Model', 'help_level', 'distortion_ratio',
                           'numerical_gt', and 'numerical_answer' columns.

    Returns:
        pd.DataFrame: A new DataFrame with 'Model', 'distortion_ratio', and 
                      'f1_score' columns.
    """
    print("\nCalculating F1 score per distortion ratio for the 'binary' task...")


    # Step 1: Group by both Model and distortion ratio
    grouped = df.groupby(['Model', 'distortion_level'])

    # Step 3: Calculate F1 score for each group
    f1_results = []
    for (model, ratio), group_df in grouped:
        y_true = group_df['numerical_gt']
        y_pred = group_df['numerical_answer']
        
        # Calculate the aggregate F1 score for this entire group
        score = f1_score(y_true, y_pred, zero_division=0)
        
        f1_results.append({
            'Model': model,
            'distortion_level': ratio,
            'f1_score': score
        })

    # Step 4: Create the new DataFrame
    summary_df = pd.DataFrame(f1_results)
    
    print("Calculation complete.")
    return summary_df

def filter_and_parse_hybrid_answers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filters a DataFrame for the hybrid task, parses the JSON from the 'answer' column,
    and converts the 'ground_truth' string to a list.

    Args:
        df (pd.DataFrame): The DataFrame containing all raw experiment results.

    Returns:
        pd.DataFrame: A new DataFrame containing only the rows for the hybrid task
                      where the answer was successfully parsed as JSON. Includes new
                      'parsed_answer' and 'ground_truth_list' columns.
    """
    print("\n--- Filtering and Parsing Hybrid Task Answers ---")
    
    # Step 1: Filter for the 'hybrid' task and drop rows with no answer
    hybrid_df = df[df['help_level'] == 'hybrid'].dropna(subset=['answer']).copy()
    initial_count = len(hybrid_df)
    print(f"Found {initial_count} initial rows for the 'hybrid' task.")

    # Step 2: Apply the extraction function to each row's 'answer'
    hybrid_df['parsed_json_list'] = hybrid_df['answer'].apply(extract_json_from_markdown)

    # Step 3: Filter out rows where no valid JSON was found
    # A valid row will have a list with one or more dictionaries
    parsable_df = hybrid_df[hybrid_df['parsed_json_list'].apply(len) > 0].copy()
    final_count = len(parsable_df)
    
    print(f"Filtered out {initial_count - final_count} rows with non-parsable answers.")
    print(f"Kept {final_count} rows with valid JSON for evaluation.")

    if not parsable_df.empty:
        # Step 4: For simplicity, assume the first valid JSON block is the intended answer.
        # Also, extract the list from the 'cohesiveMethods' key.
        def normalize_answer_methods(ans):
            _ans = ans[0].get('cohesiveMethods', []) if isinstance(ans[0], dict) else []
            if _ans:
                all_valid = all(isinstance(elem, str) for elem in _ans)
                if not all_valid:
                    return []
                methods = list(map(lambda x: x.replace(" ", "").lower(), _ans))
                return methods
            else:
                return []
            
        parsable_df['parsed_answer'] = parsable_df['parsed_json_list'].apply(
            lambda x: normalize_answer_methods(x)
        )

        def parse_ground_turth(gt):
            dict_gt = json.loads(gt)
            cohesive_methods = dict_gt['cohesiveMethods']
            cohesive_methods = list(map(lambda x: x.replace(" ", "").lower(), cohesive_methods))
            return cohesive_methods
        
        # Step 5: Convert the string-based ground_truth into a list of strings.
        if 'ground_truth' in parsable_df.columns:
            parsable_df['ground_truth_list'] = parsable_df['ground_truth'].apply(
                lambda gt: parse_ground_turth(gt)
            )
    
    # Drop the intermediate column
    parsable_df.drop(columns=['parsed_json_list'], inplace=True)
    
    return parsable_df

def _calculate_set_f1(y_true: list, y_pred: list) -> float:
    """
    Helper function to calculate the F1 score based on the intersection of two sets of items.
    """
    true_set = set(y_true)
    pred_set = set(y_pred)
    
    if not true_set and not pred_set:
        return 1.0 # Both are empty, perfect match
    if not true_set or not pred_set:
        return 0.0 # One is empty, the other isn't

    precision = len(true_set.intersection(pred_set)) / len(pred_set)
    recall = len(true_set.intersection(pred_set)) / len(true_set)

    if precision + recall == 0:
        return 0.0
        
    f1 = 2 * (precision * recall) / (precision + recall)
    return f1

def calculate_hybrid_f1_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates the F1 score for each row of the parsed hybrid task data,
    then creates a summary DataFrame with the mean F1 score per Model and 
    distortion ratio.

    Args:
        df (pd.DataFrame): The pre-processed DataFrame from filter_and_parse_hybrid_answers.

    Returns:
        pd.DataFrame: A new DataFrame with 'Model', 'distortion_ratio', and 
                      'f1_score' columns.
    """
    print("\n--- Calculating F1 Score Summary for Hybrid Task ---")
    if df.empty or 'parsed_answer' not in df.columns or 'ground_truth_list' not in df.columns:
        print("Input DataFrame is empty or missing required columns ('parsed_answer', 'ground_truth_list').")
        return pd.DataFrame({'Model': [], 'distortion_level': [], 'f1_score': []})

    # Step 1: Calculate the F1 score for each individual row
    df['f1_score'] = df.apply(
        lambda row: _calculate_set_f1(row['ground_truth_list'], row['parsed_answer']),
        axis=1
    )

    # Step 2: Group by Model and distortion ratio, then calculate the mean F1 score
    summary_df = df.groupby(['Model', 'distortion_level'])['f1_score'].mean().reset_index()
    
    print("Calculation complete.")
    return summary_df

def is_valid_answer_format(answer_dict: dict) -> bool:
    """
    Checks if an answer is in the valid format.
    A valid format is a dictionary where every value is a list of strings.
    """
    # 1. The input must be a dictionary.
    if not isinstance(answer_dict, dict):
        return False
        
    # An empty dictionary is considered valid.
    if not answer_dict:
        return True

    # 2. Every value in the dictionary must be a list.
    for value in answer_dict.values():
        if not isinstance(value, list):
            return False
        # 3. Every element within that list must be a string.
        #    all() is efficient as it stops on the first False.
        if not all(isinstance(item, str) for item in value):
            return False
            
    # If all checks pass, the format is valid.
    return True

def filter_and_parse_retrieval_answers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filters a DataFrame for the retrieval task, parses the JSON from the 'answer' column,
    and parses the 'ground_truth' JSON string.
    """
    print("\n--- Filtering and Parsing Retrieval Task Answers ---")
    
    retrieval_df = df[df['help_level'] == 'retrieval'].dropna(subset=['answer', 'ground_truth']).copy()
    initial_count = len(retrieval_df)

    retrieval_df['parsed_json_list'] = retrieval_df['answer'].apply(extract_json_from_markdown)
    parsable_df = retrieval_df[retrieval_df['parsed_json_list'].apply(len) > 0].copy()
    parsable_count = len(parsable_df)
    

    if not parsable_df.empty:
        parsable_df['parsed_answer'] = parsable_df['parsed_json_list'].apply(
            lambda x: x[0] if x and isinstance(x[0], dict) else {}
        )
        # Keep only valid answers. A valid answer must be a dict where each value is a list that contains only strings.
        parsable_df['is_valid_format'] = parsable_df['parsed_answer'].apply(is_valid_answer_format)
        
        valid_format_df = parsable_df[parsable_df['is_valid_format']].copy()
        
        valid_format_count = len(valid_format_df)
        print(f"Filtered out {parsable_count - valid_format_count} rows with incorrectly formatted JSON values.")
        print(f"Kept {valid_format_count} final rows for evaluation.")
        
        if valid_format_count == 0:
             return pd.DataFrame() # Return empty df if no rows are left

        # Also parse the ground_truth from its JSON string format
        valid_format_df['parsed_ground_truth'] = valid_format_df['ground_truth'].apply(
            lambda x: json.loads(x) if isinstance(x, str) else {}
        )
        
        # Clean up intermediate columns before returning
        valid_format_df.drop(columns=['parsed_json_list', 'is_valid_format'], inplace=True)
        return valid_format_df
        
    # If the DataFrame was empty to begin with, return an empty one
    return pd.DataFrame()

def calculate_ari(clustering1, clustering2):
    """
    Calculates the Adjusted Rand Index (ARI) for two clusterings.

    The function takes two clusterings, each represented as a list of lists,
    where each inner list is a cluster and contains the elements of that cluster.
    It handles elements that might be present in one clustering but not the other.

    Args:
        clustering1 (list[list[any]]): The first clustering.
        clustering2 (list[list[any]]): The second clustering.

    Returns:
        float: The Adjusted Rand Index, a value between -1.0 and 1.0.
               A score of 1.0 indicates perfect agreement, while a score
               close to 0 suggests random agreement.
    """
    # Flatten the lists of lists to get all elements and then find the unique set
    # of elements across both clusterings.
    all_elements = sorted(list(set(chain.from_iterable(clustering1)) | set(chain.from_iterable(clustering2))))

    # Create a mapping from each unique element to an integer index.
    # This is necessary because the scikit-learn function works with integer labels.
    element_to_id = {element: i for i, element in enumerate(all_elements)}
    num_elements = len(all_elements)

    # Initialize two lists with a default value (e.g., -1) to hold the cluster
    # labels for each element. The default value represents an element not
    # being in any cluster, though in this setup every element will be assigned.
    labels1 = [-1] * num_elements
    labels2 = [-1] * num_elements

    # Populate the first labels list. The cluster's index (i) becomes the label.
    for i, cluster in enumerate(clustering1):
        for element in cluster:
            # Look up the integer ID for the element and assign the cluster index.
            if element in element_to_id:
                labels1[element_to_id[element]] = i

    # Populate the second labels list similarly.
    for i, cluster in enumerate(clustering2):
        for element in cluster:
            if element in element_to_id:
                labels2[element_to_id[element]] = i

    # Use the scikit-learn function to compute the ARI.
    return adjusted_rand_score(labels1, labels2)

def calculate_retrieval_ari_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates the Rand scores summary for the retrieval task.
    """
    print("\n--- Calculating Cluster Rand Scores Summary for Retrieval Task ---")
    if df.empty or 'parsed_answer' not in df.columns or 'parsed_ground_truth' not in df.columns:
        print("Input DataFrame is empty or missing required columns.")
        return pd.DataFrame()

    def preprocess_answer_ground_truth(row):
        ground_truth, answer = row['parsed_ground_truth'], row['parsed_answer']
        if type(answer) != dict or type(ground_truth) != dict:
            return None
            
        gt = list(ground_truth.values())
        processed_gt = []
        for cluster in gt:
            if type(cluster) != list:
                return None
            valid_cluster = all(isinstance(elem, str) for elem in cluster)
            if not valid_cluster:
                return None
            new_cluster = list(map(lambda x: x.replace(" ", "").lower(), cluster))
            processed_gt.append(new_cluster)

        _answer = list(answer.values())
        processed_answer = []
        for ans_cluster in _answer:
            if type(cluster) != list:
                return None
            valid_cluster = all(isinstance(elem, str) for elem in ans_cluster)
            if not valid_cluster:
                return None
            new_cluster = list(map(lambda x: x.replace(" ", "").lower(), ans_cluster))
            processed_answer.append(new_cluster)

        return processed_gt, processed_answer

    df['Rand index'] = df.apply(
        lambda row: calculate_ari(row['parsed_ground_truth'].values(), row['parsed_answer'].values()),
        axis=1
    )
    df = df.dropna(subset=['Rand index'])
    summary_df = df.groupby(['Model', 'distortion_level'])['Rand index'].mean().reset_index()
    print("Calculation complete.")
    return summary_df

verification_df = process_binary(valid_df)
verification_results = calculate_f1_by_distortion(verification_df)

guided_df = filter_and_parse_hybrid_answers(valid_df)
guided_results = calculate_hybrid_f1_summary(guided_df)

open_ended_df = filter_and_parse_retrieval_answers(valid_df)
open_ended_results = calculate_retrieval_ari_summary(open_ended_df)

verification_results.to_csv("cohesion_verification_results.csv", index=None)
guided_results.to_csv("cohesion_guided_generation_results.csv", index=None)
open_ended_results.to_csv("cohesion_open-ended_generation_results.csv", index=None)