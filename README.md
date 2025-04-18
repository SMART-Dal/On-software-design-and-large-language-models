# On Software Design and Large Language Models

This repository contains two subprojects: a maven-based Java subproject that generates the benchmark data out of a Java repository, and a Python subproject that implements model inference and evaluation logic.

## Data Generation
We use [spoon](https://spoon.gforge.inria.fr/) to introduce a set of perturbations that generate suboptimal source code from a design a perspective, i.e., tightly coupled and loosely cohesive code fragments. To build the executable JAR file, first, navigate to the project's source directory `data-generator` and build the project:

```bash
mvn clean package
```
If successfull, a JAR file `data-generator-1.0-SNAPSHOT-jar-with-dependencies.jar` will be generated and stored in the `data-generator/target` directory.  

To run the transformations on a Java project, execute the following command:
```bash
java -jar target/data-generator-1.0-SNAPSHOT-jar-with-dependencies.jar <JAVA_PROJECT_DIR> <TRANSFORMATIONS>
```
Note that multiple transformation can be applied concurrently. This is done by passing the names of the transformations as comma separated list as arguments. In the section below, you will find the name and role of each transformation.
### Supported Transformations

The following table illustrates the supported transformations,

| Transformation                       | Description                                                                                                                                                                | Arg                 | Transformation Specific Arg | Output                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | Status      |
|--------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------|-----------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------|
| Direct Instantiation of Dependencies | Replaces the injected dependencies of a class with a direct instantiation. It removes the parameters from DI sites such as constructors and setters.                       | directinstantiation | N/a                         | This transformation will generate a folder called `<PROJECT_NAME>-transformed` and a JSON file `<PROJECT_NAME>_dependencies.json`. The folder contains the original project with modified classes where the transformation was applied. The JSON file contains a dictionary specifying the modified classes using the transformation.  A key represents the file path of the modified Java class, whereas the value is an array that contains the metadata of the dependencies that were initialized. | Implemented |
| Dependency Graph                     | Generates all disjoint class pairs in the project. A disjoint class pairs means that the two classes are dependent on each other, either directly on transtively.          | dependencygraph     | N/a                         | This transformation will generate a JSON file `<PROJECT_NAME>_dependencies.json` that contains the pairs of independent Java classes.                                                                                                                                                                                                                                                                                                                                                                 | Implemented |
| Disable Abstraction                  | Replaces the abstract type of parameters of a class constructor with a concrete type. Example: public FooClass(IType parameter) -> public FooClass(ConreteType parameter.) | disableabstraction  | N/a                         |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Pending     |
| God Class                            | Adds methods to a certain class from randomly selected classes.                                                                                                            | godclass            | N/a                         |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Pending     |
| Feature Envy                         | Injects a Feature Envy code smell into a class. For more information about this smell, you can check this [definition](https://tusharma.in/smells/FE.html)                 | featureenvy         | N/a                         |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | Pending     |


Note that the implementation is not optimized. It might take time to apply each transformation if the project size is big. On average, you should expect a few seconds for medium sized project.

## Inference and Evaluation

### Prompt Generation

Currently, the script is taylored towards the Direct Instantiation of Dependencies perturbation. As other transformations become available, this subproject will be further refined.

#### Basic Command
```bash
python generate_prompts.py \
  --project_name PROJECT_NAME \
  --perturbed_project_path PATH/TO/PERTURBED_CLASSES \
  --readme_path PATH/TO/README.md \
  --disjoint_json PATH/TO/DISJOINT_PAIRS.json \
  --perturbed_json PATH/TO/PERTURBED_CLASSES.json \
  --output_prompt OUTPUT_DIRECTORY \
  --model_tag MODEL_NAME \
  [--n_shuffles NUM] \
  [--prompt_template TEMPLATE_TYPE] \
  [--perturbation_types PERTURBATION_LIST]
```

#### Required Arguments
| Argument | Description |
|----------|-------------|
| `--project_name` | Name of your Java project |
| `--perturbed_project_path` | Path to directory containing perturbed Java classes after running the JAR file. |
| `--readme_path` | Path to project's README file |
| `--disjoint_json` | JSON file containing disjoint class pairs. This is the file obtained from running the JAR file. |
| `--perturbed_json` | JSON file with perturbed classes and dependencies. This is obtained after applying the DiD transformation using the JAR file. |
| `--output_prompt` | Output directory for generated prompts |
| `--model_tag` | Hugging Face model ID (e.g., `deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B`) |

#### Optional Parameters
| Parameter | Default | Description |
|-----------|---------|-------------|
| `--n_shuffles` | 1 | Number of prompt variations to generate through shuffling |
| `--prompt_template` | retrieval_based | Template type: `retrieval_based` or `binary_based` |
| `--perturbation_types` | did,dal,gc,feii | Space-separated list of perturbation types used |
| `--seed` | 42 | Random seed for reproducibility |

#### Example Command
```bash
python generate_prompts.py \
  --project_name my_java_project \
  --perturbed_project_path data/perturbed_classes \
  --readme_path docs/README.md \
  --disjoint_json metadata/disjoint_pairs.json \
  --perturbed_json metadata/perturbed.json \
  --output_prompt outputs/prompts \
  --model_tag codellama/CodeLlama-7b-hf \
  --n_shuffles 3 \
  --prompt_template binary_based \
  --perturbation_types did feii
```

### Output Files
The script generates these files in the output directory:
- **Prompt Files**: 
  - Format: `{project}_{perturbations}_{ratio}_{template}_{shuffle}.txt`
  - Example: `my_java_project_did-feii_0.5_binary_based_2.txt`
  
- **Metadata Files**:
  - Contains token counts and class statistics
  - Format: `{project}_{perturbations}_{ratio}_metadata.json`

- **Ground Truth Files**:
  - For retrieval-based: `{project}_ground_truth.json`
  - For binary-based: `{project}_{ratio}_ground_truth.json`

  