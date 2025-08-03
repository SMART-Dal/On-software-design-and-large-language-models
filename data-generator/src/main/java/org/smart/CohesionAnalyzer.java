package org.smart;

import spoon.MavenLauncher;
import spoon.reflect.CtModel;
import spoon.reflect.declaration.CtClass;
import spoon.reflect.declaration.CtElement;
import spoon.reflect.declaration.CtField;
import spoon.reflect.declaration.CtMethod;
import spoon.reflect.declaration.CtVariable;
import spoon.reflect.visitor.filter.TypeFilter;
import spoon.reflect.code.CtVariableAccess;
import spoon.reflect.code.CtInvocation;


import java.io.BufferedReader;
import java.io.FileReader;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedList;
import java.util.List;
import java.util.Map;
import java.util.Queue;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * A utility class to analyze the structural cohesion of a Java class by
 * identifying its connected components.
 * A connected component is a group of methods and fields that are linked together,
 * directly or indirectly, through field accesses.
 *
 * Usage: java -cp "path/to/data-generator.jar" com.smart.CohesionAnalyzer /path/to/MavenProject /path/to/CSVFile
 */
public class CohesionAnalyzer {

    /**
     * Builds an adjacency list representation of a class's internal structure.
     * Nodes are methods and fields. An edge exists if a method accesses a field
     * OR if a method calls another method within the same class.
     *
     * @param ctClass The Spoon CtClass object to analyze.
     * @return A map representing the adjacency list of the graph.
     */
    public Map<CtElement, Set<CtElement>> buildAdjacencyList(CtClass<?> ctClass) {
        Map<CtElement, Set<CtElement>> adjList = new HashMap<>();
        // Get only methods declared in this class, not inherited ones.
        Set<CtMethod<?>> classMethods = ctClass.getMethods().stream()
                .filter(m -> m.getDeclaringType().getQualifiedName().equals(ctClass.getQualifiedName()))
                .collect(Collectors.toSet());

        // Initialize the map with all methods and fields as keys
        classMethods.forEach(method -> adjList.put(method, new HashSet<>()));
        ctClass.getFields().forEach(field -> adjList.put(field, new HashSet<>()));

        for (CtMethod<?> method : classMethods) {
            // 1. Connect methods to fields they access
            method.getElements(new TypeFilter<>(CtVariableAccess.class)).forEach(access -> {
                CtVariable<?> variable = access.getVariable().getDeclaration();
                if (variable instanceof CtField && adjList.containsKey(variable)) {
                    adjList.get(method).add(variable);
                    adjList.get(variable).add(method);
                }
            });

            // 2. Connect methods to other methods they call within the same class
            method.getElements(new TypeFilter<>(CtInvocation.class)).forEach(invocation -> {
                CtElement calledElement = invocation.getExecutable().getDeclaration();
                // Check if the called element is indeed a method we are tracking in our graph
                if (calledElement instanceof CtMethod<?> calledMethod && adjList.containsKey(calledMethod)) {
                    adjList.get(method).add(calledMethod);
                    adjList.get(calledMethod).add(method);
                }
            });
        }
        return adjList;
    }

    /**
     * Finds all connected components in the graph represented by the adjacency list.
     * Uses a Breadth-First Search (BFS) traversal.
     *
     * @param adjList The adjacency list of the class graph.
     * @return A list of sets, where each set represents a connected component.
     */
    public List<Set<CtElement>> findComponents(Map<CtElement, Set<CtElement>> adjList) {
        List<Set<CtElement>> components = new ArrayList<>();
        Set<CtElement> visited = new HashSet<>();

        // Iterate over all nodes (methods and fields) in the graph
        for (CtElement node : adjList.keySet()) {
            if (!visited.contains(node)) {
                // If a node hasn't been visited, it's the start of a new component
                Set<CtElement> currentComponent = new HashSet<>();
                Queue<CtElement> queue = new LinkedList<>();

                queue.add(node);
                visited.add(node);

                // Start BFS from the current node
                while (!queue.isEmpty()) {
                    CtElement currentNode = queue.poll();
                    currentComponent.add(currentNode);

                    // Add all unvisited neighbors to the queue
                    for (CtElement neighbor : adjList.get(currentNode)) {
                        if (!visited.contains(neighbor)) {
                            visited.add(neighbor);
                            queue.add(neighbor);
                        }
                    }
                }
                components.add(currentComponent);
            }
        }
        return components;
    }

    /**
     * Filters the found components to extract only the method groups.
     *
     * @param components A list of components containing both methods and fields.
     * @return A list of sets, where each set contains only the methods of a component.
     */
    public List<Set<String>> getMethodGroups(List<Set<CtElement>> components) {
        List<Set<String>> methodGroups = new ArrayList<>();
        for (Set<CtElement> component : components) {
            Set<String> methods = component.stream()
                    .filter(CtMethod.class::isInstance)
                    .map(el -> ((CtMethod<?>) el).getSimpleName()) // Get method names
                    .collect(Collectors.toSet());

            // Only add non-empty method groups to the result
            if (!methods.isEmpty()) {
                methodGroups.add(methods);
            }
        }
        return methodGroups;
    }

    /**
     * Loads LCOM data from the provided CSV file.
     *
     * @param csvPath The path to the CSV file.
     * @return A map where the key is the fully qualified class name and the value is the LCOM score.
     */
    private static Map<String, Float> loadLcomData(String csvPath) {
        Map<String, Float> lcomMap = new HashMap<>();
        String line;
        try (BufferedReader br = new BufferedReader(new FileReader(csvPath))) {
            // Read header to find column indices
            String headerLine = br.readLine();
            if (headerLine == null) return lcomMap;
            String[] headers = headerLine.split(",");
            int pkgIndex = -1, typeIndex = -1, lcomIndex = -1;
            for (int i = 0; i < headers.length; i++) {
                if ("Package Name".equalsIgnoreCase(headers[i])) pkgIndex = i;
                if ("Type Name".equalsIgnoreCase(headers[i])) typeIndex = i;
                if ("LCOM".equalsIgnoreCase(headers[i])) lcomIndex = i;
            }

            if (pkgIndex == -1 || typeIndex == -1 || lcomIndex == -1) {
                System.err.println("CSV file must contain 'Package Name', 'Type Name', and 'LCOM' columns.");
                return lcomMap;
            }

            while ((line = br.readLine()) != null) {
                String[] values = line.split(",");
                String packageName = values[pkgIndex];
                String typeName = values[typeIndex];
                String fqn = packageName + "." + typeName;
                try {
                    float lcom = Float.parseFloat(values[lcomIndex]);
                    lcomMap.put(fqn, lcom);
                } catch (NumberFormatException e) {
                    // Ignore lines where LCOM is not a valid number
                    System.err.println("Invalid lcom index: " + values[lcomIndex]);
                }
            }
        } catch (IOException e) {
            System.err.println("Error reading CSV file: " + e.getMessage());
        }
        return lcomMap;
    }
}
