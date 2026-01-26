package com.idta.plc4x.model;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * Request model for establishing a PLC connection.
 */
@Data
public class PlcConnectionRequest {

    /**
     * PLC connection string in PLC4X format.
     * Examples:
     * - modbus-tcp://192.168.1.100:502
     * - s7://192.168.1.100/0/1 (rack 0, slot 1)
     * - opcua:tcp://192.168.1.100:4840
     * - simulated://127.0.0.1
     */
    @NotBlank(message = "Connection string is required")
    private String connectionString;

    /**
     * Optional connection name for identification.
     */
    private String name;

    /**
     * Connection timeout in milliseconds.
     */
    private Integer timeoutMs;
}
