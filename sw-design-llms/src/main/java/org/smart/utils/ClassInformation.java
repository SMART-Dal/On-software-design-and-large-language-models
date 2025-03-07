package org.smart.utils;

public class ClassInformation {
    // Utility class that holds a class's basic information
    private String className;
    private String packageName;
    private String filePath;

    public ClassInformation(String className, String packageName, String filePath) {
        this.className = className;
        this.packageName = packageName;
        this.filePath = filePath;
    }

    public String getClassName() {
        return className;
    }
    public String getPackageName() {
        return packageName;
    }
    public String getFilePath() {
        return filePath;
    }

    public void setFilePath(String filePath) {
        this.filePath = filePath;
    }

    public void setClassName(String className) {
        this.className = className;
    }

    public void setPackageName(String packageName) {
        this.packageName = packageName;
    }
}