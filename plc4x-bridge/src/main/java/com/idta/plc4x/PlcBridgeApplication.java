package com.idta.plc4x;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * PLC4X Bridge Application
 *
 * This microservice bridges industrial PLCs to the BaSyx AAS Server.
 * It reads values from PLCs using Apache PLC4X and pushes them to
 * AAS submodel elements.
 *
 * Supported protocols:
 * - Modbus TCP/RTU
 * - Siemens S7 (S7-300, S7-400, S7-1200, S7-1500)
 * - OPC UA
 * - Simulated (for testing)
 */
@SpringBootApplication
@EnableScheduling
public class PlcBridgeApplication {

    public static void main(String[] args) {
        SpringApplication.run(PlcBridgeApplication.class, args);
    }
}
