from collections  import defaultdict

def group_by_class(pairs):
    """
    Group dependencies by their source class
    """
    grouped = defaultdict(set)
    for _class, dep in pairs:
        grouped[_class].add(dep)

    return grouped 

def calculate_metrics(ground_truth, predicted):
    """
    Calculate micro and macro precision, recall and f1-score
    
    Args:
        ground_truth: List of tuples of tightly coupled classes [(class1, dep1), (class1, dep2), ...].
        retrieved: List of tuples [(class1, dep1), (class1, dep2), ...] returned by the model.
    """
    # Get grouped dependencies for ground truth and predicted
    gt_grouped = group_by_class(ground_truth)
    returned_grouped = group_by_class(predicted)

    micro_tp, micro_fp, micro_fn = 0, 0, 0
    macro_precisions = []
    macro_recalls = []
    macro_f1s = []

    # Caculate metrics per class

    for class_x in gt_grouped:
        true_deps = gt_grouped[class_x]
        retrieved_deps = returned_grouped.get(class_x, set())

        tp = len(true_deps & retrieved_deps)
        fp = len(retrieved_deps - true_deps)
        fn = len(true_deps - retrieved_deps)

        micro_tp += tp
        micro_fp += fp
        micro_fn += fn

        precision = tp / (tp + fp) if tp + fp > 0 else 0
        recall = tp / (tp + fn) if tp + fn > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        macro_precisions.append(precision)
        macro_recalls.append(recall)
        macro_f1s.append(f1)

    # Calculate micro-averaged metrics
    micro_precision = micro_tp / (micro_tp + micro_fp) if micro_tp + micro_fp > 0 else 0
    micro_recall = micro_tp / (micro_tp + micro_fn) if micro_tp + micro_fn > 0 else 0
    micro_f1 = 2 * (micro_precision * micro_recall) / (micro_precision + micro_recall) if (micro_precision + micro_recall) > 0 else 0

    # Calculate macro-averaged metrics
    macro_precision = sum(macro_precisions) / len(macro_precisions) if macro_precisions else 0
    macro_recall = sum(macro_recalls) / len(macro_recalls) if macro_recalls else 0
    macro_f1 = sum(macro_f1s) / len(macro_f1s) if macro_f1s else 0

    return {
        "micro": {
            "precision": micro_precision,
            "recall": micro_recall,
            "f1": micro_f1
        },
        "macro": {
            "precision": macro_precision,
            "recall": macro_recall,
            "f1": macro_f1
        }
    }
