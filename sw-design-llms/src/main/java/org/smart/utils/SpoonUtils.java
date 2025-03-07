package org.smart.utils;

import spoon.reflect.cu.SourcePosition;
import spoon.reflect.declaration.*;
import spoon.reflect.reference.CtTypeReference;
import spoon.reflect.visitor.filter.TypeFilter;

import java.io.File;
import java.util.List;
import java.util.Set;

public class SpoonUtils {
    private static final Set<String> JAVA_STANDARD_PACKAGES = Set.of(
            "com.sun.",  "java.", "javafx.", "jdk.", "netscape.javascript", "org.ietf.jgss", "org.w3c", "org.xml."
    );


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
}
