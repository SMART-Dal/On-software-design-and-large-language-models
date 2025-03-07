package org.smart.processors;

import org.smart.utils.ClassDependency;
import org.smart.utils.SpoonUtils;
import spoon.processing.AbstractProcessor;
import spoon.reflect.code.*;
import spoon.reflect.cu.SourcePosition;
import spoon.reflect.declaration.*;
import spoon.reflect.factory.Factory;
import spoon.reflect.reference.CtTypeReference;
import spoon.reflect.visitor.filter.AbstractFilter;

import java.io.File;
import java.util.*;
import java.util.stream.Collectors;

public class DirectInstantiationProcessor extends AbstractProcessor<CtElement> {
    // Store classes that were modified
    public static Map<String, String> modifiedCallers = new HashMap<>();
    public static Map<String, String> modifiedCallees = new HashMap<>();
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
    public static Map<CtTypeReference<?>, List<CtClass<?>>> implementationsCache = new HashMap<>();
    public static Map<String,ClassDependency> classDependencies = new HashMap<>();

    @Override
    public boolean isToBeProcessed(CtElement candidate) {
        // Process classes, constructor calls, and invocations
        boolean validTypes = candidate instanceof CtClass<?>
                || candidate instanceof CtConstructorCall<?>
                || candidate instanceof CtInvocation<?>;
        // Check that they are not test class
        SourcePosition pos = candidate.getPosition();
        boolean notTest = true;
        if (pos != null && pos.getFile() != null) {
            String filePath = pos.getFile().getAbsolutePath();
            notTest = !filePath.contains("src" + File.separator + "test" + File.separator + "java");
        }
        return validTypes && notTest;
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
        // Identify DI constructors
        for (CtConstructor<?> ctor : ctClass.getConstructors()) {
            if (isDIConstructor(ctor)) {
                diConstructors.add(ctor);
            }
        }

        // Identify DI setters
        for (CtMethod<?> method : ctClass.getMethods()) {
            if (isDISetter(method)) {
                diSetters.add(method);
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
            }
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
                modifiedCallers.put(className, filePath);
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
                modifiedCallers.put(className, filePath);
            }
        }
    }

    @Override
    public void processingDone() {
        // Remove DI constructors and setters.
        // Add a no-arg constructor to the class if it does not have one.
        for (CtConstructor<?> ctor : diConstructors) {
            CtClass<?> parentClass = ctor.getParent(CtClass.class);
            if (parentClass != null) {
                boolean hasNoArg = parentClass.getConstructors().stream()
                        .anyMatch(ctr -> ctr.getParameters().isEmpty());
                if (!hasNoArg) {
                    CtConstructor noArgCtor = getFactory().Core().createConstructor();
                    noArgCtor.addModifier(ModifierKind.PUBLIC);
                    noArgCtor.setBody(getFactory().Code().createCtBlock(null));
                    parentClass.addConstructor(noArgCtor);
                }
                // Add this class to the list modified callees.
                String className = parentClass.getQualifiedName();
                String filePath = parentClass.getPosition().getFile().getAbsolutePath();
                modifiedCallees.put(className, filePath);
            }
            ctor.delete();

        }
        for (CtMethod<?> setter : diSetters) {
            setter.delete();
        }

        // Add field initializers
        for (Map.Entry<CtField<?>, CtTypeReference<?>> entry : fieldsToInitialize.entrySet()) {
            CtField<?> field = entry.getKey();
            CtTypeReference<?> concreteType = entry.getValue();
            if (concreteType != null) {
                // Ensure the constructor call matches the field's type
                CtConstructorCall newInstanceCall = getFactory().Code().createConstructorCall(concreteType);
                // Since field is CtField<?>, we suppress unchecked warning or cast if needed
                field.setDefaultExpression(newInstanceCall);
                // Track the class and its dependencies
                // Get the fields type
                CtType<?> declaringType = field.getDeclaringType();
                String className = declaringType.getQualifiedName();
                String classFilePath = SpoonUtils.getOutputRelativePath(declaringType);

                // Get the dependency detail
                CtType<?> dependencyType = concreteType.getTypeDeclaration();
                String dependencyClassName = SpoonUtils.isJavaNativeType(concreteType) ? "EXTERNAL":SpoonUtils.getOutputRelativePath(dependencyType);

                String dependencyFilePath = SpoonUtils.getOutputRelativePath(dependencyType);
                // Record the dependency relation
                ClassDependency dependencyInfo = classDependencies.computeIfAbsent(
                        className,
                        k -> new ClassDependency(classFilePath)
                );
                dependencyInfo.addDependency(dependencyClassName, dependencyFilePath);
            }
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
                .allMatch(SpoonUtils::isJavaNativeType);
        if (allNative) {
            return false;
        }
        // Check if all parameters are interfaces or abstracts
        boolean allInterfacesOrAbstract = ctor.getParameters().stream()
                .map(ctParameter -> ctParameter.getType())
                .allMatch(this::isInterfaceOrAbstract);
        if (!allInterfacesOrAbstract) {
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

    // Helper method to check if all types of the parameters of a method are not concrete classes
    private boolean isInterfaceOrAbstract(CtTypeReference<?> typeRef) {
        // Resolve type declaration (needs proper classpath setup)
        CtType<?> typeDecl = typeRef.getTypeDeclaration();
        if (typeDecl == null) {
            return false;  // Unresolved type
        }
        if (typeDecl.isInterface()) {
            return true;
        }
        // Check for abstract class
        if (typeDecl instanceof CtClass) {
            return ((CtClass<?>) typeDecl).isAbstract();
        }
        return false;
    }

    private boolean isDISetter(CtMethod<?> method) {
        if (!method.getSimpleName().startsWith("set") || method.getParameters().size() != 1) {
            return false;
        }
        // Check if all parameters are native types; if so, skip this setter method
        boolean allNative = method.getParameters().stream()
                .map(param -> param.getType())
                .allMatch(SpoonUtils::isJavaNativeType);
        if (allNative) {
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
    private List<CtClass<?>> findImplementations(CtTypeReference<?> interfaceReference) {
        if (implementationsCache.containsKey(interfaceReference)) {
            return implementationsCache.get(interfaceReference);
        }
        List<CtClass<?>> implementations = interfaceReference.getFactory()
                .getModel()
                .filterChildren(new AbstractFilter<CtClass<?>>(CtClass.class) {
                    @Override
                    public boolean matches(CtClass<?> candidate) {
                        // Check if concrete (not abstract) and is subtype
                        return !candidate.isAbstract() &&
                                candidate.getReference().isSubtypeOf(interfaceReference);
                    }
                })
                .list();
        // Cache the result before returning
        implementationsCache.put(interfaceReference, implementations);
        return implementations;
    }

    /**
     * Randomly returns an implementation of an interface.
     */
    private CtTypeReference<?> returnRandomImplementation(CtTypeReference<?> interfaceReference) {
        List<CtClass<?>> implementations = findImplementations(interfaceReference);
        if (!implementations.isEmpty()) {
            Random random = new Random();
            int index = random.nextInt(implementations.size());
            return implementations.get(index).getReference();
        }

        return null;
    }
}