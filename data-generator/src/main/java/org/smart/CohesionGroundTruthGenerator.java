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
    private final Map<Double, List<CohesionDatasetGenerator.DatasetEntry>> binaryEntries = new HashMap<>();
    private final Map<Double, List<CohesionDatasetGenerator.DatasetEntry>> hybridEntries = new HashMap<>();
    private final Map<Double, List<CohesionDatasetGenerator.DatasetEntry>> retrievalEntries = new HashMap<>();
    private int entryCounter = 0;
    private final static String PROMPT_PREFIX = "You are an expert software engineer that understands code quality. A cohesive class is one with a single, well-defined responsibility, where all its methods and properties are united in serving a common purpose. A class with low cohesion handles multiple, unrelated responsibilities.";

    public CohesionGroundTruthGenerator(String outputDir) {
        this.outputDir = outputDir;
    }

    public void generateAndAccumulate(CohesionDatasetGenerator.InjectionResult result, CohesionDatasetGenerator.CandidateClass source, CohesionDatasetGenerator.CandidateClass target, double distortionRatio) {
        CtClass<?> generatedClass = result.generatedClass();
        String sourceCode = generatedClass.toString();

        CohesionDatasetGenerator.OriginalClassInfo sourceInfo = candidateToInfo(source);
        CohesionDatasetGenerator.OriginalClassInfo targetInfo = candidateToInfo(target);

        Set<String> targetMethods = target.methods();
        Set<String> injectedMethods = result.injectedMethods();

        // Generate for all three tasks
        generateRetrievalTask(generatedClass, sourceCode, targetMethods, injectedMethods, distortionRatio, sourceInfo, targetInfo);
        generateBinaryTasks(generatedClass, sourceCode, targetMethods, injectedMethods, distortionRatio, sourceInfo, targetInfo);
        generateHybridTask(generatedClass, sourceCode, targetMethods, injectedMethods, distortionRatio, sourceInfo, targetInfo);
    }

    private CohesionDatasetGenerator.OriginalClassInfo candidateToInfo(CohesionDatasetGenerator.CandidateClass c) {
        CtClass<?> ctClass = c.ctClass();
        String className = ctClass.getQualifiedName();
        String filePath = ctClass.getPosition().getFile().getAbsolutePath();
        String content = ctClass.toString();
        return new CohesionDatasetGenerator.OriginalClassInfo(className, filePath, content);
    }

    private void generateRetrievalTask(CtClass<?> generatedClass, String sourceCode, Set<String> targetMethods, Set<String> injectedMethods, double distortionRatio, CohesionDatasetGenerator.OriginalClassInfo sourceInfo, CohesionDatasetGenerator.OriginalClassInfo targetInfo) {
        String prompt = String.format("%s The following Java class `%s` appears to handle multiple distinct responsibilities. Group all methods of this class into distinct sets based on the responsibility each set addresses. Respond with a JSON object where keys are arbitrary responsibility names (e.g., \"Responsibility1\") and values are lists of method names.", PROMPT_PREFIX,generatedClass.getSimpleName());

        Map<String, Set<String>> groundTruthMap = Map.of(
                "Responsibility1", targetMethods,
                "Responsibility2", injectedMethods
        );
        String groundTruthJson = gson.toJson(groundTruthMap);

        CohesionDatasetGenerator.DatasetEntry entry = new CohesionDatasetGenerator.DatasetEntry(generatedClass.getSimpleName(), sourceCode, prompt, groundTruthJson, "Retrieval", distortionRatio, sourceInfo, targetInfo);
        addEntry(entry);
    }

    private void generateBinaryTasks(CtClass<?> generatedClass, String sourceCode, Set<String> targetMethods, Set<String> injectedMethods, double distortionRatio, CohesionDatasetGenerator.OriginalClassInfo sourceInfo, CohesionDatasetGenerator.OriginalClassInfo targetInfo) {
        List<String> targetMethodList = new ArrayList<>(targetMethods);
        List<String> injectedMethodList = new ArrayList<>(injectedMethods);

        // Positive Example
        if (targetMethodList.size() >= 2) {
            String prompt = String.format("%s Given the Java class `%s`, are the methods `[%s, %s]` cohesive? Answer with only \"Yes\" or \"No\".", PROMPT_PREFIX, generatedClass.getSimpleName(), targetMethodList.get(0), targetMethodList.get(1));
            CohesionDatasetGenerator.DatasetEntry entry = new CohesionDatasetGenerator.DatasetEntry(generatedClass.getSimpleName(), sourceCode, prompt, "Yes", "Binary", distortionRatio, sourceInfo, targetInfo);
            addEntry(entry);
        }

        // Negative Example
        if (!targetMethodList.isEmpty() && !injectedMethodList.isEmpty()) {
            String prompt = String.format("%s Given the Java class `%s`, are the methods `[%s, %s]` cohesive? Answer with only \"Yes\" or \"No\".", PROMPT_PREFIX, generatedClass.getSimpleName(), targetMethodList.get(0), injectedMethodList.get(0));
            CohesionDatasetGenerator.DatasetEntry entry = new CohesionDatasetGenerator.DatasetEntry(generatedClass.getSimpleName(), sourceCode, prompt, "No", "Binary", distortionRatio, sourceInfo, targetInfo);
            addEntry(entry);
        }
    }

    private void generateHybridTask(CtClass<?> generatedClass, String sourceCode, Set<String> targetMethods, Set<String> injectedMethods, double distortionRatio, CohesionDatasetGenerator.OriginalClassInfo sourceInfo, CohesionDatasetGenerator.OriginalClassInfo targetInfo) {
        List<String> targetMethodList = new ArrayList<>(targetMethods);
        if (targetMethodList.isEmpty()) return;

        String seedMethod = targetMethodList.get(0);
        List<String> otherMethods = new ArrayList<>(targetMethodList);
        otherMethods.remove(seedMethod);

        String prompt = String.format("%s Consider the method `%s` in class `%s`. Identify all other methods in this class that belong to the same cohesive responsibility. Respond with a JSON object containing a single key `\"cohesiveMethods\"` with a list of the method names.", PROMPT_PREFIX, seedMethod, generatedClass.getSimpleName());
        CohesionDatasetGenerator.DatasetEntry entry = new CohesionDatasetGenerator.DatasetEntry(generatedClass.getSimpleName(), sourceCode, prompt, String.join(", ", otherMethods), "Hybrid", distortionRatio, sourceInfo, targetInfo);
        addEntry(entry);
    }

    private void addEntry(CohesionDatasetGenerator.DatasetEntry entry) {
        Map<Double, List<CohesionDatasetGenerator.DatasetEntry>> targetMap;
        switch (entry.taskType()) {
            case "Binary": targetMap = binaryEntries; break;
            case "Hybrid": targetMap = hybridEntries; break;
            case "Retrieval": targetMap = retrievalEntries; break;
            default: return;
        }
        targetMap.computeIfAbsent(entry.distortionRatio(), k -> new ArrayList<>()).add(entry);
    }
    public void writeAggregatedFiles() {
        writeMapToFile(binaryEntries, "binary.json");
        writeMapToFile(hybridEntries, "hybrid.json");
        writeMapToFile(retrievalEntries, "retrieval.json");
    }

    private void writeMapToFile(Map<Double, List<CohesionDatasetGenerator.DatasetEntry>> map, String fileName) {
        // Use a LinkedHashMap to preserve insertion order for keys if needed, and convert Double to String.
        Map<String, List<CohesionDatasetGenerator.DatasetEntry>> stringKeyMap = new LinkedHashMap<>();
        map.entrySet().stream()
                .sorted(Map.Entry.comparingByKey()) // Sort by distortion ratio
                .forEach(entry -> stringKeyMap.put(String.format("%.2f", entry.getKey()), entry.getValue()));

        try (FileWriter writer = new FileWriter(Paths.get(outputDir, fileName).toString())) {
            gson.toJson(stringKeyMap, writer);
        } catch (IOException e) {
            System.err.println("Failed to write JSON file: " + fileName);
            e.printStackTrace();
        }
    }
}
