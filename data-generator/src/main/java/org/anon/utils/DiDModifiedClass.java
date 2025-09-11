package org.anon.utils;

public class DiDModifiedClass {
   private String modifiedClassName;
   private String modifiedClassFilePath;


   public DiDModifiedClass(String modifiedClassName, String modifiedClassFilePath) {
      this.modifiedClassName = modifiedClassName;
      this.modifiedClassFilePath = modifiedClassFilePath;
   }

   @Override
   public boolean equals(Object o) {
      return (o instanceof DiDModifiedClass && ((DiDModifiedClass) o).modifiedClassFilePath.equals(this.modifiedClassFilePath) && ((DiDModifiedClass) o).modifiedClassName.equals(this.modifiedClassName));
   }

   @Override
   public String toString() {
      return modifiedClassName;
   }

   public String getModifiedClassName() {
      return this.modifiedClassName;
   }

   public void setModifiedClassName(String modifiedClassName) {
      this.modifiedClassName = modifiedClassName;
   }

   public String getModifiedClassFilePath() {
      return this.modifiedClassFilePath;
   }

   public void setModifiedClassFilePath(String modifiedClassFilePath) {
      this.modifiedClassFilePath = modifiedClassFilePath;
   }



}