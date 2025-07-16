import re

def remove_comments_and_docstrings(source):
    def replacer(match):
        s = match.group(0)
        if s.startswith('/'):
            return " " # note: a space and not an empty string
        else:
            return s
    pattern = re.compile(
        r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"',
        re.DOTALL | re.MULTILINE
    )
    temp=[]
    for x in re.sub(pattern, replacer, source).split('\n'):
        if x.strip()!="":
            temp.append(x)
    return '\n'.join(temp)

def fix_nested_class_paths(data: list) -> list:
    """
    Corrects file paths for nested Java classes within a loaded data structure.

    Args:
        data (list): A list of dictionaries representing dependencies.

    Returns:
        list: The list with corrected file paths for nested classes.
    """
    for item in data:
        class_name = item.get("dependencyClassName", "")
        
        # Check if it's a nested class by looking for '$'
        if '$' in class_name:
            # The simple name of the nested class (e.g., "CommandProcessImpl")
            nested_class_simple_name = class_name.split('$')[-1]

            # The full name of the outer class (e.g., "c.t.a.c.s.s.i.ProcessImpl")
            outer_class_full_name = class_name.rsplit('$', 1)[0]
            
            # The simple name of the outer class (e.g., "ProcessImpl")
            outer_class_simple_name = outer_class_full_name.split('.')[-1]
            
            # Get the package path from the outer class's full name
            # e.g., "com/taobao/arthas/core/shell/system/impl"
            try:
                package_path = outer_class_full_name.rsplit('.', 1)[0].replace('.', '/')
                # Construct the correct file path using the outer class name
                correct_file_path = f"{package_path}/{outer_class_simple_name}.java"
            except IndexError:
                # Handles cases where the class is in the default package
                correct_file_path = f"{outer_class_simple_name}.java"

            # 1. Update the main file path
            item["dependencyClassFilePath"] = correct_file_path
            
            # 2. Update the file path within the dependency chain
            for chain_link in item.get("dependencyChain", []):
                # Find the chain link corresponding to the nested class
                if chain_link.get("className") == nested_class_simple_name:
                    chain_link["filePath"] = correct_file_path
                    
    return data