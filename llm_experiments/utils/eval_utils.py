from typing import Any, List, Tuple, Union, Dict

StringPair = Tuple[Union[str, None], Union[str, None]]

def filter_string_pairs(items: List[Any]) -> List[StringPair]:
    """
    Filters a list to keep only items that are valid string/None pairs.

    A valid item must satisfy all of the following criteria:
    1. It must be a list or a tuple.
    2. It must contain exactly two elements.
    3. Each of its two elements must be either a string or the None value.

    Args:
        items: A list of items of any type to be filtered.

    Returns:
        A new list containing only the items that meet the specified criteria.
    """
    validated_pairs = []
    for item in items:
        # Check 1: Is the item a list or a tuple?
        if not isinstance(item, (list, tuple)):
            continue

        # Check 2: Does it have exactly two elements?
        if len(item) != 2:
            continue

        # Unpack the two elements
        first, second = item

        # Check 3: Are both elements either a string or None?
        is_first_valid = isinstance(first, (str, type(None)))
        is_second_valid = isinstance(second, (str, type(None)))

        if is_first_valid and is_second_valid:
            # If all checks pass, add it to our results list as a tuple
            validated_pairs.append(item)
            
    return validated_pairs

def filter_and_normalize_coupling_dicts(dict_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filters and normalizes a list of dictionaries based on a specific structure.

    A dictionary is kept if it meets all the following criteria:
    1. It contains both "pair" and "coupled" keys.
    2. The value for the "pair" key is a list containing exactly two items.
    3. The value for the "coupled" key is a boolean (True/False) or a
       string representation of a boolean (e.g., "TRUE", "false").

    The "coupled" value in the returned dictionaries is normalized to a
    proper Python boolean.

    Args:
        dict_list: A list of dictionaries to filter.

    Returns:
        A new list containing the valid and normalized dictionaries.
    """
    validated_dicts = []
    for item in dict_list:
        # Check 1: Must be a dict with 'pair' and 'coupled' keys
        if not isinstance(item, dict) or "pair" not in item or "coupled" not in item:
            continue

        pair_value = item["pair"]
        coupled_value = item["coupled"]

        # Check 2: 'pair' must be a list with two items
        if not isinstance(pair_value, list) or len(pair_value) != 2:
            continue

        # Check 3 & Normalize: 'coupled' must be a boolean or a boolean-like string
        normalized_coupled = None
        if isinstance(coupled_value, bool):
            normalized_coupled = coupled_value
        elif isinstance(coupled_value, str):
            if coupled_value.lower() == 'true':
                normalized_coupled = True
            elif coupled_value.lower() == 'false':
                normalized_coupled = False
        
        # If normalization failed (e.g., was not a bool or a valid string), skip it
        if normalized_coupled is None:
            continue

        # If all checks pass, create the new normalized dict and add it
        validated_dicts.append({
            "pair": pair_value,
            "coupled": normalized_coupled
        })
        
    return validated_dicts

def get_unique_invariant_pairs(pairs_list):
    """
    Filters a list of tuples to keep only unique pairs, where the
    position of elements in a pair does not matter. For example,
    ('A', 'C') and ('C', 'A') are considered the same.

    This function correctly handles pairs containing None.

    Args:
        pairs_list: A list of tuples, where each tuple has two elements.

    Returns:
        A new list containing only the unique pairs from the input list.
    """
    seen_pairs = set()
    unique_list = []

    for pair in pairs_list:
        # To handle position invariance, we need a canonical representation
        # for each pair. We create one by sorting the elements within the tuple.
        #
        # A custom key is used for sorting to handle `None` values correctly,
        # as `None` cannot be directly compared to other types like strings.
        # This key ensures that `None` is always treated as a 'larger' value,
        # placing it at the end of the sorted tuple.
        # For example, both ('A', None) and (None, 'A') will become ('A', None).
        # And both ('C', 'A') and ('A', 'C') will become ('A', 'C').
        canonical_pair = tuple(sorted(pair, key=lambda x: (x is None, x)))

        # We check if we have already seen this canonical version.
        if canonical_pair not in seen_pairs:
            # If not, we add the original pair to our results...
            unique_list.append(pair)
            # ...and add the canonical version to our set of seen pairs.
            seen_pairs.add(canonical_pair)

    return unique_list

def to_canonical_set(pairs_list):
    """
    Converts a list of pairs into a set of canonical pairs.
    A canonical pair is a sorted tuple, ensuring that (X, Y) and (Y, X)
    are treated as the same element.
    """
    canonical_set = set()
    for pair in pairs_list:
        # Sort the pair to create a canonical representation.
        # The custom key handles None values correctly.
        try:
            a, b = pair
            processed_a = a.lower() if isinstance(a, str) else a
            processed_b = b.lower() if isinstance(b, str) else b

            sorted_pair = tuple(sorted((processed_a, processed_b), key=lambda x: (x is None, x)))
            canonical_set.add(sorted_pair)
        except ValueError:
            print(f"Warning: Skipping invalid pair {pair}. Expected a tuple of two elements.")
            continue

    return canonical_set

def clean_ground_turth(ground_turth, is_binary):
    """
    Cleans inner classes names. E.g. Foo$Bar => Bar.
    """
    def _clean_pair(pair):
        a,b = pair
        a = a.split("$")[-1] if isinstance(a, str) and "$" in a else a
        b = b.split("$")[-1] if isinstance(b, str) and "$" in b else b

        return [a, b]
    if is_binary:
        fixed_ground_turth = []
        for pair in ground_turth:
            fixed_ground_turth.append(
                {
                    "pair": _clean_pair(pair["pair"]),
                    "coupled": pair["coupled"]
                }
            )
        return fixed_ground_turth
    else:
        fixed_ground_turth = []
        for pair in ground_turth:
            fixed_ground_turth.append(_clean_pair(pair))
        
        return fixed_ground_turth