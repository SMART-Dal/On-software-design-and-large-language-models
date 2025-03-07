package org.smart.services;
import org.smart.dependencies.IDependency;
public class Service {
    private String serviceName;

    private String serviceVersion;

    private IDependency privateDependency;

    public Service(IDependency dependency) {
        this.privateDependency = dependency;
    }

    public Service() {
    }

    public void setDependency(IDependency dependency) {
        this.privateDependency = dependency;
    }

    public Service(String name, String version) {
        this.serviceName = name;
        this.serviceVersion = version;
    }
}
