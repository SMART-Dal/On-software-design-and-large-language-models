package org.smart;
import org.smart.processors.*;
import org.smart.utils.Dependency;
import org.smart.utils.DisjointClusterAnalyzer;
import org.smart.utils.JSONWriter;
import spoon.Launcher;
import spoon.OutputType;
import spoon.reflect.CtModel;
import spoon.reflect.declaration.CtClass;
import spoon.reflect.declaration.CtType;
import spoon.reflect.reference.CtTypeReference;

import java.io.File;
import java.io.IOException;
import java.util.*;

public class Main {
    public static void main(String[] args) {
        if (args.length < 2) {
            System.err.println("Usage: java -jar software-design-perturbations.jar <repository-path> <transformations>");
            System.err.println("Example: java -jar software-design-perturbations.jar /path/to/repo DirectInstantiation,DisableAbstraction");
            System.exit(1);
        }

        String repositoryPath = args[0];
        List<String> transformations = Arrays.asList(args[1].split(","));

        File repoDir = new File(repositoryPath);
        if (!repoDir.exists() || !repoDir.isDirectory()) {
            System.err.println("Error: Repository path does not exist or is not a directory.");
            System.exit(1);
        }

        Launcher launcher = new Launcher();
        launcher.addInputResource(repositoryPath);
        launcher.getEnvironment().setAutoImports(true);
        launcher.getEnvironment().setCommentEnabled(true);

        String outputDir = repositoryPath + "-transformed";
        launcher.setSourceOutputDirectory(outputDir);
        launcher.getEnvironment().setOutputType(OutputType.COMPILATION_UNITS);


        boolean didOccured = false;
        boolean uidOccured = false;
        for (String transformation : transformations) {
            switch (transformation.trim().toLowerCase()) {
                case "dependencygraph":
                    System.out.println("Generating the dependency graph of the project");
                    DisjointClusterAnalyzer.analyze(repositoryPath);
                    System.out.println("Finished generating the dependency graph of the project and extract all disjoint pairs. Saving on disk...");
                    try {
                        String dependenciesOutputPath = repositoryPath+"_disjointPairs.json";
                        JSONWriter.writeToJSON(dependenciesOutputPath, DisjointClusterAnalyzer.disjointPairs);
                    } catch (IOException e) {
                        throw new RuntimeException(e);
                    }
                    break;
                case "directinstantiation":
                    System.out.println("Applying Direct Instantiation transformation...");
                    launcher.addProcessor(new DirectInstantiationProcessor());
                    didOccured = true;
                    break;
                case "disableabstraction":
                    System.out.println("Applying Disable Abstraction transformation...");
                    launcher.addProcessor(new DisableAbstractionProcessor());
                    break;
                case "godclass":
                    System.out.println("Applying God Class transformation...");
                    launcher.addProcessor(new GodClassProcessor());
                    break;
                case "featureenvy":
                    System.out.println("Applying Feature Envy transformation...");
                    launcher.addProcessor(new FeatureEnvyProcessor());
                    break;
                case "unusedinjecteddependency":
                    System.out.println("Applying Unused Dependency transformation...");
                    launcher.addProcessor(new UnusedInjectedDependencyProcessor());
                    uidOccured = true;
                    break;
                default:
                    System.err.println("Error: Unknown transformation '" + transformation + "'.");
                    System.exit(1);
            }
        }

        launcher.run();

        System.out.println("Transformations applied successfully.");
        System.out.println("Transformed code saved to: " + outputDir);

        if (didOccured || uidOccured) {
            // Report modified classes for DirectInstantiationProcessor and UnusedInjectedDependency
            Set<Map.Entry<String, String>> modifiedCalless = didOccured ? DirectInstantiationProcessor.modifiedCallees.entrySet() : UnusedInjectedDependencyProcessor.modifiedCallees.entrySet();
            Set<Map.Entry<String, String>> modifiedCallers = didOccured ? DirectInstantiationProcessor.modifiedCallers.entrySet() : UnusedInjectedDependencyProcessor.modifiedCallers.entrySet();
            Map<String, Set<Dependency>> modifiedClasses = didOccured ? DirectInstantiationProcessor.modifiedClasses : UnusedInjectedDependencyProcessor.modifiedClasses;
            System.out.println("The following classes have been transformed used to implement DI:");
            for (Map.Entry<String, String> entry : modifiedCalless) {
                System.out.println("\t" + entry.getKey() + " (" + entry.getValue() + ")");
            }
            System.out.println("The following classes have been transformed used to call classes that implement DI:");
            for (Map.Entry<String, String> entry : modifiedCallers) {
                System.out.println("\t" + entry.getKey() + " (" + entry.getValue() + ")");
            }
            String dependenciesOutputPath = repositoryPath+"_dependencies.json";
            System.out.println("Saving dependencies mapping to: " + dependenciesOutputPath);
            try {
                JSONWriter.writeToJSON(dependenciesOutputPath, modifiedClasses);
            } catch (IOException e) {
                throw new RuntimeException(e);
            }
        }

    }
}