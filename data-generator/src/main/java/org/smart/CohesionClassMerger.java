package org.smart;

import spoon.reflect.declaration.CtClass;
import spoon.reflect.declaration.CtMethod;
import spoon.reflect.factory.Factory;

import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

public class CohesionClassMerger {
    private final Factory factory;

    public CohesionClassMerger(Factory factory) {
        this.factory = factory;
    }

    public CtClass<?> mergeClasses(List<CohesionDatasetGenerator.CandidateClass> candidates) {
        // Generate a neutral, non-descriptive name using a random component to avoid hinting to the LLM.
        String randomId = UUID.randomUUID().toString().substring(0, 8).replace("-", "");
        String newClassName = "Class" + randomId;

        CtClass<?> mergedClass = factory.createClass(newClassName);

        for (CohesionDatasetGenerator.CandidateClass candidate : candidates) {
            CtClass<?> sourceClass = candidate.ctClass();
            for (var field : sourceClass.getFields()) {
                mergedClass.addField(field.clone());
            }

            Set<CtMethod<?>> declaredMethods = sourceClass.getMethods().stream()
                    .filter(m -> m.getDeclaringType().getQualifiedName().equals(sourceClass.getQualifiedName()))
                    .collect(Collectors.toSet());
            for (var method : declaredMethods) {
                mergedClass.addMethod(method.clone());
            }
        }
        return mergedClass;
    }
}
