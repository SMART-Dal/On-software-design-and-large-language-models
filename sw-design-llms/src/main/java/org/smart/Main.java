package org.smart;
import org.smart.processors.*;
import spoon.Launcher;
import spoon.OutputType;
import spoon.reflect.CtModel;

import java.io.File;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

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



        for (String transformation : transformations) {
            switch (transformation.trim().toLowerCase()) {
                case "directinstantiation":
                    System.out.println("Applying Direct Instantiation transformation...");
                    launcher.addProcessor(new DirectInstantiationProcessor());
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
                default:
                    System.err.println("Error: Unknown transformation '" + transformation + "'.");
                    System.exit(1);
            }
        }

        launcher.run();

        System.out.println("Transformations applied successfully.");
        System.out.println("Transformed code saved to: " + outputDir);

        // Report modified classes for DirectInstantiationProcessor
        System.out.println("The following classes have been transformed using Direct Instantiation transformation:");
        for (Map.Entry<String, String> entry : DirectInstantiationProcessor.modifiedClasses.entrySet()) {
            System.out.println("\t" + entry.getKey() + " (" + entry.getValue() + ")");
        }
    }
}