package com.idta.plc4x.model;

import lombok.Builder;
import lombok.Data;

import java.time.Instant;

/**
 * Status information for a PLC connection.
 */
@Data
@Builder
public class PlcConnectionStatus {

    private String connectionId;
    private String connectionString;
    private String name;
    private ConnectionState state;
    private String protocol;
    private Instant connectedAt;
    private Instant lastReadAt;
    private Long totalReads;
    private Long failedReads;
    private String errorMessage;

    public enum ConnectionState {
        DISCONNECTED,
        CONNECTING,
        CONNECTED,
        ERROR,
        READING
    }
}
