package org.smart.processors;

import spoon.processing.AbstractProcessor;
import spoon.reflect.code.CtAssignment;
import spoon.reflect.code.CtFieldAccess;
import spoon.reflect.code.CtStatement;
import spoon.reflect.code.CtVariableAccess;
import spoon.reflect.declaration.*;
import spoon.reflect.factory.Factory;
import spoon.reflect.reference.CtTypeReference;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;
import java.util.Set;

public class DirectInstantiationProcessor extends AbstractProcessor<CtConstructor<?>> {
    // Java standard library packages to exclude
    private static final Set<String> JAVA_STANDARD_PACKAGES = Set.of(
            "com.sun.jarsigner",
            "com.sun.java.accessibility.util",
            "com.sun.javadoc",
            "com.sun.jdi",
            "com.sun.jdi.connect",
            "com.sun.jdi.connect.spi",
            "com.sun.jdi.event",
            "com.sun.jdi.request",
            "com.sun.management",
            "com.sun.net.httpserver",
            "com.sun.net.httpserver.spi",
            "com.sun.nio.sctp",
            "com.sun.security.auth",
            "com.sun.security.auth.callback",
            "com.sun.security.auth.login",
            "com.sun.security.auth.module",
            "com.sun.security.jgss",
            "com.sun.source.doctree",
            "com.sun.source.tree",
            "com.sun.source.util",
            "com.sun.tools.attach",
            "com.sun.tools.attach.spi",
            "com.sun.tools.javac",
            "com.sun.tools.javadoc",
            "com.sun.tools.jconsole",
            "java.applet",
            "java.awt",
            "java.awt.color",
            "java.awt.datatransfer",
            "java.awt.desktop",
            "java.awt.dnd",
            "java.awt.event",
            "java.awt.font",
            "java.awt.geom",
            "java.awt.im",
            "java.awt.im.spi",
            "java.awt.image",
            "java.awt.image.renderable",
            "java.awt.print",
            "java.beans",
            "java.beans.beancontext",
            "java.io",
            "java.lang",
            "java.lang.annotation",
            "java.lang.instrument",
            "java.lang.invoke",
            "java.lang.management",
            "java.lang.module",
            "java.lang.ref",
            "java.lang.reflect",
            "java.math",
            "java.net",
            "java.net.http",
            "java.net.spi",
            "java.nio",
            "java.nio.channels",
            "java.nio.channels.spi",
            "java.nio.charset",
            "java.nio.charset.spi",
            "java.nio.file",
            "java.nio.file.attribute",
            "java.nio.file.spi",
            "java.rmi",
            "java.rmi.activation",
            "java.rmi.dgc",
            "java.rmi.registry",
            "java.rmi.server",
            "java.security",
            "java.security.acl",
            "java.security.cert",
            "java.security.interfaces",
            "java.security.spec",
            "java.sql",
            "java.text",
            "java.text.spi",
            "java.time",
            "java.time.chrono",
            "java.time.format",
            "java.time.temporal",
            "java.time.zone",
            "java.util",
            "java.util.concurrent",
            "java.util.concurrent.atomic",
            "java.util.concurrent.locks",
            "java.util.function",
            "java.util.jar",
            "java.util.logging",
            "java.util.prefs",
            "java.util.regex",
            "java.util.spi",
            "java.util.stream",
            "java.util.zip",
            "javax.accessibility",
            "javax.annotation.processing",
            "javax.crypto",
            "javax.crypto.interfaces",
            "javax.crypto.spec",
            "javax.imageio",
            "javax.imageio.event",
            "javax.imageio.metadata",
            "javax.imageio.plugins.bmp",
            "javax.imageio.plugins.jpeg",
            "javax.imageio.plugins.tiff",
            "javax.imageio.spi",
            "javax.imageio.stream",
            "javax.lang.model",
            "javax.lang.model.element",
            "javax.lang.model.type",
            "javax.lang.model.util",
            "javax.management",
            "javax.management.loading",
            "javax.management.modelmbean",
            "javax.management.monitor",
            "javax.management.openmbean",
            "javax.management.relation",
            "javax.management.remote",
            "javax.management.remote.rmi",
            "javax.management.timer",
            "javax.naming",
            "javax.naming.directory",
            "javax.naming.event",
            "javax.naming.ldap",
            "javax.naming.spi",
            "javax.net",
            "javax.net.ssl",
            "javax.print",
            "javax.print.attribute",
            "javax.print.attribute.standard",
            "javax.print.event",
            "javax.rmi.ssl",
            "javax.script",
            "javax.security.auth",
            "javax.security.auth.callback",
            "javax.security.auth.kerberos",
            "javax.security.auth.login",
            "javax.security.auth.spi",
            "javax.security.auth.x500",
            "javax.security.cert",
            "javax.security.sasl",
            "javax.smartcardio",
            "javax.sound.midi",
            "javax.sound.midi.spi",
            "javax.sound.sampled",
            "javax.sound.sampled.spi",
            "javax.sql",
            "javax.sql.rowset",
            "javax.sql.rowset.serial",
            "javax.sql.rowset.spi",
            "javax.swing",
            "javax.swing.border",
            "javax.swing.colorchooser",
            "javax.swing.event",
            "javax.swing.filechooser",
            "javax.swing.plaf",
            "javax.swing.plaf.basic",
            "javax.swing.plaf.metal",
            "javax.swing.plaf.multi",
            "javax.swing.plaf.nimbus",
            "javax.swing.plaf.synth",
            "javax.swing.table",
            "javax.swing.text",
            "javax.swing.text.html",
            "javax.swing.text.html.parser",
            "javax.swing.text.rtf",
            "javax.swing.tree",
            "javax.swing.undo",
            "javax.tools",
            "javax.transaction.xa",
            "javax.xml",
            "javax.xml.catalog",
            "javax.xml.crypto",
            "javax.xml.crypto.dom",
            "javax.xml.crypto.dsig",
            "javax.xml.crypto.dsig.dom",
            "javax.xml.crypto.dsig.keyinfo",
            "javax.xml.crypto.dsig.spec",
            "javax.xml.datatype",
            "javax.xml.namespace",
            "javax.xml.parsers",
            "javax.xml.stream",
            "javax.xml.stream.events",
            "javax.xml.stream.util",
            "javax.xml.transform",
            "javax.xml.transform.dom",
            "javax.xml.transform.sax",
            "javax.xml.transform.stax",
            "javax.xml.transform.stream",
            "javax.xml.validation",
            "javax.xml.xpath",
            "jdk.dynalink",
            "jdk.dynalink.beans",
            "jdk.dynalink.linker",
            "jdk.dynalink.linker.support",
            "jdk.dynalink.support",
            "jdk.javadoc.doclet",
            "jdk.jfr",
            "jdk.jfr.consumer",
            "jdk.jshell",
            "jdk.jshell.execution",
            "jdk.jshell.spi",
            "jdk.jshell.tool",
            "jdk.management.jfr",
            "jdk.nashorn.api.scripting",
            "jdk.nashorn.api.tree",
            "jdk.net",
            "jdk.nio",
            "jdk.security.jarsigner",
            "netscape.javascript",
            "org.ietf.jgss",
            "org.w3c.dom",
            "org.w3c.dom.bootstrap",
            "org.w3c.dom.css",
            "org.w3c.dom.events",
            "org.w3c.dom.html",
            "org.w3c.dom.ls",
            "org.w3c.dom.ranges",
            "org.w3c.dom.stylesheets",
            "org.w3c.dom.traversal",
            "org.w3c.dom.views",
            "org.w3c.dom.xpath",
            "org.xml.sax",
            "org.xml.sax.ext",
            "org.xml.sax.helpers"
    );
    @Override
    public void process(CtConstructor<?> constructor) {
        if (constructor.getParameters().isEmpty()) {
            return;
        }
        // Check if the constructor has parameters (dependencies)
        if (!constructor.getParameters().isEmpty()) {
            // Check if all parameters are user-defined types
            boolean allUserDefined = constructor.
                    getParameters().
                    stream().
                    allMatch(ctParameter -> isUserDefineType(ctParameter.getType()));
            if (allUserDefined) {
                /**
                 * We analyze the constructor body by iterating over its statements.
                 * We look for assignment statements where a field is being assigned the value of a parameter.
                 */
                Factory factory = constructor.getFactory();
                // Iterate over the parameters of the constructor
                List<CtParameter<?>> parameters = constructor.getParameters();
                for (CtParameter<?> parameter : parameters) {
                    // Find the field corresponding to the parameter
                    CtField<?> field = findFieldForParameter(constructor, parameter);
                    if (field != null) {
                        // Account for interfaces
                        CtTypeReference<?> parameterType = parameter.getType();
                        if (parameterType.isInterface()) {
                            // Select a random implementation
                            CtType<?> implementation = returnRandomImplementation(parameterType);
                            if (implementation != null) {
                                CtStatement assignment = factory.createCodeSnippetStatement(
                                        "this."+ field.getSimpleName() + " = new " + implementation.getSimpleName() + "()"
                                );
                                // Insert
                                constructor.getBody().insertEnd(assignment);
                                // Delete old statement
                                deleteOldAssignment(constructor, field, parameter);
                            } else {
                                System.out.println("No implementation found for interface: "+ parameterType.getQualifiedName());
                            }
                        } else {
                            // Create a direct instantiation statement for the field
                            CtStatement assignment = factory.createCodeSnippetStatement(
                                    "this." + field.getSimpleName() + " = new " + parameter.getType().getSimpleName() + "()"
                            );
                            // Insert the assignment at the end of the constructor body
                            constructor.getBody().insertEnd(assignment);

                            // Delete the old assignment statement
                            deleteOldAssignment(constructor, field, parameter);
                        }
                    }
                }
                // Clear the parameters from the constructor
                constructor.getParameters().clear();
            }
        }
    }
    /**
     * Checks if a type is user-defined.
     */
    private boolean isUserDefineType(CtTypeReference<?> typeReference) {
        if (typeReference.isPrimitive()) {
            return false;
        }

        String qualifiedName = typeReference.getQualifiedName();
        for (String javaPackage: JAVA_STANDARD_PACKAGES) {
            if (qualifiedName.startsWith(javaPackage+".")) {
                return false;
            }
        }

        return true;
    }

    /**
     * Finds the field that corresponds to a constructor parameter
     */
    private CtField<?> findFieldForParameter(CtConstructor<?> constructor, CtParameter<?> parameter) {
        // Get the declaring type of the constructor, i.e. the class
        CtType<?> declaringType = constructor.getDeclaringType();

        // Iterate over the statements in the constructor body
        List<CtStatement> statements = constructor.getBody().getStatements();
        for (CtStatement statement: statements) {
            // Check if it's an assignment
            if (statement instanceof CtAssignment<?,?>) {
                CtAssignment<?,?> assignment = (CtAssignment<?,?>) statement;
                // Check if the LHS of assignment is a field access
                if (assignment.getAssigned() instanceof CtFieldAccess<?>) {
                    CtFieldAccess<?> fieldAccess = (CtFieldAccess<?>) assignment.getAssigned();
                    // Check if RHS is the parameter
                    if (assignment.getAssignment() instanceof CtVariableAccess<?>) {
                        CtVariableAccess<?> variableAccess = (CtVariableAccess<?>) assignment.getAssignment();
                        // Compare the parameter name with the variable name
                        if (variableAccess.getVariable().getSimpleName().equals(parameter.getSimpleName())) {
                            // Find the field in class (declaring type)
                            List<CtField<?>> fields = declaringType.getFields();
                            for (CtField<?> field: fields) {
                                if (field.getSimpleName().equals(fieldAccess.getVariable().getSimpleName())) {
                                    return field;
                                }
                            }
                        }
                    }
                }
            }
        }
        return null;
    }

    /**
     * Delete the old assignment statement for the given parameter and field.
     */
    private void deleteOldAssignment(CtConstructor<?> constructor, CtField<?> field, CtParameter<?> parameter) {
        List<CtStatement> statements = constructor.getBody().getStatements();
        for (CtStatement statement: statements) {
            // Make sure we are in an assignment statement
            if (statement instanceof CtAssignment<?,?>) {
                CtAssignment<?,?> assignment = (CtAssignment<?,?>) statement;
                // Check if LHS is a field access
                if (assignment.getAssigned() instanceof CtFieldAccess<?>) {
                    CtFieldAccess<?> fieldAccess = (CtFieldAccess<?>) assignment.getAssigned();
                    // Check if RHS is the parameter
                    if (assignment.getAssignment() instanceof CtVariableAccess<?>) {
                        CtVariableAccess<?> variableAccess = (CtVariableAccess<?>) assignment.getAssignment();

                        // Compare the parameter name and field name
                        if ( variableAccess.getVariable().getSimpleName().equals(parameter.getSimpleName())
                        && fieldAccess.getVariable().getSimpleName().equals(field.getSimpleName()) ) {
                            statement.delete();
                            break;
                        }
                    }
                }
            }
        }
    }

    /**
     * Finds all implementations of a given interface
     */
    private List<CtType<?>> findImplementations(CtTypeReference<?> interfaceReference) {
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
        return implementations;
    }

    /**
     * Randomly returns an implementation of an interface.
     */
    private CtType<?> returnRandomImplementation(CtTypeReference<?> interfaceReference) {
        List<CtType<?>> implementations = findImplementations(interfaceReference);
        if (!implementations.isEmpty()) {
            Random random = new Random();
            int index = random.nextInt(implementations.size());
            return implementations.get(index);
        }

        return null;
    }
}