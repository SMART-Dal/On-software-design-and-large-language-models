from tree_sitter import Parser

def remove_class_bodies(code: str, parser: Parser) -> str:
    """
    Removes the bodies of all top-level class declarations in the given Java code,
    while preserving the class signatures, imports, package declarations, etc.

    Args:
        code (str): The Java source code as a string.
        parser (Parser): A Tree-sitter Parser instance configured for the Java language.

    Returns:
        str: The modified Java code with all top-level class bodies replaced with '{}'.
    """
    # Encode the code to bytes for Tree-sitter parsing
    code_bytes = code.encode('utf8')
    
    # Parse the code into a syntax tree
    tree = parser.parse(code_bytes)
    root_node = tree.root_node
    
    # Collect replacement ranges for class bodies
    replacements = []
    for child in root_node.children:
        if child.type == 'class_declaration':
            for subchild in child.children:
                if subchild.type == 'class_body':
                    replacements.append((subchild.start_byte, subchild.end_byte))
                    break
    
    # Sort replacements in reverse order to avoid position shifts
    replacements.sort(reverse=True)
    
    # Apply replacements to the code
    modified_code_bytes = code_bytes
    for start, end in replacements:
        modified_code_bytes = modified_code_bytes[:start] + b'{...}' + modified_code_bytes[end:]
    
    # Decode the modified bytes back to a string
    return modified_code_bytes.decode('utf8')