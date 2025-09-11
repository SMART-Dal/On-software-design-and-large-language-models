package org.anon;

import spoon.reflect.declaration.CtClass;
import spoon.reflect.declaration.CtElement;
import spoon.reflect.declaration.CtField;
import spoon.reflect.declaration.CtMethod;
import spoon.reflect.declaration.CtVariable;
import spoon.reflect.visitor.filter.TypeFilter;
import spoon.reflect.code.CtVariableAccess;
import spoon.reflect.code.CtInvocation;



import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedList;
import java.util.List;
import java.util.Map;
import java.util.Queue;
import java.util.Set;
import java.util.stream.Collectors;

import static org.anon.utils.SpoonUtils.getSimplifiedSignature;

/**
 * A utility class to analyze the structural cohesion of a Java class.
 */
class CohesionAnalyzer {
    public Map<CtElement, Set<CtElement>> buildAdjacencyList(CtClass<?> ctClass) {
        Map<CtElement, Set<CtElement>> adjList = new HashMap<>();
        Set<CtMethod<?>> classMethods = getDeclaredMethods(ctClass);

        classMethods.forEach(method -> adjList.put(method, new HashSet<>()));
        ctClass.getFields().forEach(field -> adjList.put(field, new HashSet<>()));

        for (CtMethod<?> method : classMethods) {
            method.getElements(new TypeFilter<>(CtVariableAccess.class)).forEach(access -> {
                CtVariable<?> variable = access.getVariable().getDeclaration();
                if (variable instanceof CtField && adjList.containsKey(variable)) {
                    adjList.get(method).add(variable);
                    adjList.get(variable).add(method);
                }
            });
            method.getElements(new TypeFilter<>(CtInvocation.class)).forEach(invocation -> {
                CtElement calledElement = invocation.getExecutable().getDeclaration();
                if (calledElement instanceof CtMethod<?> calledMethod && adjList.containsKey(calledMethod)) {
                    adjList.get(method).add(calledMethod);
                    adjList.get(calledMethod).add(method);
                }
            });
        }
        return adjList;
    }

    public List<Set<CtElement>> findComponents(Map<CtElement, Set<CtElement>> adjList) {
        List<Set<CtElement>> components = new ArrayList<>();
        Set<CtElement> visited = new HashSet<>();
        for (CtElement node : adjList.keySet()) {
            if (!visited.contains(node)) {
                Set<CtElement> currentComponent = new HashSet<>();
                Queue<CtElement> queue = new LinkedList<>();
                queue.add(node);
                visited.add(node);
                while (!queue.isEmpty()) {
                    CtElement currentNode = queue.poll();
                    currentComponent.add(currentNode);
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

    public List<Set<String>> getMethodGroups(List<Set<CtElement>> components) {
        return components.stream()
                .map(component -> component.stream()
                        .filter(CtMethod.class::isInstance)
                        .map(el -> getSimplifiedSignature((CtMethod<?>) el))  // Use full signature
                        .collect(Collectors.toSet()))
                .filter(methodSet -> !methodSet.isEmpty())
                .collect(Collectors.toList());
    }

    public static Set<CtMethod<?>> getDeclaredMethods(CtClass<?> ctClass) {
        return ctClass.getMethods().stream()
                .filter(m -> m.getDeclaringType().getQualifiedName().equals(ctClass.getQualifiedName()) && !m.isAbstract() )
                .collect(Collectors.toSet());
    }
}
