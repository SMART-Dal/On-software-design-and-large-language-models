package org.smart;
import org.smart.processors.*;
import spoon.Launcher;
import spoon.SpoonAPI;
import spoon.processing.ProcessingManager;
import spoon.reflect.CtModel;
import spoon.reflect.declaration.CtClass;
import spoon.reflect.declaration.CtType;
import spoon.reflect.factory.Factory;
import spoon.support.QueueProcessingManager;
import spoon.support.compiler.FileSystemFolder;

import java.io.File;
import java.util.Arrays;
import java.util.List;

public class Main {

    public static void main(String[] args) {
        if (args.length < 2) {
            System.err.println("Usage: java -jar software-design-perturbations.jar <repository-path> <transformations>");
            System.err.println("Example: java -jar software-design-perturbations.jar /path/to/repo DirectInstantiation,DisableAbstraction");
            System.exit(1);
        }

        // Parse CLI arguments
        String repositoryPath = args[0];
        List<String> transformations = Arrays.asList(args[1].split(","));

        // Validate repository path
        File repoDir = new File(repositoryPath);
        if (!repoDir.exists() || !repoDir.isDirectory()) {
            System.err.println("Error: Repository path does not exist or is not a directory.");
            System.exit(1);
        }

        // Initialize Spoon launcher
        Launcher launcher = new Launcher();
        launcher.addInputResource(new FileSystemFolder(repositoryPath));
        launcher.getEnvironment().setAutoImports(true);
        launcher.getEnvironment().setCommentEnabled(true);
        launcher.run();
        Factory factory = launcher.getFactory();
        ProcessingManager processingManager = new QueueProcessingManager(factory);

        // Apply transformations
        for (String transformation : transformations) {
            switch (transformation.trim().toLowerCase()) {
                case "directinstantiation":
                    System.out.println("Applying Direct Instantiation transformation...");
                    processingManager.addProcessor(new DirectInstantiationProcessor());
                    break;
                case "disableabstraction":
                    System.out.println("Applying Disable Abstraction transformation...");
                    processingManager.addProcessor(new DisableAbstractionProcessor());
                    break;
                case "godclass":
                    System.out.println("Applying God Class transformation...");
                    processingManager.addProcessor(new GodClassProcessor());
                    break;
                case "featureenvy":
                    System.out.println("Applying Feature Envy transformation...");
                    processingManager.addProcessor(new FeatureEnvyProcessor());
                    break;
                default:
                    System.err.println("Error: Unknown transformation '" + transformation + "'.");
                    System.exit(1);
            }
        }
        // Execute all processes
        processingManager.process(factory.Class().getAll());

        // Output transformed code to a new directory
        String outputDir = repositoryPath + "-transformed";
        launcher.setSourceOutputDirectory(outputDir);
        launcher.prettyprint();
        System.out.println("Writing transformed code to: " + outputDir);

        // Print summary
        System.out.println("Transformations applied successfully.");
        System.out.println("Transformed code saved to: " + outputDir);
    }
}