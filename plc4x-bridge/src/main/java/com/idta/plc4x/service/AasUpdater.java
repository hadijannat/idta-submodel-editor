package com.idta.plc4x.service;

import com.idta.plc4x.config.BasyxConfig;
import com.idta.plc4x.config.MappingConfig;
import com.idta.plc4x.model.TagMapping;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import javax.script.ScriptEngine;
import javax.script.ScriptEngineManager;
import javax.script.ScriptException;
import java.util.*;

/**
 * Service for updating AAS submodel elements via BaSyx Server API.
 *
 * Pushes PLC values to AAS based on configured mappings.
 *
 * Note: The transformation feature uses JavaScript ScriptEngine which internally
 * uses eval-like execution. This is intentional for user-defined transformations
 * like scaling (value * 0.1) or conditionals. Transformations are configured by
 * trusted administrators, not arbitrary user input.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AasUpdater {

    private final WebClient basyxWebClient;
    private final BasyxConfig basyxConfig;
    private final MappingConfig mappingConfig;

    // JavaScript engine for transformations - uses admin-configured expressions only
    private final ScriptEngine scriptEngine = new ScriptEngineManager().getEngineByName("javascript");

    /**
     * Update an AAS submodel element with a PLC value.
     *
     * @param mapping Mapping configuration
     * @param value   Raw value from PLC
     * @return true if update successful
     */
    public boolean updateElement(TagMapping mapping, Object value) {
        if (!mapping.isEnabled()) {
            return false;
        }

        // Check if update is needed based on mode
        if (mapping.getUpdateMode() == TagMapping.UpdateMode.ON_CHANGE) {
            if (!mappingConfig.hasValueChanged(mapping.getId(), value)) {
                log.debug("Value unchanged for mapping {}, skipping update", mapping.getId());
                return true;
            }
        }

        // Apply transformation if configured
        Object transformedValue = value;
        if (mapping.getTransformation() != null && !mapping.getTransformation().isBlank()) {
            transformedValue = applyTransformation(value, mapping.getTransformation());
        }

        // Build the API path
        String path = buildElementPath(mapping);

        log.debug("Updating AAS element: {} with value: {}", path, transformedValue);

        try {
            // Create the value payload for BaSyx
            Map<String, Object> payload = createValuePayload(transformedValue);

            // Send PATCH request to update the element value
            basyxWebClient.patch()
                    .uri(path + "/$value")
                    .contentType(MediaType.APPLICATION_JSON)
                    .bodyValue(payload)
                    .retrieve()
                    .toBodilessEntity()
                    .block();

            // Update last known value
            mappingConfig.updateLastValue(mapping.getId(), value);

            log.debug("Successfully updated AAS element: {}", path);
            return true;

        } catch (WebClientResponseException e) {
            log.error("HTTP error updating AAS element {}: {} - {}",
                    path, e.getStatusCode(), e.getResponseBodyAsString());
            return false;
        } catch (Exception e) {
            log.error("Error updating AAS element {}: {}", path, e.getMessage());
            return false;
        }
    }

    /**
     * Update multiple AAS elements in batch.
     *
     * @param updates Map of mapping to value
     * @return Map of mapping ID to success status
     */
    public Map<String, Boolean> updateElements(Map<TagMapping, Object> updates) {
        Map<String, Boolean> results = new HashMap<>();

        for (Map.Entry<TagMapping, Object> entry : updates.entrySet()) {
            TagMapping mapping = entry.getKey();
            Object value = entry.getValue();
            boolean success = updateElement(mapping, value);
            results.put(mapping.getId(), success);
        }

        return results;
    }

    /**
     * Read current value from AAS element.
     *
     * @param mapping Mapping configuration
     * @return Current value or null
     */
    public Object readElementValue(TagMapping mapping) {
        String path = buildElementPath(mapping);

        try {
            return basyxWebClient.get()
                    .uri(path + "/$value")
                    .retrieve()
                    .bodyToMono(Object.class)
                    .block();
        } catch (Exception e) {
            log.error("Error reading AAS element {}: {}", path, e.getMessage());
            return null;
        }
    }

    /**
     * Check if AAS element exists.
     *
     * @param mapping Mapping configuration
     * @return true if element exists
     */
    public boolean elementExists(TagMapping mapping) {
        String path = buildElementPath(mapping);

        try {
            basyxWebClient.get()
                    .uri(path)
                    .retrieve()
                    .toBodilessEntity()
                    .block();
            return true;
        } catch (WebClientResponseException.NotFound e) {
            return false;
        } catch (Exception e) {
            log.error("Error checking AAS element existence {}: {}", path, e.getMessage());
            return false;
        }
    }

    /**
     * Validate all mappings for a connection.
     *
     * @param connectionId Connection identifier
     * @return Map of mapping ID to validation result
     */
    public Map<String, String> validateMappings(String connectionId) {
        Map<String, String> results = new HashMap<>();

        for (TagMapping mapping : mappingConfig.getMappings(connectionId)) {
            try {
                if (elementExists(mapping)) {
                    results.put(mapping.getId(), "OK");
                } else {
                    results.put(mapping.getId(), "Element not found");
                }
            } catch (Exception e) {
                results.put(mapping.getId(), "Error: " + e.getMessage());
            }
        }

        return results;
    }

    /**
     * Build the BaSyx API path for a submodel element.
     */
    private String buildElementPath(TagMapping mapping) {
        // URL encode shell and submodel IDs (they're typically Base64)
        String shellId = encodeId(mapping.getShellId());
        String submodelId = encodeId(mapping.getSubmodelId());

        // Build path from element path (e.g., "ProductionData/Temperature")
        String elementPath = mapping.getElementPath().replace("/", ".");

        return String.format("/shells/%s/submodels/%s/submodel-elements/%s",
                shellId, submodelId, elementPath);
    }

    /**
     * URL-encode an ID for use in path.
     */
    private String encodeId(String id) {
        // Base64 IDs need to be URL-safe
        return Base64.getUrlEncoder().withoutPadding()
                .encodeToString(id.getBytes());
    }

    /**
     * Create value payload for BaSyx API.
     */
    private Map<String, Object> createValuePayload(Object value) {
        // BaSyx expects the value directly for Property elements
        // For complex types, this might need adjustment
        if (value instanceof Number || value instanceof Boolean || value instanceof String) {
            return Map.of("value", value);
        }

        // For null or complex objects
        Map<String, Object> payload = new HashMap<>();
        payload.put("value", value != null ? value.toString() : "");
        return payload;
    }

    /**
     * Apply transformation expression to value.
     *
     * This uses JavaScript ScriptEngine to execute admin-configured transformation
     * expressions like "value * 0.1" or "value > 100 ? 'HIGH' : 'NORMAL'".
     * Transformations are configured via the mapping API by trusted administrators.
     *
     * @param value      Raw value
     * @param expression JavaScript expression (uses 'value' variable)
     * @return Transformed value
     */
    private Object applyTransformation(Object value, String expression) {
        if (scriptEngine == null) {
            log.warn("JavaScript engine not available, skipping transformation");
            return value;
        }

        try {
            scriptEngine.put("value", value);
            // ScriptEngine.eval executes the configured transformation expression
            Object result = scriptEngine.eval(expression);
            log.debug("Transformation '{}' applied: {} -> {}", expression, value, result);
            return result;
        } catch (ScriptException e) {
            log.error("Error applying transformation '{}' to value {}: {}",
                    expression, value, e.getMessage());
            return value;
        }
    }
}
