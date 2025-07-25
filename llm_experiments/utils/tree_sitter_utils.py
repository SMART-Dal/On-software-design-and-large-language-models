from tree_sitter import Parser, Language, Node
from typing import Set, List
import tree_sitter_java as tsjava

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

def find_method_bodies_recursive(
    node: Node,
    code_bytes: bytes,
    excluded_methods: Set[str],
    nodes_to_replace: List[Node]
):
    """
    Recursively traverses the syntax tree to find method bodies, excluding
    methods whose names are in the exclusion set.

    This function uses `child_by_field_name` for robustly finding the name
    and body of a method.
    """
    # If the current node is a method declaration, we process it.
    if node.type == 'method_declaration':
        name_node = node.child_by_field_name('name')
        body_node = node.child_by_field_name('body')

        # Proceed only if both name and body are found
        if name_node and body_node:
            # Extract the method name as a string
            method_name = code_bytes[name_node.start_byte:name_node.end_byte].decode('utf8')
            
            # If the method name is NOT in the exclusion set, add its body
            # to the list of nodes that need to be replaced.
            if method_name not in excluded_methods:
                nodes_to_replace.append(body_node)
        
        # We have processed this method declaration, so we don't need to
        # recurse into its children. We will continue the traversal with
        # its siblings in the parent's loop.
        return

    # For any other node type, continue the traversal with its children.
    for child in node.children:
        find_method_bodies_recursive(child, code_bytes, excluded_methods, nodes_to_replace)


def remove_method_bodies(
    code: str,
    parser: Parser,
    excluded_methods: Set[str] = None,
    verbose: bool = False
) -> str:
    """
    Removes the bodies of methods in a Java code string, with an option to exclude
    certain methods from this process using recursive tree traversal.

    Args:
        code: A string containing the Java source code.
        parser: A tree-sitter Parser instance configured for Java.
        excluded_methods: A set of method names (as strings) that should NOT have
                          their bodies replaced.
        verbose: If True, prints diagnostic information to the console.

    Returns:
        A string containing the Java code with specified method bodies replaced.
    """
    # Ensure excluded_methods is a set for efficient lookup
    if excluded_methods is None:
        excluded_methods = set()

    # Convert code to bytes for parsing and slicing
    code_bytes = bytes(code, "utf8")
    tree = parser.parse(code_bytes)
    root_node = tree.root_node

    # Check for parsing errors
    if root_node.has_error and verbose:
        print("Warning: Tree-sitter detected syntax errors in the provided Java code.")

    # Find all method body nodes using the recursive traversal function
    nodes_to_replace = []
    find_method_bodies_recursive(root_node, code_bytes, excluded_methods, nodes_to_replace)

    if verbose:
        print(f"Diagnostic: Found {len(nodes_to_replace)} method bodies to replace.")

    # If no method bodies were found, return the original code
    if not nodes_to_replace:
        return code

    # Use a bytearray for efficient modification
    code_bytearray = bytearray(code_bytes)
    placeholder = b"{ /* ... method body omitted ... */ }"

    # Iterate over the found nodes in REVERSE order to avoid messing up
    # the byte offsets of subsequent replacements.
    for node in reversed(nodes_to_replace):
        start = node.start_byte
        end = node.end_byte
        code_bytearray[start:end] = placeholder

    # Decode the modified byte array back into a string and return it.
    return code_bytearray.decode("utf8")


if __name__ == "__main__":
    # 1. Set up the parser (this will clone and build the grammar on first run)
    JAVA_LANGUAGE = Language(tsjava.language())
    parser = Parser(JAVA_LANGUAGE)

    # 2. Define an example Java class with various constructs
    java_code_example = """
package com.example;

import java.util.List;
import java.util.stream.Collectors;

public class Bar {
    private IDependency myDep;
    private IAnotherDependency anotherDep = new AnotherDep();
    private String name;

    // This constructor's body should be PRESERVED because it contains
    // the tight coupling evidence we want the LLM to find.
    public Bar(String name) {
        this.myDep = new ImplementationDep();
        this.name = name;
    }

    // The body of this public method should be REMOVED.
    public String processData(List<String> data) {
        System.out.println("Processing " + data.size() + " items for " + this.name);
        String result = data.stream()
            .map(String::toUpperCase)
            .filter(s -> s.startsWith("A"))
            .collect(Collectors.joining(", "));
        myDep.execute(result);
        return "Done";
    }

    // The body of this simple getter that should NOT be removed.
    public String getName() {
        return this.name;
    }

    // The body of this private helper method should also be REMOVED.
    private void internalHelper() {
        System.out.println("Internal logic...");
    }
}
"""

    # 3. Run the skeletonization function
    print("--- Original Code ---")
    print(java_code_example)

    skeleton_code = remove_method_bodies(java_code_example, parser, excluded_methods={"getName"})

    print("\n--- Skeletonized Code ---")
    print(skeleton_code)
