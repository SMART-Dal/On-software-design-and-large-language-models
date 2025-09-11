
from utils.io import read_json_file
from utils.cleanup import extract_json_from_markdown, convert_string_none
from utils.eval_utils import filter_and_normalize_coupling_dicts, filter_string_pairs, clean_ground_turth
from evaluation.metrics import BinaryPromptEval, RetrievalPromptEval
from tqdm import tqdm
import pandas as pd
import os

models_map = {
    "deepseek-r1-distill-qwen-14b": "DS-R1 (14B)",
    "deepseek-r1-distill-qwen-32b": "DS-R1 (32B)",
    "deepseek-r1-distill-llama-70b": "DS-R1 (70B)"
}
mutation = "did"
ROOT_RESULTS_FOLDER = ""
OUTPUT_FOLDER = ""

def create_df(results_path, model_name):
    samples = read_json_file(results_path)
    samples = list(filter(lambda x: 'answer' in x, samples))
    df = pd.DataFrame(samples)
    new_col = [model_name] * len(df)
    df['Model'] = new_col
    scores = []
    for index, row in tqdm(df.iterrows()):
        answer = row['answer']
        parsed_answer = extract_json_from_markdown(f"""{answer}""")
        if not len(parsed_answer):
            scores.append(-1)
            continue
        converted_parsed_answer = convert_string_none(parsed_answer[0])
        ground_truth = row["ground_truth"]
        if not ground_truth:
            scores.append(-1)
            continue
        prompt_method = row["help_level"]
        if prompt_method == "hybrid" or prompt_method == "retrieval":
            cleaned_gt = clean_ground_turth(ground_truth, False)
            filtered_ground_truth = filter_string_pairs(cleaned_gt)
            filtered_answer = filter_string_pairs(converted_parsed_answer)
            evaluator = RetrievalPromptEval(ground_truth, filtered_answer)
        else:
            cleaned_gt = clean_ground_turth(ground_truth, True)
            filtered_answer = filter_and_normalize_coupling_dicts(converted_parsed_answer)
            filtered_gt = filter_and_normalize_coupling_dicts(cleaned_gt)
            evaluator = BinaryPromptEval(filtered_gt, filtered_answer)
    
        results = evaluator.calculate_f1_p_r()
        scores.append(results["f1"])
        evaluator.reset()
    
    df['F1'] = scores
    valid_df = df[df["F1"] != -1]
    
    help_level_mapping = {
        'binary': 'Verification',
        'hybrid': 'Guided Generation',
        'retrieval': 'Open-ended Generation'
    }
    
    valid_df['task_type'] = valid_df['help_level'].map(help_level_mapping)
    
    task_order = list(help_level_mapping.values())

    return valid_df
    

dfs = [create_df(os.path.join(ROOT_RESULTS_FOLDER, mutation, m_path, "results.json"), m_name) for m_path, m_name in models_map.items()]
df = pd.concat(dfs)

df.to_csv(f"coupling_results_{mutation}.csv")