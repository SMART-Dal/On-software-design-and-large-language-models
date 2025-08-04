package org.smart;

import spoon.reflect.declaration.CtClass;
import spoon.reflect.declaration.CtField;
import spoon.reflect.declaration.CtMethod;
import spoon.reflect.code.CtVariableAccess;
import spoon.reflect.declaration.CtVariable;
import spoon.reflect.factory.Factory;
import spoon.reflect.visitor.filter.TypeFilter;

import java.util.*;
import java.util.stream.Collectors;

/**
 * Handles injecting methods and their dependencies from a source class into a target class.
 */
class CohesionInjector {
    private final Factory factory;

    public CohesionInjector(Factory factory) {
        this.factory = factory;
    }

    public CohesionDatasetGenerator.InjectionResult inject(CtClass<?> target, CtClass<?> source, double distortionRatio) {
        Set<CtMethod<?>> targetMethods = CohesionAnalyzer.getDeclaredMethods(target);
        List<CtMethod<?>> sourceMethods = new ArrayList<>(CohesionAnalyzer.getDeclaredMethods(source));

        int numTargetMethods = targetMethods.size();
        if (numTargetMethods == 0) return null;

        // Calculate how many methods to inject to achieve the desired ratio
        int numToInject = (int) Math.round((distortionRatio * numTargetMethods) / (1.0 - distortionRatio));
        if (numToInject <= 0 || numToInject >= sourceMethods.size()) {
            return null; // Cannot achieve this ratio
        }

        // Select methods to inject
        Collections.shuffle(sourceMethods);
        List<CtMethod<?>> methodsToInject = sourceMethods.subList(0, numToInject);
        Set<String> injectedMethodNames = methodsToInject.stream().map(CtMethod::getSimpleName).collect(Collectors.toSet());

        // Dependency Analysis: find all fields required by the injected methods
        Set<CtField<?>> fieldsToInject = new HashSet<>();
        for (CtMethod<?> method : methodsToInject) {
            method.getElements(new TypeFilter<>(CtVariableAccess.class)).forEach(access -> {
                CtVariable<?> variable = access.getVariable().getDeclaration();
                if (variable instanceof CtField) {
                    fieldsToInject.add((CtField<?>) variable);
                }
            });
        }

        // Create the new class
        CtClass<?> generatedClass = target.clone();
        String randomId = UUID.randomUUID().toString().substring(0, 8).replace("-", "");
        generatedClass.setSimpleName("GeneratedClass" + randomId);

        // Add the injected methods and their required fields
        methodsToInject.forEach(m -> generatedClass.addMethod(m.clone()));
        fieldsToInject.forEach(f -> {
            if (generatedClass.getField(f.getSimpleName()) == null) {
                generatedClass.addField(f.clone());
            }
        });

        return new CohesionDatasetGenerator.InjectionResult(generatedClass, injectedMethodNames);
    }
}