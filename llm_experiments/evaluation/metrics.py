from collections  import defaultdict
from sklearn.metrics import precision_score, recall_score, f1_score
from utils.eval_utils import to_canonical_set

class BinaryPromptEval:
    def __init__(self, ground_truth, answers) -> None:
        """
        Args:
            ground_truth: List of dictionaries following the format: {"pair": [classX, classY], "coupled": True/False}
            answers: List of dictionaries following the format: {"pair": [classX, classY], "coupled": True/False} returned by the LLM.
        """
        # Normalize the pairs by sorting the classes in each pair
        # MS: using set() would have also worked, but it would have been less readable.
        self.ground_truth = [
            {"pair": sorted(pair["pair"]), "coupled": pair["coupled"]} for pair in ground_truth
        ]
        self.answers = [
            {"pair": sorted(pair["pair"]), "coupled": pair["coupled"]} for pair in answers
        ]
        # Normalize by sorting by the list of pairs
        self.ground_truth.sort(key=lambda x: x["pair"])
        self.answers.sort(key=lambda x: x["pair"])
        # Convert into numerical binary values to calculate metrics
        self.ground_truth_numerical = [int(pair["coupled"]) for pair in self.ground_truth]
        self.answers_numerical = [int(pair["coupled"]) for pair in self.answers]
        # Sanity check and verify that all pairs are the same
        assert len(self.ground_truth) == len(self.answers), "Ground truth and answers must have the same length"
        assert all(pair1["pair"] == pair2["pair"] for pair1, pair2 in zip(self.ground_truth, self.answers)), "Ground truth and answers must have the same pairs"

    def calculate_metrics(self):
        """
        Calculate precision, recall and f1-score
        """
        # Calculate precision, recall and f1-score
        precision = precision_score(self.ground_truth_numerical, self.answers_numerical)
        recall = recall_score(self.ground_truth_numerical, self.answers_numerical)
        f1 = f1_score(self.ground_truth_numerical, self.answers_numerical)

        return {
            "precision": precision,
            "recall": recall,
            "f1": f1
        }
    
    def reset(self):
        """
        Reset the evaluation metrics
        """
        self.ground_truth = []
        self.answers = []
        self.ground_truth_numerical = []
        self.answers_numerical = []

class RetrievalPromptEval:
    """
    Class used to calculate F1, precision and recall for the retrieval-based task.
    """
    def __init__(self, ground_truth, answers) -> None:
        """
        Args:
            ground_truth: List of tuples of tightly coupled classes [(class1, dep1), (class1, dep2), ...].
            answers: List of tuples [(class1, dep1), (class1, dep2), ...] returned by the model.
        """
        # Normalize the pairs by sorting the classes in each pair. This is what frozenset does as a by product.
        # forzenset([foo, bar]) == forzenset([bar, foo]) is True. We use frozenset instead of set to make it hashable.
        # also lower case the classes to avoid case sensitivity issues.
        self.ground_truth = to_canonical_set(ground_truth)
        self.answers = to_canonical_set(answers)

    def calculate_f1_p_r(self):
        """
        Calculate precision, recall and f1-score
        """
        tp = self.ground_truth.intersection(self.answers)
        fp = self.answers - self.ground_truth
        fn = self.ground_truth - self.answers

        tp_count = len(tp)
        fp_count = len(fp)
        fn_count = len(fn)

        precision = tp_count / (tp_count + fp_count) if (tp_count + fp_count) > 0 else 0
        recall = tp_count / (tp_count + fn_count) if (tp_count + fn_count) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        return {
            "precision": precision,
            "recall": recall,
            "f1": f1
        }
    
    def get_unretrieved_ground_truth(self):
        """
        Get the ground truth pairs that were not retrieved by the model.
        """
        return self.ground_truth - self.answers
    
    def reset(self):
        """
        Reset the evaluation metrics
        """
        self.ground_truth = set()
        self.answers = set()
         
def calculate_jaccard_for_pairs(list_a, list_b):
    """
    Calculates the Jaccard Similarity between two lists of pairs,
    where the position of elements in a pair does not matter.

    Args:
        list_a: The first list of tuples.
        list_b: The second list of tuples.

    Returns:
        The Jaccard Similarity score as a float between 0.0 and 1.0.
    """
    # Convert both lists to sets of canonical pairs
    set_a = to_canonical_set(list_a)
    set_b = to_canonical_set(list_b)

    # Calculate the size of the intersection and union
    intersection_size = len(set_a.intersection(set_b))
    union_size = len(set_a.union(set_b))

    # Calculate Jaccard Similarity
    if union_size == 0:
        # If both lists are empty, they are perfectly similar.
        return 1.0
    else:
        return intersection_size / union_size