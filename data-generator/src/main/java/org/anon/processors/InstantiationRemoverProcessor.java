package org.anon.processors;

import spoon.processing.AbstractProcessor;
import spoon.reflect.code.*;

public class InstantiationRemoverProcessor extends AbstractProcessor<CtStatement> {
    public static int modifiedClassesCounter = 0;

    @Override
    public void process(CtStatement stmt) {
        stmt.delete();
        modifiedClassesCounter++;
    }

    @Override
    public boolean isToBeProcessed(CtStatement stmt) {
        if (stmt instanceof CtLocalVariable) {
            CtLocalVariable<?> localVar = (CtLocalVariable<?>) stmt;
            return localVar.getDefaultExpression() instanceof CtConstructorCall;
        } else if (stmt instanceof CtAssignment) {
            CtAssignment<?, ?> assignment = (CtAssignment<?, ?>) stmt;
            return assignment.getAssignment() instanceof CtConstructorCall;
        } else if (stmt instanceof CtConstructorCall) {
            return true;
        }
        return false;
    }

}