package org.smart.utils;

import org.apache.commons.lang3.tuple.Pair;
import spoon.reflect.code.CtConstructorCall;
import spoon.reflect.cu.SourcePosition;
import spoon.reflect.declaration.*;
import spoon.reflect.reference.CtTypeReference;
import spoon.reflect.visitor.filter.TypeFilter;

import java.io.File;
import java.util.*;
import java.util.stream.Collectors;

public class SpoonUtils {
    private static final Set<String> JAVA_STANDARD_PACKAGES = Set.of(
            "com.sun.", "javax.",  "java.", "javafx.", "jdk.", "netscape.javascript", "org.ietf.jgss", "org.w3c", "org.xml."
    );

    /**
     * Creates a simplified method signature using simple type names.
     * This version correctly handles nested and inner classes.
     * Example: "visit(org.example.OuterClass$InnerClass)" becomes "visit(InnerClass)".
     *
     * @param method The Spoon CtMethod object.
     * @return A simplified signature string.
     */
    public static String getSimplifiedSignature(CtMethod<?> method) {
        String methodName = method.getSimpleName();
        String parameters = method.getParameters().stream()
                .map(param -> getUltimateSimpleName(param.getType())) // Use the new helper method
                .collect(Collectors.joining(","));
        return String.format("%s(%s)", methodName, parameters);
    }

    /**
     * Gets the most simplified name for a type, properly handling nested/inner classes.
     * It extracts the name after the last dot, then after the last dollar sign.
     *
     * @param typeReference The Spoon CtTypeReference object.
     * @return The ultimate simple name of the type.
     */
    private static String getUltimateSimpleName(CtTypeReference<?> typeReference) {
        if (typeReference == null) {
            return "";
        }
        String qualifiedName = typeReference.getQualifiedName();

        // 1. Split by dot and take the last part.
        // Using lastIndexOf is more efficient than split() for this task.
        int lastDotIndex = qualifiedName.lastIndexOf('.');
        String classNamePart = (lastDotIndex == -1) ? qualifiedName : qualifiedName.substring(lastDotIndex + 1);

        // 2. If that part contains a dollar sign, split by it and take the last part.
        int lastDollarIndex = classNamePart.lastIndexOf('$');
        String simpleName = (lastDollarIndex == -1) ? classNamePart : classNamePart.substring(lastDollarIndex + 1);

        return simpleName;
    }

    public static String getOutputRelativePath(CtType<?> type) {
        if (type == null) {
            return "UNKNOWN";
        }
        CtPackage pkg = type.getPackage();
        String packageName = (pkg != null) ? pkg.getQualifiedName() : "";
        String className = type.getSimpleName() + ".java";
        return packageName.isEmpty()
                ? className
                : packageName.replace('.', '/') + "/" + className;
    }

    public static boolean isJavaNativeType(CtTypeReference<?> typeRef) {
        String packageName = typeRef.getPackage() != null ? typeRef.getPackage().getQualifiedName() : "";
        // Check for primitive types or java.lang/java.util types commonly used as "native"
        boolean result = typeRef.isPrimitive()
                || JAVA_STANDARD_PACKAGES.stream().anyMatch(p -> packageName.startsWith(p))
                || typeRef.isArray();

        return result;
    }

    public static boolean isTestClass(CtClass<?> clazz, List<CtTypeReference<?>> testAnnotations) {
        // Ensure it's a class (not an interface or other type)
        if (clazz == null || !(clazz instanceof CtClass)) {
            return false;
        }

        // Find methods with test annotations
        List<CtMethod<?>> testMethods = clazz.getElements(new TypeFilter<CtMethod<?>>(CtMethod.class) {
            @Override
            public boolean matches(CtMethod<?> method) {
                return method.getAnnotations().stream()
                        .anyMatch(annotation -> testAnnotations.contains(annotation.getAnnotationType()));
            }
        });

        // Return true if at least one test method is found
        return !testMethods.isEmpty();
    }

    /**
     * (Alternative Implementation) Checks if a CtClass is a test class using a combination of heuristics.
     *
     * @param ctClass The class to check.
     * @return true if the class is likely a test class, false otherwise.
     */
    public static boolean isTestClass(CtClass<?> ctClass) {
        // Heuristic 1: Check file path (most reliable for Maven/Gradle projects)
        if (ctClass.getPosition() != null && ctClass.getPosition().getFile() != null) {
            // Normalize path separators for cross-platform compatibility
            String path = ctClass.getPosition().getFile().getAbsolutePath().replace('\\', '/');
            if (path.contains("/src/test/") || path.contains("/test/")) {
                return true;
            }
        }

        // Heuristic 2: Check class name conventions
        String className = ctClass.getSimpleName();
        if (className.endsWith("Test") || className.endsWith("Tests")) {
            return true;
        }

        // Heuristic 3: Check for common test annotations on methods
        for (CtMethod<?> method : (Set<CtMethod<?>>) ctClass.getMethods()) {
            for (CtAnnotation<?> annotation : method.getAnnotations()) {
                String annotationName = annotation.getAnnotationType().getQualifiedName();
                if ("org.junit.Test".equals(annotationName) || "org.junit.jupiter.api.Test".equals(annotationName)) {
                    return true;
                }
            }
        }

        return false;
    }

    public static List<CtTypeReference<?>> getDependencyChain(CtTypeReference<?> startType, CtTypeReference<?> targetType) {
        Queue<Pair<CtTypeReference<?>, List<CtTypeReference<?>>>> queue = new LinkedList<>();
        Set<CtTypeReference<?>> visited = new HashSet<>();

        List<CtTypeReference<?>> initialPath = new ArrayList<>();
        initialPath.add(startType);
        queue.add(Pair.of(startType, initialPath));

        while (!queue.isEmpty()) {
            Pair<CtTypeReference<?>, List<CtTypeReference<?>>> current = queue.poll();
            CtTypeReference<?> currentType = current.getLeft();
            List<CtTypeReference<?>> currentPath = current.getRight();

            if (visited.contains(currentType)) {
                continue;
            }
            visited.add(currentType);

            if (currentType.equals(targetType)) {
                Collections.reverse(currentPath);
                return currentPath;
            }

            CtType<?> currentTypeDecl = currentType.getTypeDeclaration();
            if (currentTypeDecl == null) {
                continue;
            }

            CtTypeReference<?> superClassRef = currentTypeDecl.getSuperclass();
            if (superClassRef != null && !isJavaNativeType(superClassRef)) {
                List<CtTypeReference<?>> newPath = new ArrayList<>(currentPath);
                newPath.add(superClassRef);
                queue.add(Pair.of(superClassRef, newPath));
            }

            for (CtTypeReference<?> interfaceRef : currentTypeDecl.getSuperInterfaces()) {
                if (!isJavaNativeType(interfaceRef)) {
                    List<CtTypeReference<?>> newPath = new ArrayList<>(currentPath);
                    newPath.add(interfaceRef);
                    queue.add(Pair.of(interfaceRef, newPath));
                }
            }
        }

        return Collections.emptyList();
    }
}
