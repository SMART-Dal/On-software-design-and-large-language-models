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
        canonical_pair = tuple(sorted(pair, key=lambda x: (x is None, x)))
        # Lowercasing is applied to handle case insensitivity.
        canonical_pair = tuple(map(lambda x: x.lower() if isinstance(x, str) else x, canonical_pair))
        canonical_set.add(canonical_pair)
    return canonical_set