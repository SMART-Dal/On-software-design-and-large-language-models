package org.smart;

import spoon.MavenLauncher;
import spoon.reflect.declaration.CtClass;

import java.io.File;
import java.util.List;
import java.util.Set;

public class CohesionDatasetGenerator {

    // Represents a single, highly-cohesive class selected as a building block.
    public record CandidateClass(CtClass<?> ctClass, Set<String> methods) {}

    // Represents detailed information about an original class used in a merge.
    public record OriginalClassInfo(String className, String filePath, String content) {}

    // Represents a single data point for the experiment dataset.
    public record DatasetEntry(String mergedClassName, String sourceCode, String prompt, String groundTruth, String taskType, double distortionRatio, List<OriginalClassInfo> originalClasses) {}


    public static void main(String[] args) {
        if (args.length != 3) {
            System.out.println("Usage: java -cp \"path/to/spoon-core-all.jar:path/to/gson.jar:.\" DatasetGenerator /path/to/project /path/to/metrics.csv /path/to/output_dir");
            return;
        }

        String projectPath = args[0];
        String csvPath = args[1];
        String outputDir = args[2];

        // Ensure output directory exists
        new File(outputDir).mkdirs();

        // Step 1: Select Candidate Classes
        System.out.println("Step 1: Selecting candidate classes...");
        CohesionCandidateSelector selector = new CohesionCandidateSelector();
        List<CandidateClass> candidates = selector.selectCandidates(projectPath, csvPath);
        System.out.println("Selected " + candidates.size() + " atomic candidate classes.");

        if (candidates.size() < 2) {
            System.err.println("Need at least 2 candidate classes to create merged examples. Exiting.");
            return;
        }

        // Step 2 & 3: Systematically Generate Low-Cohesion Classes
        System.out.println("\nStep 2 & 3: Generating low-cohesion classes by merging candidates...");
        MavenLauncher launcher = new MavenLauncher(projectPath, MavenLauncher.SOURCE_TYPE.APP_SOURCE);
        launcher.getEnvironment().setAutoImports(true);
        launcher.getEnvironment().setCommentEnabled(true);
        launcher.getEnvironment().setNoClasspath(true);
        launcher.getEnvironment().setIgnoreDuplicateDeclarations(true);
        CohesionClassMerger merger = new CohesionClassMerger(launcher.getFactory());
        CohesionGroundTruthGenerator groundTruthGenerator = new CohesionGroundTruthGenerator(outputDir);

        // For this project, we will generate pairs. This can be extended to triplets, etc.
        for (int i = 0; i < candidates.size(); i++) {
            for (int j = i + 1; j < candidates.size(); j++) {
                List<CandidateClass> toMerge = List.of(candidates.get(i), candidates.get(j));

                // Merge the classes
                CtClass<?> mergedClass = merger.mergeClasses(toMerge);
                if (mergedClass == null) continue;

                // Step 4 & 5: Generate and Save Ground Truth
                groundTruthGenerator.generateAndSave(mergedClass, toMerge);
            }
        }
        System.out.println("\nDataset generation complete. Files saved to: " + outputDir);
    }
}
