package org.anon;

import org.anon.utils.SpoonUtils;
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
    private static final int METHODS_PER_SOURCE = 3; // Inject 3 methods from each source

    public CohesionInjector(Factory factory) {
        this.factory = factory;
    }

    public CohesionDatasetGenerator.InjectionResult inject(CtClass<?> target, List<CohesionDatasetGenerator.CandidateClass> sources) {
        Set<String> targetMethodSignatures = CohesionAnalyzer.getDeclaredMethods(target).stream()
                .map(SpoonUtils::getSimplifiedSignature)
                .collect(Collectors.toSet());

        CtClass<?> generatedClass = target.clone();
        String randomId = UUID.randomUUID().toString().substring(0, 8);
        generatedClass.setSimpleName("GeneratedClass" + randomId);

        Map<String, Set<String>> injectedResponsibilities = new HashMap<>();
        Set<String> allInjectedMethodSignatures = new HashSet<>();

        for (CohesionDatasetGenerator.CandidateClass sourceCandidate : sources) {
            CtClass<?> source = sourceCandidate.ctClass();
            Set<String> existingSignatures = new HashSet<>(targetMethodSignatures);
            existingSignatures.addAll(allInjectedMethodSignatures);

            List<CtMethod<?>> injectableMethods = CohesionAnalyzer.getDeclaredMethods(source).stream()
                    .filter(m -> !existingSignatures.contains(SpoonUtils.getSimplifiedSignature(m)))
                    .collect(Collectors.toList());

            if (injectableMethods.isEmpty()) continue;

            Collections.shuffle(injectableMethods);
            int numToInject = Math.min(METHODS_PER_SOURCE, injectableMethods.size());
            List<CtMethod<?>> methodsToInject = injectableMethods.subList(0, numToInject);

            Set<String> injectedSignaturesForThisSource = new HashSet<>();
            Set<CtField<?>> fieldsToInject = new HashSet<>();

            for (CtMethod<?> method : methodsToInject) {
                injectedSignaturesForThisSource.add(SpoonUtils.getSimplifiedSignature(method));
                method.getElements(new TypeFilter<>(CtVariableAccess.class)).forEach(access -> {
                    CtVariable<?> variable = access.getVariable().getDeclaration();
                    if (variable instanceof CtField) {
                        fieldsToInject.add((CtField<?>) variable);
                    }
                });
            }

            methodsToInject.forEach(m -> generatedClass.addMethod(m.clone()));
            fieldsToInject.forEach(f -> {
                if (generatedClass.getField(f.getSimpleName()) == null) {
                    generatedClass.addField(f.clone());
                }
            });

            allInjectedMethodSignatures.addAll(injectedSignaturesForThisSource);
            injectedResponsibilities.put(source.getQualifiedName(), injectedSignaturesForThisSource);
        }

        return new CohesionDatasetGenerator.InjectionResult(generatedClass, injectedResponsibilities);
    }
}