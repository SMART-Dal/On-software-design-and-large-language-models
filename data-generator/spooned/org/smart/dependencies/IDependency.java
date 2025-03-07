package org.smart.dependencies;
import java.io.File;
public interface IDependency {
    public void read(File file);

    public void write(File file);

    public String getName();
}
