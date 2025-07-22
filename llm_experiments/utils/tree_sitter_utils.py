from tree_sitter import Parser, Language
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

def find_method_bodies_recursive(node, nodes_to_replace):
    """
    Recursively traverses the syntax tree to find method bodies.

    Args:
        node: The current tree-sitter Node to inspect.
        nodes_to_replace: A list to append found method body nodes to.
    """
    # If the node is a method declaration, we've found what we're looking for.
    if node.type == 'method_declaration':
        # The body of a method is typically a 'block' node. We find it among
        # the children of the method_declaration node.
        for child in node.children:
            if child.type == 'block':
                nodes_to_replace.append(child)
                # Once we find the body, we don't need to check other children
                # of this method, so we stop the inner loop.
                break
        # We don't recurse further into the method_declaration itself.
        return

    # If the current node is not a method, continue traversing its children.
    for child in node.children:
        find_method_bodies_recursive(child, nodes_to_replace)


def remove_method_bodies(code: str, parser: Parser, verbose: bool = False) -> str:
    """
    Removes the bodies of all methods in a Java code string by iterating
    through the syntax tree and identifying nodes of type 'method_declaration'.

    Args:
        code: A string containing the Java source code.
        parser: A tree-sitter Parser instance configured for Java.

    Returns:
        A string containing the skeletonized Java code.
    """
    # Parse the source code into a syntax tree
    tree = parser.parse(bytes(code, "utf8"))
    root_node = tree.root_node

    # Check for parsing errors
    if root_node.has_error and verbose:
        print("Warning: Tree-sitter detected syntax errors in the provided Java code.")

    # Find all method body nodes using the recursive traversal function
    nodes_to_replace = []
    find_method_bodies_recursive(root_node, nodes_to_replace)
    if verbose:
        print(f"Diagnostic: Found {len(nodes_to_replace)} method bodies to replace.")

    # If no method bodies were found, return the original code
    if not nodes_to_replace:
        return code

    # Convert the source code to a byte array for efficient modification
    code_bytes = bytearray(code, "utf8")
    placeholder = b"{ /* ... method body omitted ... */ }"

    # Iterate over the found nodes in REVERSE order to avoid messing up
    # the byte offsets of subsequent replacements.
    for node in reversed(nodes_to_replace):
        start = node.start_byte
        end = node.end_byte
        code_bytes[start:end] = placeholder

    # Decode the modified byte array back into a string and return it.
    return code_bytes.decode("utf8")


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

    // The body of this simple getter should also be REMOVED.
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

    skeleton_code = remove_method_bodies(java_code_example, parser)

    print("\n--- Skeletonized Code ---")
    print(skeleton_code)
