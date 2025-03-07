package org.smart.utils;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

import java.io.FileWriter;
import java.io.IOException;
import java.util.Map;

public class JSONWriter {
    public static void writeToJSON(String outputPath, Object content) throws IOException {
        try (FileWriter fileWriter = new FileWriter(outputPath)) {
            Gson gson = new GsonBuilder().setPrettyPrinting().create();
            gson.toJson(content, fileWriter);
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
}
