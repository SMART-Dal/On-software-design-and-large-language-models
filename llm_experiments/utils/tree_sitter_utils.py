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

def extract_method_names_from_class(code: str, parser: Parser) -> List[str]:
    """
    Extracts method names by manually traversing the syntax tree.

    This function parses the code and recursively visits every node. If a node
    of type 'method_declaration' is found, it extracts the identifier from its
    'name' field.

    Args:
        code: A string containing the Java class code.
        parser: A pre-configured tree-sitter Parser instance with the Java
                language loaded.

    Returns:
        A list of strings, where each string is a found method name.
    """
    # 1. Parse the code to get the tree
    tree = parser.parse(bytes(code, "utf8"))
    root_node = tree.root_node

    method_names = []

    # 2. Define a recursive function to walk the tree
    def traverse_tree(node: Node):
        # 3. Check the type of the current node
        if node.type == 'method_declaration':
            # This node is a method. Now, we need to find the node
            # containing its name. The Java grammar assigns the method's
            # identifier to a field named 'name'.
            name_node = node.child_by_field_name('name')
            if name_node:
                method_name = name_node.text.decode('utf8')
                method_names.append(method_name)

        # 4. Recursively call this function for all children of the current node
        for child in node.children:
            traverse_tree(child)

    # 5. Start the traversal from the root node
    traverse_tree(root_node)

    return method_names

if __name__ == "__main__":
    # 1. Set up the parser (this will clone and build the grammar on first run)
    JAVA_LANGUAGE = Language(tsjava.language())
    parser = Parser(JAVA_LANGUAGE)

    # 2. Define an example Java class with various constructs
    java_code_example = """
public class GeneratedClass34ec2475<E> implements Queue<E> {
    JAVA("java", "java")
    private int limit;
    Queue<E> queue = new ConcurrentLinkedQueue<>();
    public GeneratedClass34ec2475(int limit) {
        this.limit = limit;
    }
    private final LFLog LOG = LFLoggerManager.getLogger(this.getClass());
    @Override
    public boolean offer(E e) {
        if (queue.size() >= limit) {
            queue.poll();
        }
        return queue.offer(e);
    }
    private ScriptExecutor scriptExecutor;
    @Override
    public E poll() {
        return queue.poll();
    }
    public Queue<E> getQueue() {
        return queue;
    }
    @Override
    public void loadScript(String script, String language) {
        scriptExecutor = ScriptExecutorFactory.loadInstance().getScriptExecutor(language);
        scriptExecutor.load(getNodeId(), script);
    }
    public int getLimit() {
        return limit;
    }
    @Override
    public boolean add(E e) {
        return queue.add(e);
    }
    @Override
    public E element() {
        return queue.element();
    }
    @Override
    public E peek() {
        return queue.peek();
    }
    @Override
    public boolean isEmpty() {
        return queue.size() == 0 ? true : false;
    }
    @Override
    public int size() {
        return queue.size();
    }
    @Override
    public E remove() {
        return queue.remove();
    }
    @Override
    public boolean addAll(Collection<? extends E> c) {
        return queue.addAll(c);
    }
    @Override
    public void clear() {
        queue.clear();
    }
    @Override
    public boolean isEnd() {
        if (!ScriptTypeEnum.JAVA.getDisplayName().equals(this.getRefNode().getLanguage())) {
            return super.isEnd();
        }
        ScriptExecuteWrap wrap = this.buildWrap(this);
        return scriptExecutor.executeIsEnd(wrap);
    }
    @Override
    public boolean contains(Object o) {
        return queue.contains(o);
    }
    @Override
    public boolean containsAll(Collection<?> c) {
        return queue.containsAll(c);
    }
    @Override
    public Iterator<E> iterator() {
        return queue.iterator();
    }
    @Override
    public void beforeProcess() {
        ScriptExecuteWrap wrap = this.buildWrap(this);
        scriptExecutor.executeBeforeProcess(wrap);
    }
    @Override
    public boolean remove(Object o) {
        return queue.remove(o);
    }
    @Override
    public boolean removeAll(Collection<?> c) {
        return queue.removeAll(c);
    }
    @Override
    public boolean retainAll(Collection<?> c) {
        return queue.retainAll(c);
    }
    @Override
    public Object[] toArray() {
        return queue.toArray();
    }
    @Override
    public <T> T[] toArray(T[] a) {
        return queue.toArray(a);
    }
}
"""

    # 3. Run the skeletonization function
    method_names = extract_method_names_from_class(java_code_example, parser)
    print(method_names)
