package org.smart;

import org.smart.utils.PathUtils;
import org.smart.utils.SpoonUtils;
import spoon.Launcher;
import spoon.reflect.CtModel;
import spoon.reflect.declaration.CtClass;
import spoon.reflect.declaration.CtPackage;
import spoon.reflect.visitor.filter.TypeFilter;

import java.io.IOException;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import static org.smart.utils.CSVWriter.writeReportToFile;

/**
 * A class to calculate the "Package Tree Distance" for every pair
 * of classes in a given Java project.
 *
 * The distance is defined as the number of steps required to navigate from one
 * class's package to the other's through their lowest common ancestor in the
 * package hierarchy.
 *
 * Usage:
 * 1. Compile the class with Spoon dependencies (using the provided pom.xml).
 * 2. Run from the command line:
 * java -cp target/your-jar-with-dependencies.jar PackageDistanceCalculator /path/to/your/project/src
 */
public class PackageDistanceCalculator {

    public static void main(String[] args) {
        if (args.length == 0) {
            System.err.println("Error: Please provide the path to the Java project's source folder.");
            System.err.println("Usage: java PackageDistanceCalculator /path/to/project/src");
            return;
        }
        String projectPath = args[0];
        System.err.println("Analyzing project at: " + projectPath);

        String inputFolderName = PathUtils.getFolderName(projectPath);
        String outputFolderName = inputFolderName + "_ptd_distances.csv";
        String outputFileName = Paths.get(PathUtils.getParent(projectPath).toString(), outputFolderName).toString();

        // Configure and Run Spoon
        Launcher spoon = new Launcher();
        spoon.addInputResource(projectPath);
        // Telling Spoon to not auto-compile, as we only need the model
        spoon.getEnvironment().setAutoImports(true);
        spoon.getEnvironment().setNoClasspath(true); // Important for analyzing projects without their dependencies

        System.err.println("Building Spoon model... This may take a moment.");
        spoon.buildModel();
        CtModel model = spoon.getModel();
        System.err.println("Model built successfully.");

        // Collect All Classes
        List<CtClass> allClasses = model.getElements(new TypeFilter<>(CtClass.class));
        // Filter out anonymous and local classes which don't have a meaningful package distance
        allClasses.removeIf(c -> c.isAnonymous() || c.isLocalType() || SpoonUtils.isTestClass(c));

        System.err.println("Found " + allClasses.size() + " classes to analyze.");
        System.err.println("Calculating distances...");

        // Print Pairwise Distances
        // Print CSV header
        List<String> results = new ArrayList<>();
        results.add("ClassA,ClassB,Distance,ProjectName");

        for (int i = 0; i < allClasses.size(); i++) {
            for (int j = i + 1; j < allClasses.size(); j++) {
                CtClass<?> classA = allClasses.get(i);
                CtClass<?> classB = allClasses.get(j);

                int distance = calculateDistance(classA, classB);

                results.add(
                        classA.getQualifiedName() + "," +
                                classB.getQualifiedName() + "," +
                                distance + "," + inputFolderName
                );
            }
        }


        try {
            writeReportToFile(results, outputFileName);
            System.err.println("Analysis complete. Report successfully written to " + outputFileName);
        } catch (IOException e) {
            System.err.println("Error: Failed to write report to file '" + outputFileName + "'.");
            e.printStackTrace();
        }
    }

    /**
     * Calculates the package tree distance between two Spoon CtClass objects.
     *
     * @param classA The first class.
     * @param classB The second class.
     * @return The calculated distance. Returns -1 if one of the classes is in a null package.
     */
    public static int calculateDistance(CtClass<?> classA, CtClass<?> classB) {
        CtPackage packageA = classA.getPackage();
        CtPackage packageB = classB.getPackage();

        // Handle cases where classes might be in the default (unnamed) package
        String pkgAName = (packageA == null || packageA.isUnnamedPackage()) ? "" : packageA.getQualifiedName();
        String pkgBName = (packageB == null || packageB.isUnnamedPackage()) ? "" : packageB.getQualifiedName();

        List<String> pathA = Arrays.asList(pkgAName.split("\\."));
        List<String> pathB = Arrays.asList(pkgBName.split("\\."));

        // Handle empty package names after split
        if (pkgAName.isEmpty()) pathA.clear();
        if (pkgBName.isEmpty()) pathB.clear();

        // Find the length of the longest common prefix (which represents the LCA)
        int lcaIndex = -1;
        int minLength = Math.min(pathA.size(), pathB.size());
        for (int i = 0; i < minLength; i++) {
            if (pathA.get(i).equals(pathB.get(i))) {
                lcaIndex = i;
            } else {
                break;
            }
        }

        // Calculate steps from each path up to the LCA
        // The number of steps is the number of nodes minus the LCA node itself.
        int stepsA = pathA.size() - 1 - lcaIndex;
        int stepsB = pathB.size() - 1 - lcaIndex;

        return stepsA + stepsB;
    }
}
