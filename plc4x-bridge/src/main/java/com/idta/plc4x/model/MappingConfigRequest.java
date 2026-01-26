package com.idta.plc4x.model;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotEmpty;
import lombok.Data;

import java.util.List;

/**
 * Request to configure tag-to-AAS mappings.
 */
@Data
public class MappingConfigRequest {

    /**
     * Connection ID to apply mappings to.
     */
    private String connectionId;

    /**
     * List of tag mappings.
     */
    @NotEmpty(message = "At least one mapping is required")
    @Valid
    private List<TagMapping> mappings;

    /**
     * Whether to replace existing mappings or merge.
     */
    private boolean replaceExisting = false;
}
