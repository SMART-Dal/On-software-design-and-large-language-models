package org.anon.utils;

import org.apache.commons.lang3.tuple.Pair;
import spoon.MavenLauncher;
import spoon.reflect.CtModel;
import spoon.reflect.declaration.CtClass;
import spoon.reflect.declaration.CtPackage;
import spoon.reflect.reference.CtTypeReference;
import spoon.reflect.visitor.filter.TypeFilter;

import java.util.*;
import java.util.stream.Collectors;


public class DisjointClusterAnalyzer {
    // Add limit to save time. On average we only need 100s of perturbed classes.
    // Exhausting all possible disjoint pairs can be very slow, especially on large code bases.
    private static int MAX_NUMBER_OF_PAIRS = 1000;


    // Compute transitive dependencies using DFS
    private static Set<String> getTransitiveDependencies(String className, Map<String, Set<String>> dependencyGraph) {
        Set<String> transitiveDeps = new HashSet<>();
        Stack<String> stack = new Stack<>();
        Set<String> visited = new HashSet<>();

        stack.push(className);
        while (!stack.isEmpty()) {
            String current = stack.pop();
            if (visited.add(current)) {
                Set<String> directDeps = dependencyGraph.getOrDefault(current, Collections.emptySet());
                for (String dep : directDeps) {
                    if (!visited.contains(dep)) {
                        stack.push(dep);
                    }
                }
                if (!current.equals(className)) { // Exclude the class itself from its own dependency set
                    transitiveDeps.add(current);
                }
            }
        }
        return transitiveDeps;
    }

    public static List<Pair<ClassInformation, ClassInformation>> analyze(MavenLauncher launcher) {

        launcher.buildModel();
        CtModel model = launcher.getModel();
        // Define test annotations to filter out test classes
        List<CtTypeReference<?>> testAnnotations = Arrays.asList(
                launcher.getFactory().Type().createReference("org.junit.Test"),
                launcher.getFactory().Type().createReference("org.junit.jupiter.api.Test"),
                launcher.getFactory().Type().createReference("org.testng.annotations.Test")
        );

        // Get all classes and filter out native/test classes
        List<CtClass<?>> allClasses = model.getRootPackage().getElements(new TypeFilter<>(CtClass.class));
        List<CtClass<?>> projectClasses = allClasses.stream()
                .filter(cls -> !SpoonUtils.isJavaNativeType(cls.getReference()) && !SpoonUtils.isTestClass(cls, testAnnotations))
                .collect(Collectors.toList());

        // Step 2: Build the dependency graph
        Map<String, Set<String>> dependencyGraph = new HashMap<>();
        for (CtClass<?> cls : projectClasses) {
            String className = cls.getQualifiedName();
            Set<String> directDeps = cls.getReferencedTypes().stream()
                    .filter(ref -> ref.getTypeDeclaration() instanceof CtClass)
                    .map(CtTypeReference::getQualifiedName)
                    .filter(depName -> !SpoonUtils.isJavaNativeType(launcher.getFactory().Type().createReference(depName)))
                    .filter(depName -> projectClasses.stream().anyMatch(c -> c.getQualifiedName().equals(depName)))
                    .collect(Collectors.toSet());
            dependencyGraph.put(className, directDeps);
        }

        // Step 3: Compute transitive dependency sets for all classes
        Map<String, Set<String>> transitiveDeps = new HashMap<>();
        for (CtClass<?> cls : projectClasses) {
            String className = cls.getQualifiedName();
            transitiveDeps.put(className, getTransitiveDependencies(className, dependencyGraph));
        }

        // Step 4: Identify and store disjoint pairs
        List<Pair<ClassInformation, ClassInformation>> disjointPairs = new ArrayList<>();
        for (int i = 0; i < projectClasses.size(); i++) {
            CtClass<?> classA = projectClasses.get(i);
            String nameA = classA.getQualifiedName();
            Set<String> depsA = transitiveDeps.get(nameA);

            for (int j = i + 1; j < projectClasses.size(); j++) {
                CtClass<?> classB = projectClasses.get(j);
                String nameB = classB.getQualifiedName();
                Set<String> depsB = transitiveDeps.get(nameB);

                // Check if dependency sets intersect
                Set<String> intersection = new HashSet<>(depsA);
                intersection.retainAll(depsB);

                if (intersection.isEmpty()) {
                    CtPackage packageA = classA.getPackage();
                    CtPackage packageB = classB.getPackage();
                    if (packageA == null || packageB == null) {
                        continue;
                    }

                    ClassInformation classInformationA = new ClassInformation(nameA, classA.getPackage().getQualifiedName(), SpoonUtils.getOutputRelativePath(classA));
                    ClassInformation classInformationB = new ClassInformation(nameB, classB.getPackage().getQualifiedName(), SpoonUtils.getOutputRelativePath(classB));
                    Pair<ClassInformation, ClassInformation> pair = Pair.of(classInformationA, classInformationB);
                    disjointPairs.add(pair);
                    if (disjointPairs.size() >= MAX_NUMBER_OF_PAIRS) {
                        return disjointPairs;
                    }


                }
            }
        }
        return disjointPairs;
    }


}