HYBRID_PROMPT =  """
You are an expert software engineer that understands code quality. You are given a Java project named {project_name}. Below is the content of its README file to provide context about its purpose:
## README:
{project_readme}

## Task:
You will be given a list of Java classes and your task is to determine which classes they are tightly coupled with from a bigger list, if any. Tightly coupled classes are those with strong dependencies, where one or both classes rely heavily on the other, making them difficult to modify or test independently. The list of names of classes is as follows:

{classes_under_analysis}

At the end of the prompt, you will be provided with the body of all classes. You should analyze the code and determine which classes from the list below, are tightly coupled with those mentioned above. Note that you should NOT consider primitive types (e.g., int, float) as classes. You should only consider the classes that are provided in the list of class bodies below. For instance, if a class X has dependency with class Y, but class Y is not in the list of class bodies, you should not consider it as tightly coupled.

## Response Format:
Assuming you are given this list of class names: ["Class1", "Class2", "Class3"]

And the following list of class bodies:
- Class1
- Class2
- Class3
- Class8
- Class9
- Class10

You must provide your response in the following format:
```json
[
    ["Class1", "Class8"],
    [Class1, "Class9"],
    ["Class2", "None"],
    ["Class3", "Class10"]
    ...
]
```
In this scenario, Class1 is tightly coupled with classes Class8 and Class9, Class2 is not coupled with none of the classes and Class3 is tightly coupled with Class10. You should only provide a classe's simple name, where the simple name is the class name without the package prefix (e.g., 'Class' instead of 'com.foo.bar.Class'). Do not include any additional text or explanations. Just provide the JSON response.
## Classes:
{list_of_classes}
"""

RETRIEVAL_BASED_COUPLING = """
You are an expert software engineer that understands code quality. You are given a Java project named {project_name}. Below is the content of its README file to provide context about its purpose:

## README:
{project_readme}

## Task:
Your task is to analyze the dependencies between these classes and identify any tightly coupled classes. Tightly coupled classes are those with strong dependencies on each other, making them difficult to modify or test independently. 

Please provide the list of pairs of classes that you think are tightly coupled. For example, if you think a Java class A is tightly coupled with classes B and C, you should provide the following tuple: [ [A, B] [A, C] ].
Note that you should NOT consider primitive types (e.g., int, float) as classes.

## Response Format:
Please provide your response in the following format:
```json
[
    ["Class1", "Class2"],
    [Class1, "Class3"],
    ["Class5", "Class8"]
    ...
]
```
In this case, Class1 is tightly coupled with Class2 and Class3, and Class5 is tightly coupled with Class8. Note that these are arbitrary examples and may not be true for the given project.
If no classes are tightly coupled, please provide an empty list []. You should only provide the classe's simple name, where the simple name is the class name without the package prefix (e.g., 'Class' instead of 'com.foo.bar.Class'). Do not include any additional text or explanations. Just provide the JSON response.

## Classes:
{list_of_classes}
"""

BINARY_BASED_COUPLING = """
You are an expert software engineer that understands code quality. You are given a Java project named {project_name}. Below is the content of its README file to provide context about its purpose:

## README:
{project_readme}

## Task:
You will be given a list of pairs of Java classes and your task is to determine whether they are tightly coupled or not. Tightly coupled classes are those with strong dependencies, where one or both classes rely heavily on the other, making them difficult to modify or test independently. The list of pairs of classes is as follows:

{class_pair}

At the end of the prompt, you will be provided with the body of each class. You should analyze the code and determine whether the classes in each pair above are tightly coupled or not. Note that you should NOT consider primitive types (e.g., int, float) as classes. You should only consider the classes that are provided in the list of class bodies below. For instance, if a class X has dependency with class Y, but class Y is not in the list of class bodies, you should not consider it as tightly coupled.

## Response Format:
For each pair, you must provide your response in the following format:
```json
{{
    "pair": <PAIR-NAME>,
    "coupled": TRUE/FALSE,
}}
```
For example, if you are provided with the following list of pairs:
```
[
    ["ClassA", "ClassB"],
    ["ClassC", "ClassD"]
]
```
You should provide the following response:
```json
[
    {{
        "pair": ["ClassA", "ClassB"],
        "coupled": TRUE
    }},
    {{
        "pair": ["ClassC", "ClassD"],
        "coupled": FALSE
    }}
]
```
Do not include any additional text or explanations. Just provide the JSON response.
## Classes:
{list_of_classes}

"""