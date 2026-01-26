package com.idta.plc4x.config;

import com.idta.plc4x.model.TagMapping;
import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Configuration for PLC tag to AAS element mappings.
 * Manages the mapping registry and provides lookup functionality.
 */
@Data
@Configuration
@ConfigurationProperties(prefix = "mapping")
public class MappingConfig {

    /**
     * Path to external mapping configuration file.
     */
    private String configFile;

    /**
     * Default update mode for mappings.
     */
    private TagMapping.UpdateMode updateMode = TagMapping.UpdateMode.ON_CHANGE;

    /**
     * Batch size for BATCH update mode.
     */
    private int batchSize = 10;

    /**
     * Change threshold percentage for ON_CHANGE mode.
     */
    private double changeThreshold = 0.01;

    /**
     * In-memory mapping storage (connectionId -> list of mappings).
     */
    private final Map<String, List<TagMapping>> mappingsByConnection = new ConcurrentHashMap<>();

    /**
     * Last known values for change detection (mappingId -> value).
     */
    private final Map<String, Object> lastValues = new ConcurrentHashMap<>();

    /**
     * Add mappings for a connection.
     *
     * @param connectionId Connection identifier
     * @param mappings     List of tag mappings
     * @param replace      Whether to replace existing mappings
     */
    public void addMappings(String connectionId, List<TagMapping> mappings, boolean replace) {
        // Assign IDs to mappings that don't have them
        mappings.forEach(m -> {
            if (m.getId() == null || m.getId().isBlank()) {
                m.setId(UUID.randomUUID().toString());
            }
            // Apply default update mode if not specified
            if (m.getUpdateMode() == null) {
                m.setUpdateMode(updateMode);
            }
        });

        if (replace) {
            mappingsByConnection.put(connectionId, new ArrayList<>(mappings));
        } else {
            mappingsByConnection.computeIfAbsent(connectionId, k -> new ArrayList<>())
                    .addAll(mappings);
        }
    }

    /**
     * Get all mappings for a connection.
     *
     * @param connectionId Connection identifier
     * @return List of mappings
     */
    public List<TagMapping> getMappings(String connectionId) {
        return mappingsByConnection.getOrDefault(connectionId, List.of());
    }

    /**
     * Get enabled mappings for a connection.
     *
     * @param connectionId Connection identifier
     * @return List of enabled mappings
     */
    public List<TagMapping> getEnabledMappings(String connectionId) {
        return getMappings(connectionId).stream()
                .filter(TagMapping::isEnabled)
                .toList();
    }

    /**
     * Remove a specific mapping.
     *
     * @param connectionId Connection identifier
     * @param mappingId    Mapping identifier
     * @return true if removed
     */
    public boolean removeMapping(String connectionId, String mappingId) {
        List<TagMapping> mappings = mappingsByConnection.get(connectionId);
        if (mappings != null) {
            return mappings.removeIf(m -> m.getId().equals(mappingId));
        }
        return false;
    }

    /**
     * Clear all mappings for a connection.
     *
     * @param connectionId Connection identifier
     */
    public void clearMappings(String connectionId) {
        mappingsByConnection.remove(connectionId);
    }

    /**
     * Check if value has changed significantly (for ON_CHANGE mode).
     *
     * @param mappingId Mapping identifier
     * @param newValue  New value
     * @return true if value changed beyond threshold
     */
    public boolean hasValueChanged(String mappingId, Object newValue) {
        Object lastValue = lastValues.get(mappingId);
        if (lastValue == null) {
            return true;
        }

        if (newValue == null) {
            return lastValue != null;
        }

        // For numeric types, check threshold
        if (newValue instanceof Number && lastValue instanceof Number) {
            double newNum = ((Number) newValue).doubleValue();
            double lastNum = ((Number) lastValue).doubleValue();
            if (lastNum == 0) {
                return newNum != 0;
            }
            double change = Math.abs((newNum - lastNum) / lastNum);
            return change > changeThreshold;
        }

        // For other types, use equals
        return !newValue.equals(lastValue);
    }

    /**
     * Update last known value for a mapping.
     *
     * @param mappingId Mapping identifier
     * @param value     Current value
     */
    public void updateLastValue(String mappingId, Object value) {
        lastValues.put(mappingId, value);
    }

    /**
     * Get a specific mapping by ID.
     *
     * @param connectionId Connection identifier
     * @param mappingId    Mapping identifier
     * @return Optional mapping
     */
    public Optional<TagMapping> getMapping(String connectionId, String mappingId) {
        return getMappings(connectionId).stream()
                .filter(m -> m.getId().equals(mappingId))
                .findFirst();
    }
}
