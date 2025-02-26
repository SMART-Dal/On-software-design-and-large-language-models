package org.smart.processors;

import spoon.processing.AbstractProcessor;
import spoon.reflect.code.*;
import spoon.reflect.declaration.*;
import spoon.reflect.factory.Factory;
import spoon.reflect.reference.CtTypeReference;

import java.util.*;
import java.util.stream.Collectors;

public class DirectInstantiationProcessor extends AbstractProcessor<CtElement> {
    // Store classes that were modified
    public static Map<String, String> modifiedClasses = new HashMap<>();
    // Java standard library packages to exclude
    private static final Set<String> JAVA_STANDARD_PACKAGES = Set.of(
            "com.sun.",  "java.", "javafx.", "jdk.", "netscape.javascript", "org.ietf.jgss", "org.w3c", "org.xml."
    );
    // Store DI constructors and setters to remove
    private Set<CtConstructor<?>> diConstructors = new HashSet<>();
    private Set<CtMethod<?>> diSetters = new HashSet<>();
    // Fields needing initializers and their concrete types
    private Map<CtField<?>, CtTypeReference<?>> fieldsToInitialize = new HashMap<>();
    // To avoid rechecking
    private Map<CtTypeReference<?>, List<CtType<?>>> implementationsCache = new HashMap<>();

    @Override
    public boolean isToBeProcessed(CtElement candidate) {
        // Process classes, constructor calls, and invocations
        return candidate instanceof CtClass<?>
                || candidate instanceof CtConstructorCall<?>
                || candidate instanceof CtInvocation<?>;
    }

    @Override
    public void process(CtElement element) {
        if (element instanceof CtClass<?>) {
            processClass((CtClass<?>) element);
        } else if (element instanceof CtConstructorCall<?>) {
            processConstructorCall((CtConstructorCall<?>) element);
        } else if (element instanceof CtInvocation<?>) {
            processInvocation((CtInvocation<?>) element);
        }
    }

    private void processClass(CtClass<?> ctClass) {
        // Boolean to keep track of modified classes
        boolean modified = false;
        // Identify DI constructors
        for (CtConstructor<?> ctor : ctClass.getConstructors()) {
            if (isDIConstructor(ctor)) {
                diConstructors.add(ctor);
                modified = true;
            }
        }

        // Identify DI setters
        for (CtMethod<?> method : ctClass.getMethods()) {
            if (isDISetter(method)) {
                diSetters.add(method);
                modified = true;
            }
        }

        // Collect fields set by DI
        Set<CtField<?>> diFields = new HashSet<>();
        for (CtConstructor<?> ctor : diConstructors) {
            diFields.addAll(getAssignedFields(ctor));
        }
        for (CtMethod<?> setter : diSetters) {
            CtField<?> field = getAssignedField(setter);
            if (field != null) {
                diFields.add(field);
            }
        }

        // Determine which fields need initializers
        for (CtField<?> field : diFields) {
            boolean initialized = false;
            for (CtConstructor<?> ctor : ctClass.getConstructors()) {
                if (!diConstructors.contains(ctor) && assignsToField(ctor, field)) {
                    initialized = true;
                    break;
                }
            }
            if (!initialized && field.getDefaultExpression() == null) {
                CtTypeReference<?> concreteType = returnRandomImplementation(field.getType());
                fieldsToInitialize.put(field, concreteType);
                modified = true;
            }
        }
        if (modified) {
            String className = ctClass.getQualifiedName();
            String filePath = ctClass.getPosition().getFile().getAbsolutePath();
            modifiedClasses.put(className, filePath);
        }
    }

    private void processConstructorCall(CtConstructorCall<?> call) {
        CtConstructor<?> calledCtor = (CtConstructor<?>) call.getExecutable().getDeclaration();
        if (calledCtor != null && diConstructors.contains(calledCtor)) {
            // Replace with no-arg constructor call
            CtConstructorCall<?> newCall = getFactory().createConstructorCall(call.getType());
            call.replace(newCall);
            // Store the calling class as a modified class
            CtClass<?> parentClass = call.getParent(CtClass.class);
            if (parentClass != null) {
                String className = parentClass.getQualifiedName();
                String filePath = parentClass.getPosition().getFile().getAbsolutePath(); // calledCtor.getPosition()... will also work, but just for consistency.
                modifiedClasses.put(className, filePath);
            }
        }
    }

    private void processInvocation(CtInvocation<?> invocation) {
        CtExecutable<?> executable = invocation.getExecutable().getDeclaration();
        if (executable instanceof CtMethod<?> calledMethod && diSetters.contains(calledMethod)) {
            // Remove the setter invocation
            invocation.delete();
            // Store the calling class as modified
            CtClass<?> parentClass = invocation.getParent(CtClass.class);
            if (parentClass != null) {
                String className = parentClass.getQualifiedName();
                String filePath = parentClass.getPosition().getFile().getAbsolutePath();
                modifiedClasses.put(className, filePath);
            }
        }
    }

    @Override
    public void processingDone() {
        // Remove DI constructors and setters
        for (CtConstructor<?> ctor : diConstructors) {
            ctor.delete();
        }
        for (CtMethod<?> setter : diSetters) {
            setter.delete();
        }

        // Add field initializers
        for (Map.Entry<CtField<?>, CtTypeReference<?>> entry : fieldsToInitialize.entrySet()) {
            CtField<?> field = entry.getKey();
            CtTypeReference<?> concreteType = entry.getValue();
            // Ensure the constructor call matches the field's type
            CtConstructorCall<?> newInstanceCall = getFactory().createConstructorCall(concreteType);
            // Since field is CtField<?>, we suppress unchecked warning or cast if needed
            field.setDefaultExpression((CtExpression) newInstanceCall); // Explicit cast
        }
    }

    // Helper Methods

    private boolean isDIConstructor(CtConstructor<?> ctor) {
        if (ctor.getParameters().isEmpty()) {
            return false;
        }
        // Check if all parameters are native types; if so, skip this constructor
        boolean allNative = ctor.getParameters().stream()
                .map(param -> param.getType())
                .allMatch(this::isJavaNativeType);
        if (allNative) {
            return false;
        }
        // Collect parameter names
        Set<String> paramNames = new HashSet<>();
        ctor.getParameters().forEach(p -> paramNames.add(p.getSimpleName()));
        // Track which parameters are assigned to fields
        Set<String> assignedParams = new HashSet<>();
        for (CtStatement stmt : ctor.getBody().getStatements()) {
            if (stmt instanceof CtAssignment) {
                CtAssignment<?, ?> assign = (CtAssignment<?, ?>) stmt;
                if (assign.getAssigned() instanceof CtFieldAccess
                        && ((CtFieldAccess<?>) assign.getAssigned()).getTarget() instanceof CtThisAccess) {
                    CtExpression<?> assignedExpr = assign.getAssignment();
                    if (assignedExpr instanceof CtVariableRead) {
                        String varName = assignedExpr.toString();
                        if (paramNames.contains(varName)) {
                            assignedParams.add(varName);
                        }
                    }
                }
            }
        }
        // Constructor is DI if all parameters are assigned to fields
        return assignedParams.size() == paramNames.size();
    }

    // Helper method to check if a type is a Java native type
    private boolean isJavaNativeType(CtTypeReference<?> typeRef) {
        String packageName = typeRef.getPackage() != null ? typeRef.getPackage().getQualifiedName() : "";
        // Check for primitive types or java.lang/java.util types commonly used as "native"
        boolean result = typeRef.isPrimitive()
                || JAVA_STANDARD_PACKAGES.stream().anyMatch(p -> packageName.startsWith(p));

        return result;
    }

    private boolean isDISetter(CtMethod<?> method) {
        if (!method.getSimpleName().startsWith("set") || method.getParameters().size() != 1) {
            return false;
        }
        CtBlock<?> body = method.getBody();
        if (body == null) {
            // Abstract method or interface
            return false;
        }
        List<CtStatement> statements = body.getStatements();
        if (statements.size() != 1 || !(statements.get(0) instanceof CtAssignment)) {
            return false;
        }
        CtAssignment<?, ?> assign = (CtAssignment<?, ?>) statements.get(0);
        if (!(assign.getAssigned() instanceof CtFieldAccess)
                || !(((CtFieldAccess<?>) assign.getAssigned()).getTarget() instanceof CtThisAccess)) {
            return false;
        }
        CtExpression<?> assignedExpr = assign.getAssignment();
        String paramName = method.getParameters().get(0).getSimpleName();
        return assignedExpr.toString().equals(paramName);
    }

    private Set<CtField<?>> getAssignedFields(CtConstructor<?> ctor) {
        Set<CtField<?>> fields = new HashSet<>();
        // Get assignment statements
        List<CtStatement> assignments =  ctor.getBody().getStatements().stream().filter(s -> s instanceof CtAssignment<?,?>).toList();
        for (CtStatement stmt : assignments) {
            CtAssignment<?, ?> assign = (CtAssignment<?, ?>) stmt;
            CtFieldAccess<?> fieldAccess = (CtFieldAccess<?>) assign.getAssigned();
            fields.add(fieldAccess.getVariable().getDeclaration());
        }
        return fields;
    }

    private CtField<?> getAssignedField(CtMethod<?> setter) {
        CtStatement stmt = setter.getBody().getStatement(0);
        CtAssignment<?, ?> assign = (CtAssignment<?, ?>) stmt;
        CtFieldAccess<?> fieldAccess = (CtFieldAccess<?>) assign.getAssigned();
        return fieldAccess.getVariable().getDeclaration();
    }

    private boolean assignsToField(CtConstructor<?> ctor, CtField<?> field) {
        for (CtStatement stmt : ctor.getBody().getStatements()) {
            if (stmt instanceof CtAssignment) {
                CtAssignment<?, ?> assign = (CtAssignment<?, ?>) stmt;
                if (assign.getAssigned() instanceof CtFieldAccess) {
                    CtFieldAccess<?> fa = (CtFieldAccess<?>) assign.getAssigned();
                    if (fa.getVariable().getDeclaration() == field) {
                        return true;
                    }
                }
            }
        }
        return false;
    }

    /**
     * Finds all implementations of a given interface
     */
    private List<CtType<?>> findImplementations(CtTypeReference<?> interfaceReference) {
        if (implementationsCache.containsKey(interfaceReference)) {
            return implementationsCache.get(interfaceReference);
        }
        List<CtType<?>> implementations = new ArrayList<>();
        Factory factory = interfaceReference.getFactory();
        // Iterate over all types in the project
        List<CtType<?>> allTypes = factory.Type().getAll();
        for (CtType<?> type: allTypes) {
            // Check if the type is a concrete class, i.e. not an interface nor an abstract class.
            if (type.isClass() && !type.isAbstract()) {
                // Check if it's an implementation of interfaceReference
                if (
                        type.getSuperInterfaces().stream()
                                .anyMatch(superInterface -> superInterface.equals(interfaceReference))
                ) {
                    implementations.add(type);
                }
            }
        }
        // Cache the result before returning
        implementationsCache.put(interfaceReference, implementations);
        return implementations;
    }

    /**
     * Randomly returns an implementation of an interface.
     */
    private CtTypeReference<?> returnRandomImplementation(CtTypeReference<?> interfaceReference) {
        List<CtType<?>> implementations = findImplementations(interfaceReference);
        if (!implementations.isEmpty()) {
            Random random = new Random();
            int index = random.nextInt(implementations.size());
            return implementations.get(index).getReference();
        }

        return null;
    }
}