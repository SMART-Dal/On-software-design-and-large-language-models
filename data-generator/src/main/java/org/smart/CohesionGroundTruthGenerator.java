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
    private final Map<Integer, List<CohesionDatasetGenerator.DatasetEntry>> binaryEntries = new HashMap<>();
    private final Map<Integer, List<CohesionDatasetGenerator.DatasetEntry>> hybridEntries = new HashMap<>();
    private final Map<Integer, List<CohesionDatasetGenerator.DatasetEntry>> retrievalEntries = new HashMap<>();
    private int entryCounter = 0;
    private final static String PROMPT_PREFIX = "You are an expert software engineer that understands code quality. A cohesive class is one with a single, well-defined responsibility, where all its methods and properties are united in serving a common purpose. A class with low cohesion handles multiple, unrelated responsibilities.\\n\\nNote: For this task, class constructors should not be considered part of a class's responsibilities. When providing method names, provide the method's signature, e.g., calculateAnswer(double, int, double, double). Do NOT include its return type. If the type is a parameterized generic type, e.g. List<Foo>, only provide the generic type, i.e. List. For Varargs, the type should be formatted as `Type[]`. For example, you should return the method `foo(Type... a)` as `foo(Type[])`.\n\n";

    public CohesionGroundTruthGenerator(String outputDir) {
        this.outputDir = outputDir;
    }

    public void generateAndAccumulate(CohesionDatasetGenerator.InjectionResult result, CohesionDatasetGenerator.CandidateClass target, List<CohesionDatasetGenerator.CandidateClass> sources, int distortionLevel) {
        CtClass<?> generatedClass = result.generatedClass();
        String sourceCode = generatedClass.toString();

        CohesionDatasetGenerator.OriginalClassInfo targetInfo = candidateToInfo(target);
        List<CohesionDatasetGenerator.OriginalClassInfo> sourceInfo = sources.stream().map(this::candidateToInfo).toList();

        Set<String> targetMethods = target.methods();
        Map<String, Set<String>> injectedResponsibilities = result.injectedResponsibilities();

        generateRetrievalTask(generatedClass, sourceCode, targetMethods, injectedResponsibilities, distortionLevel, targetInfo, sourceInfo);
        generateBinaryTasks(generatedClass, sourceCode, targetMethods, injectedResponsibilities, distortionLevel, targetInfo, sourceInfo);
        generateHybridTask(generatedClass, sourceCode, targetMethods, distortionLevel, targetInfo, sourceInfo);
    }

    private CohesionDatasetGenerator.OriginalClassInfo candidateToInfo(CohesionDatasetGenerator.CandidateClass c) {
        CtClass<?> ctClass = c.ctClass();
        String className = ctClass.getQualifiedName();
        String filePath = ctClass.getPosition().getFile().getAbsolutePath();
        String content = ctClass.toString();
        return new CohesionDatasetGenerator.OriginalClassInfo(className, filePath, content);
    }

    private void generateRetrievalTask(CtClass<?> generatedClass, String sourceCode, Set<String> targetMethods, Map<String, Set<String>> injectedResponsibilities, int distortionLevel, CohesionDatasetGenerator.OriginalClassInfo targetInfo, List<CohesionDatasetGenerator.OriginalClassInfo> sourceInfo) {
        String prompt = String.format("%s The following Java class `%s` appears to handle multiple distinct responsibilities. Group all methods of this class into distinct sets based on the responsibility each set addresses. Respond with a JSON object where keys are arbitrary responsibility names (e.g., \"Responsibility1\") and values are lists of method signatures.", PROMPT_PREFIX,generatedClass.getSimpleName());
        Map<String, Set<String>> groundTruthMap = new HashMap<>();
        groundTruthMap.put("Responsibility_Target", targetMethods);
        int i = 1;
        for (Set<String> injectedMethods : injectedResponsibilities.values()) {
            groundTruthMap.put("Responsibility_Injected" + i++, injectedMethods);
        }
        String groundTruthJson = gson.toJson(groundTruthMap);

        CohesionDatasetGenerator.DatasetEntry entry = new CohesionDatasetGenerator.DatasetEntry(generatedClass.getSimpleName(), sourceCode, prompt, groundTruthJson, "Retrieval", distortionLevel, targetInfo, sourceInfo);
        addEntry(entry);
    }

    private void generateBinaryTasks(CtClass<?> generatedClass, String sourceCode, Set<String> targetMethods, Map<String, Set<String>> injectedResponsibilities, int distortionLevel, CohesionDatasetGenerator.OriginalClassInfo targetInfo, List<CohesionDatasetGenerator.OriginalClassInfo> sourceInfo) {
        List<String> targetMethodList = new ArrayList<>(targetMethods);
        if (targetMethodList.size() >= 2) {
            String prompt = PROMPT_PREFIX + String.format("Given the Java class `%s`, are the methods `[%s, %s]` cohesive? Answer with only \"Yes\" or \"No\".", generatedClass.getSimpleName(), targetMethodList.get(0), targetMethodList.get(1));
            CohesionDatasetGenerator.DatasetEntry entry = new CohesionDatasetGenerator.DatasetEntry(generatedClass.getSimpleName(), sourceCode, prompt, "Yes", "Binary", distortionLevel, targetInfo, sourceInfo);
            addEntry(entry);
        }

        if (!targetMethodList.isEmpty() && !injectedResponsibilities.isEmpty()) {
            List<String> injectedMethodList = new ArrayList<>(injectedResponsibilities.values().iterator().next());
            if (!injectedMethodList.isEmpty()) {
                String prompt = PROMPT_PREFIX + String.format("Given the Java class `%s`, are the methods `[%s, %s]` cohesive? Answer with only \"Yes\" or \"No\".", generatedClass.getSimpleName(), targetMethodList.get(0), injectedMethodList.get(0));
                CohesionDatasetGenerator.DatasetEntry entry = new CohesionDatasetGenerator.DatasetEntry(generatedClass.getSimpleName(), sourceCode, prompt, "No", "Binary", distortionLevel, targetInfo, sourceInfo);
                addEntry(entry);
            }
        }
    }

    private void generateHybridTask(CtClass<?> generatedClass, String sourceCode, Set<String> targetMethods, int distortionLevel, CohesionDatasetGenerator.OriginalClassInfo targetInfo, List<CohesionDatasetGenerator.OriginalClassInfo> sourceInfo) {
        List<String> targetMethodList = new ArrayList<>(targetMethods);
        if (targetMethodList.isEmpty()) return;

        String seedMethod = targetMethodList.get(0);
        List<String> otherMethods = new ArrayList<>(targetMethodList);
        otherMethods.remove(seedMethod);

        String prompt = String.format("%s Consider the method `%s` in class `%s`. Identify all other methods in this class that belong to the same cohesive responsibility. Respond with a JSON object containing a single key `\"cohesiveMethods\"` with a list of the method signatures.", PROMPT_PREFIX, seedMethod, generatedClass.getSimpleName());

        Map<String, List<String>> groundTruthMap = Map.of("cohesiveMethods", otherMethods);
        String groundTruthJson = gson.toJson(groundTruthMap);

        CohesionDatasetGenerator.DatasetEntry entry = new CohesionDatasetGenerator.DatasetEntry(generatedClass.getSimpleName(), sourceCode, prompt, groundTruthJson, "Hybrid", distortionLevel, targetInfo, sourceInfo);
        addEntry(entry);
    }

    private void addEntry(CohesionDatasetGenerator.DatasetEntry entry) {
        Map<Integer, List<CohesionDatasetGenerator.DatasetEntry>> targetMap;
        switch (entry.taskType()) {
            case "Binary": targetMap = binaryEntries; break;
            case "Hybrid": targetMap = hybridEntries; break;
            case "Retrieval": targetMap = retrievalEntries; break;
            default: return;
        }
        targetMap.computeIfAbsent(entry.distortionLevel(), k -> new ArrayList<>()).add(entry);
    }
    public void writeAggregatedFiles() {
        writeMapToFile(binaryEntries, "binary.json");
        writeMapToFile(hybridEntries, "hybrid.json");
        writeMapToFile(retrievalEntries, "retrieval.json");
    }

    private void writeMapToFile(Map<Integer, List<CohesionDatasetGenerator.DatasetEntry>> map, String fileName) {
        Map<String, List<CohesionDatasetGenerator.DatasetEntry>> stringKeyMap = new LinkedHashMap<>();
        map.entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                .forEach(entry -> stringKeyMap.put(String.valueOf(entry.getKey()), entry.getValue()));

        try (FileWriter writer = new FileWriter(Paths.get(outputDir, fileName).toString())) {
            gson.toJson(stringKeyMap, writer);
        } catch (IOException e) {
            System.err.println("Failed to write JSON file: " + fileName);
            e.printStackTrace();
        }
    }
}
