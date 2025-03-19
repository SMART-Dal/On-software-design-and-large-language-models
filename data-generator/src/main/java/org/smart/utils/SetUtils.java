package org.smart.utils;

import spoon.reflect.declaration.CtClass;
import spoon.reflect.reference.CtTypeReference;

import java.util.List;
import java.util.Map;

public class SetUtils {

    public static CtTypeReference<?> getKeyByValue(Map<CtTypeReference<?>, List<CtClass<?>>> map, Object x) {
        for (Map.Entry<CtTypeReference<?>, List<CtClass<?>>> entry : map.entrySet()) {
            if (entry.getValue().contains(x)) {
                return entry.getKey();
            }
        }
        return null;
    }
}
