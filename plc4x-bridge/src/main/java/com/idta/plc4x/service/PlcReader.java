package com.idta.plc4x.service;

import com.idta.plc4x.config.PlcConfig;
import com.idta.plc4x.model.PlcConnectionRequest;
import com.idta.plc4x.model.PlcConnectionStatus;
import com.idta.plc4x.model.PlcTag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.plc4x.java.api.PlcConnection;
import org.apache.plc4x.java.api.PlcConnectionManager;
import org.apache.plc4x.java.api.PlcDriverManager;
import org.apache.plc4x.java.api.messages.PlcReadRequest;
import org.apache.plc4x.java.api.messages.PlcReadResponse;
import org.apache.plc4x.java.api.types.PlcResponseCode;
import org.springframework.stereotype.Service;

import jakarta.annotation.PreDestroy;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;

/**
 * Service for managing PLC connections and reading values using Apache PLC4X.
 *
 * Supported protocols:
 * - modbus-tcp: Modbus TCP/IP
 * - s7: Siemens S7 (S7-300, S7-400, S7-1200, S7-1500)
 * - opcua: OPC UA
 * - simulated: Simulated PLC for testing
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class PlcReader {

    private final PlcConfig plcConfig;
    private final PlcConnectionManager connectionManager = PlcDriverManager.getDefault().getConnectionManager();

    /**
     * Active connections (connectionId -> PlcConnection).
     */
    private final Map<String, PlcConnection> connections = new ConcurrentHashMap<>();

    /**
     * Connection metadata (connectionId -> status).
     */
    private final Map<String, PlcConnectionStatus> connectionStatuses = new ConcurrentHashMap<>();

    /**
     * Connect to a PLC.
     *
     * @param request Connection request
     * @return Connection status
     */
    public PlcConnectionStatus connect(PlcConnectionRequest request) {
        String connectionId = UUID.randomUUID().toString();
        String connectionString = request.getConnectionString();

        log.info("Connecting to PLC: {} (id: {})", connectionString, connectionId);

        PlcConnectionStatus.PlcConnectionStatusBuilder statusBuilder = PlcConnectionStatus.builder()
                .connectionId(connectionId)
                .connectionString(connectionString)
                .name(request.getName() != null ? request.getName() : extractProtocol(connectionString))
                .protocol(extractProtocol(connectionString))
                .state(PlcConnectionStatus.ConnectionState.CONNECTING)
                .totalReads(0L)
                .failedReads(0L);

        try {
            PlcConnection connection = connectionManager.getConnection(connectionString);

            if (!connection.isConnected()) {
                throw new RuntimeException("Failed to establish connection");
            }

            connections.put(connectionId, connection);

            PlcConnectionStatus status = statusBuilder
                    .state(PlcConnectionStatus.ConnectionState.CONNECTED)
                    .connectedAt(Instant.now())
                    .build();

            connectionStatuses.put(connectionId, status);
            log.info("Successfully connected to PLC: {}", connectionString);

            return status;

        } catch (Exception e) {
            log.error("Failed to connect to PLC: {}", connectionString, e);

            PlcConnectionStatus status = statusBuilder
                    .state(PlcConnectionStatus.ConnectionState.ERROR)
                    .errorMessage(e.getMessage())
                    .build();

            connectionStatuses.put(connectionId, status);
            return status;
        }
    }

    /**
     * Disconnect from a PLC.
     *
     * @param connectionId Connection identifier
     * @return true if disconnected successfully
     */
    public boolean disconnect(String connectionId) {
        PlcConnection connection = connections.remove(connectionId);
        if (connection != null) {
            try {
                connection.close();
                log.info("Disconnected from PLC: {}", connectionId);

                PlcConnectionStatus status = connectionStatuses.get(connectionId);
                if (status != null) {
                    connectionStatuses.put(connectionId, PlcConnectionStatus.builder()
                            .connectionId(connectionId)
                            .connectionString(status.getConnectionString())
                            .name(status.getName())
                            .protocol(status.getProtocol())
                            .state(PlcConnectionStatus.ConnectionState.DISCONNECTED)
                            .totalReads(status.getTotalReads())
                            .failedReads(status.getFailedReads())
                            .build());
                }
                return true;
            } catch (Exception e) {
                log.error("Error disconnecting from PLC: {}", connectionId, e);
            }
        }
        return false;
    }

    /**
     * Read multiple tags from a PLC.
     *
     * @param connectionId Connection identifier
     * @param tagAddresses Map of tag name to PLC address
     * @return Map of tag name to read result
     */
    public Map<String, PlcTag> readTags(String connectionId, Map<String, String> tagAddresses) {
        Map<String, PlcTag> results = new HashMap<>();
        PlcConnection connection = connections.get(connectionId);

        if (connection == null || !connection.isConnected()) {
            log.warn("Connection not available: {}", connectionId);
            tagAddresses.forEach((name, address) ->
                    results.put(name, PlcTag.builder()
                            .name(name)
                            .address(address)
                            .quality(PlcTag.TagQuality.BAD)
                            .build()));
            return results;
        }

        try {
            // Build read request
            PlcReadRequest.Builder builder = connection.readRequestBuilder();
            tagAddresses.forEach(builder::addTagAddress);

            PlcReadRequest readRequest = builder.build();
            PlcReadResponse response = readRequest.execute().get(
                    plcConfig.getConnectionTimeout(), TimeUnit.MILLISECONDS);

            // Process response
            long timestamp = System.currentTimeMillis();
            for (String tagName : tagAddresses.keySet()) {
                PlcResponseCode responseCode = response.getResponseCode(tagName);
                PlcTag.PlcTagBuilder tagBuilder = PlcTag.builder()
                        .name(tagName)
                        .address(tagAddresses.get(tagName))
                        .timestamp(timestamp);

                if (responseCode == PlcResponseCode.OK) {
                    Object value = response.getObject(tagName);
                    tagBuilder
                            .value(value)
                            .dataType(value != null ? value.getClass().getSimpleName() : "null")
                            .quality(PlcTag.TagQuality.GOOD);
                } else {
                    tagBuilder.quality(PlcTag.TagQuality.BAD);
                }

                results.put(tagName, tagBuilder.build());
            }

            // Update statistics
            updateReadStats(connectionId, true);

        } catch (Exception e) {
            log.error("Error reading tags from PLC: {}", connectionId, e);
            updateReadStats(connectionId, false);

            tagAddresses.forEach((name, address) ->
                    results.put(name, PlcTag.builder()
                            .name(name)
                            .address(address)
                            .quality(PlcTag.TagQuality.BAD)
                            .build()));
        }

        return results;
    }

    /**
     * Read a single tag from a PLC.
     *
     * @param connectionId Connection identifier
     * @param tagName      Tag name
     * @param address      PLC address
     * @return Tag with value
     */
    public PlcTag readTag(String connectionId, String tagName, String address) {
        Map<String, PlcTag> result = readTags(connectionId, Map.of(tagName, address));
        return result.get(tagName);
    }

    /**
     * Get list of discovered tags (for protocols that support browsing).
     *
     * @param connectionId Connection identifier
     * @return List of discovered tags
     */
    public List<PlcTag> discoverTags(String connectionId) {
        PlcConnection connection = connections.get(connectionId);
        List<PlcTag> tags = new ArrayList<>();

        if (connection == null) {
            return tags;
        }

        // Note: Tag discovery is protocol-specific and may not be supported
        // For OPC UA, we could browse the address space
        // For S7, we could read the symbol table
        // For Modbus, there's no standard discovery mechanism

        // Return example tags for simulated protocol
        PlcConnectionStatus status = connectionStatuses.get(connectionId);
        if (status != null && "simulated".equals(status.getProtocol())) {
            tags.add(PlcTag.builder()
                    .name("temperature")
                    .address("RANDOM/temperature:REAL")
                    .dataType("REAL")
                    .quality(PlcTag.TagQuality.NOT_READ)
                    .build());
            tags.add(PlcTag.builder()
                    .name("pressure")
                    .address("RANDOM/pressure:REAL")
                    .dataType("REAL")
                    .quality(PlcTag.TagQuality.NOT_READ)
                    .build());
            tags.add(PlcTag.builder()
                    .name("counter")
                    .address("RANDOM/counter:INT")
                    .dataType("INT")
                    .quality(PlcTag.TagQuality.NOT_READ)
                    .build());
            tags.add(PlcTag.builder()
                    .name("running")
                    .address("RANDOM/running:BOOL")
                    .dataType("BOOL")
                    .quality(PlcTag.TagQuality.NOT_READ)
                    .build());
        }

        return tags;
    }

    /**
     * Get connection status.
     *
     * @param connectionId Connection identifier
     * @return Connection status or null
     */
    public PlcConnectionStatus getConnectionStatus(String connectionId) {
        return connectionStatuses.get(connectionId);
    }

    /**
     * Get all active connections.
     *
     * @return List of connection statuses
     */
    public List<PlcConnectionStatus> getAllConnections() {
        return new ArrayList<>(connectionStatuses.values());
    }

    /**
     * Check if a connection is active.
     *
     * @param connectionId Connection identifier
     * @return true if connected
     */
    public boolean isConnected(String connectionId) {
        PlcConnection connection = connections.get(connectionId);
        return connection != null && connection.isConnected();
    }

    /**
     * Extract protocol from connection string.
     */
    private String extractProtocol(String connectionString) {
        int colonIndex = connectionString.indexOf(":");
        if (colonIndex > 0) {
            return connectionString.substring(0, colonIndex);
        }
        return "unknown";
    }

    /**
     * Update read statistics.
     */
    private void updateReadStats(String connectionId, boolean success) {
        PlcConnectionStatus status = connectionStatuses.get(connectionId);
        if (status != null) {
            connectionStatuses.put(connectionId, PlcConnectionStatus.builder()
                    .connectionId(connectionId)
                    .connectionString(status.getConnectionString())
                    .name(status.getName())
                    .protocol(status.getProtocol())
                    .state(success ? PlcConnectionStatus.ConnectionState.CONNECTED :
                            PlcConnectionStatus.ConnectionState.ERROR)
                    .connectedAt(status.getConnectedAt())
                    .lastReadAt(Instant.now())
                    .totalReads(status.getTotalReads() + 1)
                    .failedReads(status.getFailedReads() + (success ? 0 : 1))
                    .build());
        }
    }

    /**
     * Clean up connections on shutdown.
     */
    @PreDestroy
    public void cleanup() {
        log.info("Cleaning up PLC connections...");
        connections.keySet().forEach(this::disconnect);
    }
}
