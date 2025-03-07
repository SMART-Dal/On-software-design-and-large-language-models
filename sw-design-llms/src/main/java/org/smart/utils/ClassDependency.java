package org.smart.utils;

import java.util.HashMap;
import java.util.Map;

public class ClassDependency {
    private String classFilePath;          // Path of the modified class
    private Map<String, String> dependencies = new HashMap<>(); // Dependency class → its file path

    public ClassDependency(String classFilePath) {
        this.classFilePath = classFilePath;
    }

    public void addDependency(String className, String filePath) {
        dependencies.put(className, filePath);
    }

    // Getters for serialization
    public String getClassFilePath() { return classFilePath; }
    public Map<String, String> getDependencies() { return dependencies; }
}