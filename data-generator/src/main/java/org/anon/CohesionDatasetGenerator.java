package org.anon;

import spoon.MavenLauncher;
import spoon.reflect.declaration.CtClass;

import java.io.File;
import java.util.*;

public class CohesionDatasetGenerator {

    /**
     * Main class to generate the dataset for cohesion experiments.
     *
     * Workflow:
     * 1. Selects highly cohesive, non-trivial "atomic" classes from a project. Filters: YALCOM = 0 AND #methods > 2
     * 2. For each pair of atomic classes, it treats one as a target and one as a source.
     * 3. For predefined distortion ratios, it injects methods (and their dependencies) from the source into the target.
     * 4. For each generated class, it creates prompts and ground truth for all three experimental tasks.
     * 5. Saves the complete dataset entry as a JSON file.
     *
     * Usage: java -cp "path/to/jar" con.smart.DatasetGenerator /path/to/project /path/to/metrics.csv /path/to/output_dir
     */

    // Represents a single, highly-cohesive class selected as a building block.
    public record CandidateClass(CtClass<?> ctClass, Set<String> methods) {}

    // Represents detailed information about an original class.
    public record OriginalClassInfo(String className, String filePath, String content) {}

    // Represents the result of an injection operation.
    public record InjectionResult(CtClass<?> generatedClass, Map<String, Set<String>> injectedResponsibilities) {}

    // Represents a single data point for the experiment dataset.
    public record DatasetEntry(String generatedClassName, String sourceCode, String prompt, String groundTruth, String taskType, int distortionLevel, OriginalClassInfo targetClass, List<OriginalClassInfo> sourceClasses) {}


    public static void main(String[] args) {
        if (args.length != 3) {
            System.out.println("Usage: java -cp \"path/to/spoon-core-all.jar:path/to/gson.jar:.\" DatasetGenerator /path/to/project /path/to/metrics.csv /path/to/output_dir");
            return;
        }

        String projectPath = args[0];
        String csvPath = args[1];
        String outputDir = args[2];

        new File(outputDir).mkdirs();

        System.out.println("Step 1: Selecting candidate classes...");
        CohesionCandidateSelector selector = new CohesionCandidateSelector();
        List<CandidateClass> candidates = selector.selectCandidates(projectPath, csvPath);
        System.out.println("Selected " + candidates.size() + " atomic candidate classes.");

        if (candidates.size() < 2) {
            System.err.println("Need at least 2 candidate classes to create examples. Exiting.");
            return;
        }

        System.out.println("\nStep 2 & 3: Generating low-cohesion classes by injecting methods...");
        MavenLauncher launcher = new MavenLauncher(projectPath, MavenLauncher.SOURCE_TYPE.APP_SOURCE);
        launcher.getEnvironment().setAutoImports(true);
        launcher.getEnvironment().setCommentEnabled(true);
        launcher.getEnvironment().setNoClasspath(true);
        launcher.getEnvironment().setIgnoreDuplicateDeclarations(true);
        CohesionInjector injector = new CohesionInjector(launcher.getFactory());
        CohesionGroundTruthGenerator groundTruthGenerator = new CohesionGroundTruthGenerator(outputDir);

        // Define the distortion levels to generate
        List<Integer> distortionLevels = List.of(1, 2, 3, 4, 5, 6, 7, 8, 9);

        for (CandidateClass targetCandidate : candidates) {
            for (int N : distortionLevels) {
                List<CandidateClass> potentialSources = new ArrayList<>(candidates);
                potentialSources.remove(targetCandidate);
                potentialSources.removeIf(source -> sharesCommonAncestor(targetCandidate.ctClass(), source.ctClass()));

                if (potentialSources.size() < N) {
                    continue; // Not enough valid sources for this N
                }

                Collections.shuffle(potentialSources);
                List<CandidateClass> selectedSources = potentialSources.subList(0, N);

                InjectionResult result = injector.inject(targetCandidate.ctClass(), selectedSources);
                if (result != null && !result.injectedResponsibilities().isEmpty()) {
                    groundTruthGenerator.generateAndAccumulate(result, targetCandidate, selectedSources, N);
                }
            }
        }
        // Step 4: Write the aggregated results to the final JSON files.
        System.out.println("\nStep 4: Writing aggregated JSON files...");
        groundTruthGenerator.writeAggregatedFiles();

        System.out.println("\nDataset generation complete. Files saved to: " + outputDir);
    }

    private static boolean sharesCommonAncestor(CtClass<?> classA, CtClass<?> classB) {
        Set<String> chainA = CohesionCandidateSelector.getInheritanceChain(classA);
        Set<String> chainB = CohesionCandidateSelector.getInheritanceChain(classB);
        Set<String> intersection = new HashSet<>(chainA);
        intersection.retainAll(chainB);
        return !intersection.isEmpty();
    }
}
