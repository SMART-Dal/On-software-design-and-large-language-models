package org.smart;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import spoon.reflect.declaration.CtClass;

import java.io.FileWriter;
import java.io.IOException;
import java.nio.file.Paths;
import java.util.*;

public class CohesionGroundTruthGenerator {
    private final String outputDir;
    private final Gson gson = new GsonBuilder().setPrettyPrinting().create();
    private int entryCounter = 0;

    public CohesionGroundTruthGenerator(String outputDir) {
        this.outputDir = outputDir;
    }

    public void generateAndSave(CtClass<?> mergedClass, List<CohesionDatasetGenerator.CandidateClass> originalCandidates) {
        String sourceCode = mergedClass.toString();
        List<String> originalClassNames = originalCandidates.stream().map(c -> c.ctClass().getQualifiedName()).toList();

        List<CohesionDatasetGenerator.OriginalClassInfo> originalClassInfo = originalCandidates.stream()
                .map(c -> {
                    CtClass<?> ctClass = c.ctClass();
                    String className = ctClass.getQualifiedName();
                    String filePath = ctClass.getPosition().getFile().getAbsolutePath();
                    String content = ctClass.toString();
                    return new CohesionDatasetGenerator.OriginalClassInfo(className, filePath, content);
                })
                .toList();

        generateRetrievalTask(mergedClass, originalCandidates, sourceCode, originalClassInfo);
        generateBinaryAndHybridTasks(mergedClass, originalCandidates, sourceCode, originalClassInfo);
    }

    private void generateRetrievalTask(CtClass<?> mergedClass, List<CohesionDatasetGenerator.CandidateClass> candidates, String sourceCode, List<CohesionDatasetGenerator.OriginalClassInfo> originalNames) {
        String prompt = String.format("You are an expert software engineer that understands code quality. A cohesive class is one with a single, well-defined responsibility, where all its methods and properties are united in serving a common purpose. A class with low cohesion handles multiple, unrelated responsibilities. The following Java class `%s` appears to handle multiple distinct responsibilities. Group all methods of this class into distinct sets based on the responsibility each set addresses.", mergedClass.getSimpleName());

        Map<String, Set<String>> groundTruthMap = new HashMap<>();
        for (int i = 0; i < candidates.size(); i++) {
            groundTruthMap.put("Responsibility" + (i + 1), candidates.get(i).methods());
        }
        String groundTruthJson = gson.toJson(groundTruthMap);

        double distortion = calculateDistortion(candidates, Collections.emptySet());
        CohesionDatasetGenerator.DatasetEntry entry = new CohesionDatasetGenerator.DatasetEntry(mergedClass.getSimpleName(), sourceCode, prompt, groundTruthJson, "Retrieval", distortion, originalNames);
        saveEntry(entry);
    }

    private void generateBinaryAndHybridTasks(CtClass<?> mergedClass, List<CohesionDatasetGenerator.CandidateClass> candidates, String sourceCode, List<CohesionDatasetGenerator.OriginalClassInfo> originalNames) {
        for (int i = 0; i < candidates.size(); i++) {
            List<String> component1 = new ArrayList<>(candidates.get(i).methods());
            if (component1.size() < 2) continue;

            String positiveBinaryPrompt = String.format("You are an expert software engineer that understands code quality. A cohesive class is one with a single, well-defined responsibility, where all its methods and properties are united in serving a common purpose. A class with low cohesion handles multiple, unrelated responsibilities. Given the Java class `%s`, are the methods `[%s, %s]` cohesive and part of a single, well-defined responsibility? Answer with only \"Yes\" or \"No\".", mergedClass.getSimpleName(), component1.get(0), component1.get(1));
            CohesionDatasetGenerator.DatasetEntry posBinaryEntry = new CohesionDatasetGenerator.DatasetEntry(mergedClass.getSimpleName(), sourceCode, positiveBinaryPrompt, "Yes", "Binary", calculateDistortion(candidates, candidates.get(i).methods()), originalNames);
            saveEntry(posBinaryEntry);

            String seedMethod = component1.get(0);
            List<String> otherMethods = new ArrayList<>(component1);
            otherMethods.remove(seedMethod);
            String hybridPrompt = String.format("You are an expert software engineer that understands code quality. A cohesive class is one with a single, well-defined responsibility, where all its methods and properties are united in serving a common purpose. A class with low cohesion handles multiple, unrelated responsibilities. Consider the method `%s` in class `%s`. Identify all other methods in this class that belong to the same cohesive responsibility.", seedMethod, mergedClass.getSimpleName());
            CohesionDatasetGenerator.DatasetEntry hybridEntry = new CohesionDatasetGenerator.DatasetEntry(mergedClass.getSimpleName(), sourceCode, hybridPrompt, String.join(", ", otherMethods), "Hybrid", calculateDistortion(candidates, candidates.get(i).methods()), originalNames);
            saveEntry(hybridEntry);

            if (i + 1 < candidates.size()) {
                List<String> component2 = new ArrayList<>(candidates.get(i + 1).methods());
                if (component2.isEmpty()) continue;
                String negativeBinaryPrompt = String.format("You are an expert software engineer that understands code quality. A cohesive class is one with a single, well-defined responsibility, where all its methods and properties are united in serving a common purpose. A class with low cohesion handles multiple, unrelated responsibilities. Given the Java class `%s`, are the methods `[%s, %s]` cohesive and part of a single, well-defined responsibility? Answer with only \"Yes\" or \"No\".", mergedClass.getSimpleName(), component1.get(0), component2.get(0));
                CohesionDatasetGenerator.DatasetEntry negBinaryEntry = new CohesionDatasetGenerator.DatasetEntry(mergedClass.getSimpleName(), sourceCode, negativeBinaryPrompt, "No", "Binary", calculateDistortion(candidates, Collections.emptySet()), originalNames);
                saveEntry(negBinaryEntry);
            }
        }
    }

    private double calculateDistortion(List<CohesionDatasetGenerator.CandidateClass> allCandidates, Set<String> signalMethods) {
        if (signalMethods.isEmpty()) return 0.0;
        long totalMethods = allCandidates.stream().mapToLong(c -> c.methods().size()).sum();
        long signalCount = signalMethods.size();
        long distractorCount = totalMethods - signalCount;
        return (double) distractorCount / totalMethods;
    }

    private void saveEntry(CohesionDatasetGenerator.DatasetEntry entry) {
        String fileName = String.format("%s_%s_%d.json", entry.mergedClassName(), entry.taskType(), ++entryCounter);
        try (FileWriter writer = new FileWriter(Paths.get(outputDir, fileName).toString())) {
            gson.toJson(entry, writer);
        } catch (IOException e) {
            System.err.println("Failed to write JSON file: " + fileName);
            e.printStackTrace();
        }
    }
}
