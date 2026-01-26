package com.idta.plc4x.controller;

import com.idta.plc4x.config.MappingConfig;
import com.idta.plc4x.model.*;
import com.idta.plc4x.service.AasUpdater;
import com.idta.plc4x.service.ContinuousReader;
import com.idta.plc4x.service.PlcReader;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * REST API controller for PLC4X Bridge operations.
 *
 * Provides endpoints for:
 * - Connecting/disconnecting from PLCs
 * - Discovering and reading PLC tags
 * - Configuring tag-to-AAS mappings
 * - Starting/stopping continuous reading
 */
@Slf4j
@RestController
@RequestMapping("/api/plc")
@RequiredArgsConstructor
@Tag(name = "PLC Bridge", description = "PLC4X to BaSyx AAS Bridge API")
public class PlcController {

    private final PlcReader plcReader;
    private final AasUpdater aasUpdater;
    private final ContinuousReader continuousReader;
    private final MappingConfig mappingConfig;

    // ========================================================================
    // Connection Management
    // ========================================================================

    @PostMapping("/connect")
    @Operation(summary = "Connect to a PLC",
            description = "Establish a connection to a PLC using PLC4X. " +
                    "Supported protocols: modbus-tcp, s7, opcua, simulated")
    public ResponseEntity<PlcConnectionStatus> connect(
            @Valid @RequestBody PlcConnectionRequest request) {

        log.info("Connection request received: {}", request.getConnectionString());
        PlcConnectionStatus status = plcReader.connect(request);

        if (status.getState() == PlcConnectionStatus.ConnectionState.CONNECTED) {
            return ResponseEntity.ok(status);
        } else {
            return ResponseEntity.badRequest().body(status);
        }
    }

    @DeleteMapping("/connections/{connectionId}")
    @Operation(summary = "Disconnect from a PLC")
    public ResponseEntity<Map<String, Object>> disconnect(
            @PathVariable String connectionId) {

        // Stop continuous reading if active
        if (continuousReader.isReading(connectionId)) {
            continuousReader.stopReading(connectionId);
        }

        boolean disconnected = plcReader.disconnect(connectionId);

        return ResponseEntity.ok(Map.of(
                "connectionId", connectionId,
                "disconnected", disconnected
        ));
    }

    @GetMapping("/connections")
    @Operation(summary = "List all PLC connections")
    public ResponseEntity<List<PlcConnectionStatus>> listConnections() {
        return ResponseEntity.ok(plcReader.getAllConnections());
    }

    @GetMapping("/connections/{connectionId}")
    @Operation(summary = "Get connection status")
    public ResponseEntity<PlcConnectionStatus> getConnectionStatus(
            @PathVariable String connectionId) {

        PlcConnectionStatus status = plcReader.getConnectionStatus(connectionId);
        if (status == null) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(status);
    }

    // ========================================================================
    // Tag Discovery and Reading
    // ========================================================================

    @GetMapping("/tags")
    @Operation(summary = "List available tags for a connection",
            description = "Discover available PLC tags. Note: Discovery support varies by protocol.")
    public ResponseEntity<List<PlcTag>> listTags(
            @RequestParam String connectionId) {

        if (!plcReader.isConnected(connectionId)) {
            return ResponseEntity.badRequest().build();
        }

        return ResponseEntity.ok(plcReader.discoverTags(connectionId));
    }

    @PostMapping("/tags/read")
    @Operation(summary = "Read tag values",
            description = "Read one or more tag values from the PLC")
    public ResponseEntity<Map<String, PlcTag>> readTags(
            @RequestParam String connectionId,
            @RequestBody Map<String, String> tagAddresses) {

        if (!plcReader.isConnected(connectionId)) {
            return ResponseEntity.badRequest().build();
        }

        return ResponseEntity.ok(plcReader.readTags(connectionId, tagAddresses));
    }

    // ========================================================================
    // Mapping Configuration
    // ========================================================================

    @PostMapping("/mappings")
    @Operation(summary = "Configure tag-to-AAS mappings",
            description = "Define mappings between PLC tags and AAS submodel elements")
    public ResponseEntity<Map<String, Object>> configureMappings(
            @Valid @RequestBody MappingConfigRequest request) {

        String connectionId = request.getConnectionId();
        if (connectionId == null || connectionId.isBlank()) {
            // Use first active connection if not specified
            List<PlcConnectionStatus> connections = plcReader.getAllConnections();
            if (connections.isEmpty()) {
                return ResponseEntity.badRequest().body(Map.of(
                        "error", "No active connections. Connect to a PLC first."
                ));
            }
            connectionId = connections.get(0).getConnectionId();
        }

        mappingConfig.addMappings(connectionId, request.getMappings(), request.isReplaceExisting());

        return ResponseEntity.ok(Map.of(
                "connectionId", connectionId,
                "mappingsAdded", request.getMappings().size(),
                "totalMappings", mappingConfig.getMappings(connectionId).size()
        ));
    }

    @GetMapping("/mappings")
    @Operation(summary = "Get configured mappings")
    public ResponseEntity<List<TagMapping>> getMappings(
            @RequestParam String connectionId) {

        return ResponseEntity.ok(mappingConfig.getMappings(connectionId));
    }

    @DeleteMapping("/mappings/{mappingId}")
    @Operation(summary = "Delete a mapping")
    public ResponseEntity<Map<String, Object>> deleteMapping(
            @RequestParam String connectionId,
            @PathVariable String mappingId) {

        boolean removed = mappingConfig.removeMapping(connectionId, mappingId);

        return ResponseEntity.ok(Map.of(
                "mappingId", mappingId,
                "removed", removed
        ));
    }

    @PostMapping("/mappings/validate")
    @Operation(summary = "Validate mappings against AAS server",
            description = "Check if all mapped AAS elements exist")
    public ResponseEntity<Map<String, String>> validateMappings(
            @RequestParam String connectionId) {

        return ResponseEntity.ok(aasUpdater.validateMappings(connectionId));
    }

    // ========================================================================
    // Continuous Reading
    // ========================================================================

    @PostMapping("/start")
    @Operation(summary = "Start continuous reading",
            description = "Begin continuous PLC reading and AAS updates based on configured mappings")
    public ResponseEntity<ReadingStatus> startReading(
            @RequestParam String connectionId,
            @RequestParam(required = false, defaultValue = "0") long intervalMs) {

        if (!plcReader.isConnected(connectionId)) {
            return ResponseEntity.badRequest().body(
                    ReadingStatus.builder()
                            .connectionId(connectionId)
                            .running(false)
                            .errors(List.of("PLC not connected"))
                            .build()
            );
        }

        List<TagMapping> mappings = mappingConfig.getEnabledMappings(connectionId);
        if (mappings.isEmpty()) {
            return ResponseEntity.badRequest().body(
                    ReadingStatus.builder()
                            .connectionId(connectionId)
                            .running(false)
                            .errors(List.of("No mappings configured"))
                            .build()
            );
        }

        return ResponseEntity.ok(continuousReader.startReading(connectionId, intervalMs));
    }

    @PostMapping("/stop")
    @Operation(summary = "Stop continuous reading")
    public ResponseEntity<ReadingStatus> stopReading(
            @RequestParam String connectionId) {

        return ResponseEntity.ok(continuousReader.stopReading(connectionId));
    }

    @GetMapping("/status")
    @Operation(summary = "Get reading status")
    public ResponseEntity<ReadingStatus> getReadingStatus(
            @RequestParam String connectionId) {

        return ResponseEntity.ok(continuousReader.getReadingStatus(connectionId));
    }

    @GetMapping("/sessions")
    @Operation(summary = "List active reading sessions")
    public ResponseEntity<List<String>> getActiveSessions() {
        return ResponseEntity.ok(continuousReader.getActiveReadingSessions());
    }

    // ========================================================================
    // Health and Info
    // ========================================================================

    @GetMapping("/health")
    @Operation(summary = "Health check")
    public ResponseEntity<Map<String, Object>> health() {
        List<PlcConnectionStatus> connections = plcReader.getAllConnections();
        long connectedCount = connections.stream()
                .filter(c -> c.getState() == PlcConnectionStatus.ConnectionState.CONNECTED)
                .count();

        return ResponseEntity.ok(Map.of(
                "status", "UP",
                "totalConnections", connections.size(),
                "connectedCount", connectedCount,
                "activeReadingSessions", continuousReader.getActiveReadingSessions().size()
        ));
    }

    @GetMapping("/protocols")
    @Operation(summary = "List supported protocols")
    public ResponseEntity<List<Map<String, String>>> getSupportedProtocols() {
        return ResponseEntity.ok(List.of(
                Map.of(
                        "protocol", "modbus-tcp",
                        "description", "Modbus TCP/IP",
                        "example", "modbus-tcp://192.168.1.100:502"
                ),
                Map.of(
                        "protocol", "s7",
                        "description", "Siemens S7 (S7-300, S7-400, S7-1200, S7-1500)",
                        "example", "s7://192.168.1.100/0/1"
                ),
                Map.of(
                        "protocol", "opcua",
                        "description", "OPC UA",
                        "example", "opcua:tcp://192.168.1.100:4840"
                ),
                Map.of(
                        "protocol", "simulated",
                        "description", "Simulated PLC for testing",
                        "example", "simulated://127.0.0.1"
                )
        ));
    }
}
