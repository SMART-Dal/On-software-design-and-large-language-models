package org.smart;
public class Service {
    private String serviceName;

    private String serviceVersion;

    private IDependency privateDependency;

    public Service(IDependency dependency) {
        this.privateDependency = dependency;
    }

    public Service(String name, String version) {
        this.serviceName = name;
        this.serviceVersion = version;
    }
}
