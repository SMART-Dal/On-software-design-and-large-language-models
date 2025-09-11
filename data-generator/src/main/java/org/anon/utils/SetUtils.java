package org.anon.utils;

import spoon.reflect.declaration.CtClass;
import spoon.reflect.reference.CtTypeReference;

import java.io.IOException;
import java.nio.file.Paths;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

public class SetUtils {

    public static CtTypeReference<?> getKeyByValue(Map<CtTypeReference<?>, List<CtClass<?>>> map, Object x) {
        for (Map.Entry<CtTypeReference<?>, List<CtClass<?>>> entry : map.entrySet()) {
            if (entry.getValue().contains(x)) {
                return entry.getKey();
            }
        }
        return null;
    }

    public static boolean containsStringList(List<String> array, String target) {
        List<String> list = array.stream().map(String::toLowerCase).collect(Collectors.toList());
        ;
        return list.contains(target.trim().toLowerCase());
    }

    public static void processModifiedClasses(Set<Map.Entry<String, String>> modifiedCallees,
                                              Set<Map.Entry<String, String>> modifiedCallers,
                                              Map<String, Set<Dependency>> modifiedClasses,
                                              String suffix,
                                              String inputFolderName,
                                              String outputPath) {
        System.out.println("Classes that used to implement DI:");
        for (Map.Entry<String, String> entry : modifiedCallees) {
            System.out.println("\t" + entry.getKey() + " (" + entry.getValue() + ")");
        }

        System.out.println("The following classes have been transformed used to call classes that implement DI:");
        for (Map.Entry<String, String> entry : modifiedCallers) {
            System.out.println("\t" + entry.getKey() + " (" + entry.getValue() + ")");
        }

        String dependenciesOutputPath = inputFolderName + "_mutated_classes_" + suffix + ".json";
        dependenciesOutputPath = Paths.get(outputPath, dependenciesOutputPath).toString();
        System.out.println("Saving dependencies mapping to: " + dependenciesOutputPath);

        try {
            JSONWriter.writeToJSON(dependenciesOutputPath, modifiedClasses);
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }
}