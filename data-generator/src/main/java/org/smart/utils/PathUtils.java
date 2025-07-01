package org.smart.utils;

import java.nio.file.Path;
import java.nio.file.Paths;

public class PathUtils {

    public static String getFolderName(String fullPath) {
        Path path = Paths.get(fullPath);
        Path fileName = path.getFileName();

        if (fileName != null) {
            return fileName.toString();
        }

        // Handle root paths
        if (path.getRoot() != null) {
            return path.getRoot().toString();
        }

        return ""; // Fallback for empty paths
    }

    public static Path getParent(String pathString) {
        Path path = Paths.get(pathString);
        if (path.getParent() != null) {
            return path.getParent();
        }
        return null;
    }
}
