FROM maven:3.9.14-eclipse-temurin-25 AS build

WORKDIR /workspace

COPY . /workspace

RUN mvn -q -DskipTests package

FROM eclipse-temurin:25-jre

WORKDIR /app

COPY --from=build /workspace/target/*.jar /app/app.jar

EXPOSE 8081

ENTRYPOINT ["java", "-jar", "/app/app.jar"]
