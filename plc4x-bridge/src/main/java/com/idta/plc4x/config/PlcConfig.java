package com.idta.plc4x.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * PLC connection configuration properties.
 */
@Data
@Configuration
@ConfigurationProperties(prefix = "plc")
public class PlcConfig {

    /**
     * Default PLC connection string.
     */
    private String defaultConnection = "simulated://127.0.0.1";

    /**
     * Connection timeout in milliseconds.
     */
    private int connectionTimeout = 5000;

    /**
     * Read interval for continuous reading (milliseconds).
     */
    private long readInterval = 1000;

    /**
     * Retry configuration.
     */
    private RetryConfig retry = new RetryConfig();

    @Data
    public static class RetryConfig {
        /**
         * Maximum retry attempts.
         */
        private int maxAttempts = 3;

        /**
         * Delay between retries in milliseconds.
         */
        private long delayMs = 1000;
    }
}
