package org.smart;
import org.smart.processors.*;
import org.smart.utils.*;
import spoon.Launcher;
import spoon.MavenLauncher;
import spoon.OutputType;
import java.io.File;
import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;
import java.util.stream.Collectors;

public class Main {
    public static void main(String[] args) {
        if (args.length < 2) {
            System.err.println("Usage: java -jar software-design-perturbations.jar <repository-path> <output-path> <transformations>");
            System.err.println("Example: java -jar software-design-perturbations.jar /path/to/repo /path/to/output DirectInstantiation,DisableAbstraction");
            System.exit(1);
        }

        String repositoryPath = args[0];
        String outputPath = args[1];
        List<String> transformations = Arrays.asList(args[2].split(","));

        File repoDir = new File(repositoryPath);
        if (!repoDir.exists() || !repoDir.isDirectory()) {
            System.err.println("Error: Repository path does not exist or is not a directory.");
            System.exit(1);
        }


        MavenLauncher launcher = new MavenLauncher(repositoryPath, MavenLauncher.SOURCE_TYPE.ALL_SOURCE);
        launcher.getEnvironment().setAutoImports(true);
        launcher.getEnvironment().setCommentEnabled(true);
        launcher.getEnvironment().setShouldCompile(false); // Some projects use lombok. This affects how getter and setter methods are defined. Alternative: https://projectlombok.org/features/delombok

        String concatenatedTranformations = transformations.stream().collect(Collectors.joining("_"));

        String inputFolderName = PathUtils.getFolderName(repositoryPath);
        String outputFolderName = inputFolderName + "-transformed_" + concatenatedTranformations;

        String outputDir = Paths.get(outputPath, outputFolderName).toString();
        launcher.setSourceOutputDirectory(outputDir);


        launcher.getEnvironment().setOutputType(OutputType.COMPILATION_UNITS);

        Set<Map.Entry<String, String>> modifiedCalless = null;
        Set<Map.Entry<String, String>> modifiedCallers = null;
        Map<String, Set<Dependency>> modifiedClasses = null;
        String dependenciesOutputPath = null;

        boolean isDiD = false;
        boolean isUiD = false;

        for (String transformation : transformations) {
            switch (transformation.trim().toLowerCase()) {
                case "dependencygraph":
                    System.out.println("Generating the dependency graph of the project");
                    DisjointClusterAnalyzer.analyze(repositoryPath);
                    System.out.println("Finished generating the dependency graph of the project and extract all disjoint pairs. Saving on disk...");
                    try {
                        String disjointPairsOutputPath = inputFolderName+"_disjointPairs.json";
                        disjointPairsOutputPath = Paths.get(outputPath, disjointPairsOutputPath).toString();
                        JSONWriter.writeToJSON(disjointPairsOutputPath, DisjointClusterAnalyzer.disjointPairs);
                    } catch (IOException e) {
                        throw new RuntimeException(e);
                    }
                    break;
                case "instantiationremover":
                    System.out.println("Adding InstantiationRemoverProcessor to transformations...");
                    launcher.addProcessor(new InstantiationRemoverProcessor());
                    break;
                case "directinstantiation":
                    System.out.println("Applying Direct Instantiation transformation...");
                    launcher.addProcessor(new DirectInstantiationProcessor());
                    isDiD = true;
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
                    isUiD = true;
                    break;
                default:
                    System.err.println("Error: Unknown transformation '" + transformation + "'.");
                    System.exit(1);
            }
        }

        launcher.run();

        System.out.println("Transformations applied successfully.");
        if (SetUtils.containsStringList(transformations, "instantiationremover")) {
            System.out.println("Number of modified assignment statements: "+InstantiationRemoverProcessor.modifiedClassesCounter);
        }

        if (isDiD) {
            modifiedCalless = DirectInstantiationProcessor.modifiedCallees.entrySet();
            modifiedCallers = DirectInstantiationProcessor.modifiedCallers.entrySet();
            modifiedClasses = DirectInstantiationProcessor.modifiedClasses;
            SetUtils.processModifiedClasses(
                    modifiedCalless,
                    modifiedCallers,
                    modifiedClasses,
                    "did",
                    inputFolderName,
                    outputPath
            );
        }

        if (isUiD) {
            modifiedCalless = UnusedInjectedDependencyProcessor.modifiedCallees.entrySet();
            modifiedCallers = UnusedInjectedDependencyProcessor.modifiedCallers.entrySet();
            modifiedClasses = UnusedInjectedDependencyProcessor.modifiedClasses;
            SetUtils.processModifiedClasses(
                    modifiedCalless,
                    modifiedCallers,
                    modifiedClasses,
                    "uid",
                    inputFolderName,
                    outputPath
            );
        }

        System.out.println("Transformed code saved to: " + outputDir);

    }
}