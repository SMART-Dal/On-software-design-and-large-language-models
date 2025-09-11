package org.anon.utils;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.List;

public class CSVWriter {

    public static void writeReportToFile(List<String> lines, String path) throws IOException {
        Files.write(Paths.get(path), lines, StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING);
    }
}
