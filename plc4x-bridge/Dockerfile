# Build stage
FROM maven:3-eclipse-temurin-25 AS builder

WORKDIR /build

# Copy pom.xml first for dependency caching
COPY pom.xml .

# Download dependencies (cached layer)
RUN mvn dependency:go-offline -B

# Copy source code
COPY src ./src

# Build the application.
# Java 25 requires explicit full annotation processing for Lombok-generated methods.
RUN mvn package -DskipTests -B -Dmaven.compiler.proc=full

# Runtime stage
FROM eclipse-temurin:25-jre-alpine

LABEL maintainer="IDTA Submodel Editor Team"
LABEL description="PLC4X Bridge - Industrial PLC to BaSyx AAS Bridge"

WORKDIR /app

# Create non-root user for security
RUN addgroup -g 1001 plc4x && \
    adduser -u 1001 -G plc4x -D plc4x

# Copy built artifact with final ownership in one layer.
COPY --from=builder --chown=plc4x:plc4x /build/target/*.jar app.jar

# Switch to non-root user
USER plc4x

# Expose the API port
EXPOSE 8090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=30s \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8090/actuator/health || exit 1

# JVM options for containerized environment
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=75.0 -Djava.security.egd=file:/dev/./urandom"

# Run the application
ENTRYPOINT ["java", "-jar", "app.jar"]
