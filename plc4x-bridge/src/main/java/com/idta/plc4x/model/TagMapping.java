package com.idta.plc4x.model;

import jakarta.validation.constraints.NotBlank;
import lombok.Data;

/**
 * Mapping between a PLC tag and an AAS submodel element path.
 */
@Data
public class TagMapping {

    /**
     * Unique identifier for this mapping.
     */
    private String id;

    /**
     * PLC tag address.
     */
    @NotBlank(message = "PLC tag address is required")
    private String plcTag;

    /**
     * AAS Shell ID (Base64 encoded).
     */
    @NotBlank(message = "Shell ID is required")
    private String shellId;

    /**
     * AAS Submodel ID (Base64 encoded).
     */
    @NotBlank(message = "Submodel ID is required")
    private String submodelId;

    /**
     * Submodel element idShort path (e.g., "ProductionData/Temperature").
     */
    @NotBlank(message = "Element path is required")
    private String elementPath;

    /**
     * Optional transformation expression.
     * Examples:
     * - "value * 0.1" (scale)
     * - "value > 100 ? 'HIGH' : 'NORMAL'" (conditional)
     */
    private String transformation;

    /**
     * Whether this mapping is enabled.
     */
    private boolean enabled = true;

    /**
     * Update mode for this specific mapping.
     */
    private UpdateMode updateMode;

    /**
     * Description of what this mapping does.
     */
    private String description;

    public enum UpdateMode {
        IMMEDIATE,    // Update AAS immediately on every read
        ON_CHANGE,    // Update AAS only when value changes
        BATCH         // Batch updates together
    }
}
