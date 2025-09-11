package org.anon;

import spoon.MavenLauncher;
import spoon.reflect.CtModel;
import spoon.reflect.declaration.CtClass;
import spoon.reflect.declaration.CtElement;
import spoon.reflect.declaration.CtMethod;
import spoon.reflect.declaration.CtType;
import spoon.reflect.reference.CtTypeReference;
import spoon.reflect.visitor.filter.TypeFilter;

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.util.*;

import static org.anon.utils.SpoonUtils.isJavaNativeType;
import static org.anon.utils.SpoonUtils.isTestClass;

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
            if (!ctClass.isClass() || ctClass.isAbstract() || isTestClass(ctClass)) continue;

            String csvFqn = ctClass.getQualifiedName().replace('$', '.');
            if (!lcomData.containsKey(csvFqn)) continue;

            // Exclude classes with a mix of static and instance methods
            Set<CtMethod<?>> declaredMethods = CohesionAnalyzer.getDeclaredMethods(ctClass);
            boolean hasStatic = declaredMethods.stream().anyMatch(CtMethod::isStatic);
            boolean hasInstance = declaredMethods.stream().anyMatch(m -> !m.isStatic());
            if (hasStatic && hasInstance) {
                continue;
            }

            Integer lcom = lcomData.get(csvFqn);
            int numMethods = declaredMethods.size();

            if (lcom != null && lcom == 0 && numMethods > 2) {
                Map<CtElement, Set<CtElement>> adjList = cohesionAnalyzer.buildAdjacencyList(ctClass);
                List<Set<CtElement>> components = cohesionAnalyzer.findComponents(adjList);
                List<Set<String>> methodGroups = cohesionAnalyzer.getMethodGroups(components);

                if (methodGroups.size() == 1) {
                    candidates.add(new CohesionDatasetGenerator.CandidateClass(ctClass, methodGroups.get(0)));
                }
            }
        }
        return candidates;
    }

    public static Set<String> getInheritanceChain(CtClass<?> ctClass) {
        Set<String> chain = new HashSet<>();
        Queue<CtTypeReference<?>> queue = new LinkedList<>();
        if (ctClass.getSuperclass() != null) queue.add(ctClass.getSuperclass());
        queue.addAll(ctClass.getSuperInterfaces());

        while (!queue.isEmpty()) {
            CtTypeReference<?> currentTypeRef = queue.poll();
            if (currentTypeRef == null || chain.contains(currentTypeRef.getQualifiedName())) continue;
            String fqn = currentTypeRef.getQualifiedName();
            if (!isJavaNativeType(currentTypeRef)) {
                chain.add(fqn);
                CtType<?> currentTypeDecl = currentTypeRef.getDeclaration();
                if (currentTypeDecl != null) {
                    if (currentTypeDecl.getSuperclass() != null) queue.add(currentTypeDecl.getSuperclass());
                    queue.addAll(currentTypeDecl.getSuperInterfaces());
                }
            }
        }
        return chain;
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
