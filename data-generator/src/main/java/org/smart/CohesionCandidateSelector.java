package org.smart;

import spoon.MavenLauncher;
import spoon.reflect.CtModel;
import spoon.reflect.declaration.CtClass;
import spoon.reflect.declaration.CtElement;
import spoon.reflect.declaration.CtMethod;
import spoon.reflect.visitor.filter.TypeFilter;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.HashMap;
import java.util.Set;
import java.util.stream.Collectors;

import static org.smart.utils.SpoonUtils.isTestClass;

public class CohesionCandidateSelector {
    private final CohesionAnalyzer cohesionAnalyzer = new CohesionAnalyzer();

    public List<CohesionDatasetGenerator.CandidateClass> selectCandidates(String projectPath, String csvPath) {
        Map<String, Integer> lcomData = loadLcomData(csvPath);
        MavenLauncher launcher = new MavenLauncher(projectPath, MavenLauncher.SOURCE_TYPE.APP_SOURCE);
        launcher.getEnvironment().setAutoImports(true);
        launcher.getEnvironment().setCommentEnabled(true);
        launcher.getEnvironment().setNoClasspath(true);
        launcher.getEnvironment().setIgnoreDuplicateDeclarations(true);
        CtModel model = launcher.buildModel();

        List<CtClass<?>> classes = model.getElements(new TypeFilter<>(CtClass.class));

        List<CohesionDatasetGenerator.CandidateClass> candidates = new ArrayList<>();

        for (CtClass<?> ctClass : classes) {
            if (!ctClass.isClass() || isTestClass(ctClass)) {
                continue;
            }

            String csvFqn = ctClass.getQualifiedName().replace('$', '.');
            if (!lcomData.containsKey(csvFqn)) continue;

            Integer lcom = lcomData.get(csvFqn);

            Set<CtMethod<?>> declaredMethods = ctClass.getMethods().stream()
                    .filter(m -> m.getDeclaringType().getQualifiedName().equals(ctClass.getQualifiedName()))
                    .collect(Collectors.toSet());
            int numMethods = declaredMethods.size();

            if (lcom != null && lcom == 0 && numMethods > 2) {
                Map<CtElement, Set<CtElement>> adjList = cohesionAnalyzer.buildAdjacencyList(ctClass);
                List<Set<CtElement>> components = cohesionAnalyzer.findComponents(adjList);
                List<Set<String>> methodGroups = cohesionAnalyzer.getMethodGroups(components);

                // The crucial filter: only accept classes with exactly ONE component
                if (methodGroups.size() == 1) {
                    candidates.add(new CohesionDatasetGenerator.CandidateClass(ctClass, methodGroups.get(0)));
                }
            }
        }
        return candidates;
    }

    private Map<String, Integer> loadLcomData(String csvPath) {
        Map<String, Integer> lcomMap = new HashMap<>();
        try (BufferedReader br = new BufferedReader(new FileReader(csvPath))) {
            br.readLine(); // Skip header
            String line;
            while ((line = br.readLine()) != null) {
                String[] values = line.split(",");
                if (values.length > 12) {
                    String fqn = values[1] + "." + values[2];
                    try {
                        int lcom = Integer.parseInt(values[12]);
                        lcomMap.put(fqn, lcom);
                    } catch (NumberFormatException ignored) {}
                }
            }
        } catch (IOException e) {
            System.err.println("Error reading CSV file: " + e.getMessage());
        }
        return lcomMap;
    }
}
