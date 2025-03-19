package org.smart.utils;

import java.util.ArrayList;
import java.util.List;

public class Dependency {
    private final String dependencyClassName;
    private final String dependencyClassFilePath;
    private final List<ClassInformation> dependencyChain;

    public Dependency(String className, String filePath, List<ClassInformation> dependencyChain) {
        this.dependencyClassName = className;
        this.dependencyClassFilePath = filePath;
        this.dependencyChain = dependencyChain;
    }

    public String getDependencyClassName() {
        return this.dependencyClassName;
    }
    public String getDependencyClassFilePath() {
        return this.dependencyClassFilePath;
    }

    public List<ClassInformation> getDependencyChain() {
        return this.dependencyChain;
    }

}