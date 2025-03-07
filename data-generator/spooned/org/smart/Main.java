package org.smart;
import org.smart.dependencies.DependencyA;
import org.smart.dependencies.DependencyB;
import org.smart.dependencies.IDependency;
import org.smart.services.Service;
public class Main {
    public static void main(String[] args) {
        System.out.println("Hello world!");
        IDependency dependency = new DependencyA();
        Service service = new Service(dependency);
        Service otherService = new Service();
        otherService.setDependency(new DependencyB());
    }
}
