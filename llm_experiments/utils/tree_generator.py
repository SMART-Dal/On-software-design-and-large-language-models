from collections import defaultdict

def find_common_prefix(paths):
    """Find the longest common prefix among a list of paths."""
    if not paths:
        return ''
    split_paths = [p.strip('/').split('/') for p in paths]
    min_len = min(len(p) for p in split_paths)
    common_parts = []
    for i in range(min_len):
        part = split_paths[0][i]
        for other in split_paths[1:]:
            if other[i] != part:
                return '/'.join(common_parts)
        common_parts.append(part)
    return '/'.join(common_parts)

def generate_file_tree(file_paths):
    """Generate a tree structure from a list of file paths."""
    tree = defaultdict(lambda: defaultdict(dict))
    for path in file_paths:
        parts = path.strip('/').split('/')
        current = tree
        for part in parts[:-1]:
            current = current.setdefault(part, defaultdict(dict))
        current[parts[-1]] = None  # Mark as file
    return tree

def format_tree(tree, indent=''):
    """Format the tree structure into a string."""
    lines = []
    items = sorted(tree.items(), key=lambda x: x[0])
    for i, (name, children) in enumerate(items):
        if i == len(items) - 1:
            prefix = '└── '
            next_indent = indent + '    '
        else:
            prefix = '├── '
            next_indent = indent + '│   '
        if children is None:
            lines.append(f"{indent}{prefix}{name}")
        else:
            lines.append(f"{indent}{prefix}{name}/")
            lines.extend(format_tree(children, next_indent))
    return '\n'.join(lines)