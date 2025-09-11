package org.anon.processors;

import org.anon.utils.ClassInformation;
import org.anon.utils.Dependency;
import org.anon.utils.SetUtils;
import org.anon.utils.SpoonUtils;
import spoon.processing.AbstractProcessor;
import spoon.reflect.code.*;
import spoon.reflect.cu.SourcePosition;
import spoon.reflect.declaration.*;
import spoon.reflect.reference.CtFieldReference;
import spoon.reflect.reference.CtTypeReference;
import spoon.reflect.reference.CtVariableReference;
import spoon.reflect.visitor.CtScanner;
import spoon.reflect.visitor.filter.AbstractFilter;

import java.io.File;
import java.util.*;
import java.util.stream.Collectors;

public class UnusedInjectedDependencyProcessor extends AbstractProcessor<CtElement> {
    // Store classes that were modified
    public static Map<String, String> modifiedCallers = new HashMap<>();
    public static Map<String, String> modifiedCallees = new HashMap<>();

    public static Map<String, Set<Dependency>> modifiedClasses = new HashMap<>();

    // Java standard library packages to exclude
    private static final Set<String> JAVA_STANDARD_PACKAGES = Set.of(
            "com.sun.",  "java.", "javafx.", "jdk.", "netscape.javascript", "org.ietf.jgss", "org.w3c", "org.xml."
    );

    // Store DI constructors and setters to remove
    private Set<CtConstructor<?>> diConstructors = new HashSet<>();
    private Set<CtMethod<?>> diSetters = new HashSet<>();

    // To avoid rechecking
    public static Map<CtTypeReference<?>, List<CtClass<?>>> implementationsCache = new HashMap<>();

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
        } else if (element instanceof CtInvocation<?>) {
            processInvocation((CtInvocation<?>) element);
        }
    }
    // Processor methods for each CtElement
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

    }

    @Override
    public void processingDone() {
        // Remove DI setters.
        // Directly instantiate the dependencies in the constructor body while preserving the constructor signature.
        for (CtConstructor<?> ctor : diConstructors) {
            CtClass<?> parentClass = ctor.getParent(CtClass.class);
            if (parentClass != null) {
                // Directly instantiate the class attributed that were previously instantiated through the constructor's parameters.
                // E.g.: // public Class(IDependency dep) {this.dep = dep} => public Class(IDependency dep) {this.dep = new DepImplementation()}
                Set<CtVariableReference<?>> paramRefs = ctor.getParameters().stream()
                        .map(CtParameter::getReference)
                        .collect(Collectors.toSet());
                // Iterate over each stmtnt in the constructor body
                ctor.getBody().getStatements().forEach(ctStatement -> {
                    // Only consider assginment statements
                    if (ctStatement instanceof CtAssignment<?,?>) {
                        CtAssignment<?,?> assignment = (CtAssignment<?,?>) ctStatement;
                        CtExpression<?> lhs = assignment.getAssigned();
                        CtExpression<?> rhs = assignment.getAssignment();
                        if (lhs instanceof CtFieldWrite<?>) {
                            CtFieldReference<?> fieldRef = ((CtFieldWrite<?>) lhs).getVariable();
                            // Get all variable access in the RHS
                            Set<CtVariableReference<?>> rhsVariables = new HashSet<>();
                            rhs.accept(new CtScanner() {
                                @Override
                                public <T> void visitCtVariableRead(CtVariableRead<T> varAccess) {
                                    rhsVariables.add(varAccess.getVariable());
                                    super.visitCtVariableRead(varAccess);
                                }

                                @Override
                                public <T> void visitCtVariableWrite(CtVariableWrite<T> varAccess) {
                                    rhsVariables.add(varAccess.getVariable());
                                    super.visitCtVariableWrite(varAccess);
                                }
                            });
                            // Check if any RHS variable in a constructor parameter
                            boolean usesParam = rhsVariables.stream().anyMatch(paramRefs::contains);

                            if (usesParam) {
                                // Get a random implementation
                                CtTypeReference<?> concreteType = returnRandomImplementation(fieldRef.getType());
                                if (concreteType == null) {
                                    return;
                                }
                                // Replace RHS with constructor call.
                                CtConstructorCall newInstanceCall = getFactory().Code().createConstructorCall(concreteType);
                                assignment.setAssignment(newInstanceCall);
                                // Save information
                                CtType<?> declaringType = parentClass;
                                String classFilePath = SpoonUtils.getOutputRelativePath(declaringType);

                                // Get the dependency detail
                                CtType<?> dependencyType = concreteType.getTypeDeclaration();
                                String dependencyClassName = SpoonUtils.isJavaNativeType(concreteType) ? "EXTERNAL": dependencyType.getQualifiedName();

                                String dependencyFilePath = SpoonUtils.getOutputRelativePath(dependencyType);
                                // Record the depdency relation
                                CtTypeReference<?> parent = SetUtils.getKeyByValue(implementationsCache, dependencyType);
                                List<CtTypeReference<?>> dependencyChain = SpoonUtils.getDependencyChain(concreteType, parent);
                                // Filter classes that do not have a package
                                List<ClassInformation> transformedDependencyChain = dependencyChain.stream()
                                        .map(ct -> new ClassInformation(ct.getSimpleName(), ct.getPackage() != null ? ct.getPackage().getQualifiedName() : "pkg" , SpoonUtils.getOutputRelativePath(ct.getTypeDeclaration())))
                                        .collect(Collectors.toUnmodifiableList());
                                Dependency dependency = new Dependency(dependencyClassName, dependencyFilePath, transformedDependencyChain);
                                if (!modifiedClasses.containsKey(classFilePath)) {
                                    // First get the dependency's parent (interface or abstract)
                                    modifiedClasses.put(classFilePath, new HashSet<>(Arrays.asList(dependency)));
                                } else {
                                    modifiedClasses.get(classFilePath).add(dependency);
                                }

                            }
                        }
                    }
                });

                // Add this class to the list modified callees.
                String className = parentClass.getQualifiedName();
                String filePath = parentClass.getPosition().getFile().getAbsolutePath();
                modifiedCallees.put(className, filePath);
            }
        }
        // Remove the DI setter method
        for (CtMethod<?> setter : diSetters) {
            setter.delete();
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

    // Helper methods
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
        // Check if all parameters are either interfaces or abstracts
        boolean allInterfacesOrAbstract = method.getParameters().stream()
                .map(methpdParameter -> methpdParameter.getType())
                .allMatch(this::isInterfaceOrAbstract);
        if (!allInterfacesOrAbstract) {
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

    private CtTypeReference<?> returnRandomImplementation(CtTypeReference<?> interfaceReference) {
        List<CtClass<?>> implementations = findImplementations(interfaceReference);
        if (!implementations.isEmpty()) {
            Random random = new Random();
            int index = random.nextInt(implementations.size());
            return implementations.get(index).getReference();
        }

        return null;
    }

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

}
