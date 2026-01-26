package com.idta.plc4x.model;

import lombok.Builder;
import lombok.Data;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/**
 * Status of continuous reading operation.
 */
@Data
@Builder
public class ReadingStatus {

    private String connectionId;
    private boolean running;
    private Instant startedAt;
    private Long readIntervalMs;
    private Long totalCycles;
    private Long successfulUpdates;
    private Long failedUpdates;
    private Map<String, Object> lastValues;
    private List<String> errors;
}
