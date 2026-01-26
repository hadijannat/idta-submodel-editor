package com.idta.plc4x.service;

import com.idta.plc4x.config.MappingConfig;
import com.idta.plc4x.config.PlcConfig;
import com.idta.plc4x.model.PlcTag;
import com.idta.plc4x.model.ReadingStatus;
import com.idta.plc4x.model.TagMapping;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import jakarta.annotation.PreDestroy;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.*;
import java.util.stream.Collectors;

/**
 * Service for continuous PLC reading and AAS updates.
 *
 * Manages scheduled reading tasks that poll PLC values and push them to AAS.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ContinuousReader {

    private final PlcReader plcReader;
    private final AasUpdater aasUpdater;
    private final MappingConfig mappingConfig;
    private final PlcConfig plcConfig;

    /**
     * Executor for continuous reading tasks.
     */
    private final ScheduledExecutorService scheduler = Executors.newScheduledThreadPool(4);

    /**
     * Active reading tasks (connectionId -> future).
     */
    private final Map<String, ScheduledFuture<?>> readingTasks = new ConcurrentHashMap<>();

    /**
     * Reading statistics (connectionId -> status).
     */
    private final Map<String, ReadingStatus.ReadingStatusBuilder> readingStats = new ConcurrentHashMap<>();

    /**
     * Last read values (connectionId -> tag -> value).
     */
    private final Map<String, Map<String, Object>> lastValues = new ConcurrentHashMap<>();

    /**
     * Error buffer (connectionId -> errors).
     */
    private final Map<String, List<String>> errorBuffers = new ConcurrentHashMap<>();

    /**
     * Start continuous reading for a connection.
     *
     * @param connectionId Connection identifier
     * @param intervalMs   Read interval in milliseconds (0 = use default)
     * @return Reading status
     */
    public ReadingStatus startReading(String connectionId, long intervalMs) {
        if (readingTasks.containsKey(connectionId)) {
            log.warn("Reading already active for connection: {}", connectionId);
            return getReadingStatus(connectionId);
        }

        long interval = intervalMs > 0 ? intervalMs : plcConfig.getReadInterval();

        log.info("Starting continuous reading for connection {} with interval {}ms",
                connectionId, interval);

        // Initialize statistics
        ReadingStatus.ReadingStatusBuilder statusBuilder = ReadingStatus.builder()
                .connectionId(connectionId)
                .running(true)
                .startedAt(Instant.now())
                .readIntervalMs(interval)
                .totalCycles(0L)
                .successfulUpdates(0L)
                .failedUpdates(0L);

        readingStats.put(connectionId, statusBuilder);
        lastValues.put(connectionId, new ConcurrentHashMap<>());
        errorBuffers.put(connectionId, Collections.synchronizedList(new ArrayList<>()));

        // Schedule reading task
        ScheduledFuture<?> future = scheduler.scheduleAtFixedRate(
                () -> executeReadCycle(connectionId),
                0,
                interval,
                TimeUnit.MILLISECONDS
        );

        readingTasks.put(connectionId, future);

        return getReadingStatus(connectionId);
    }

    /**
     * Stop continuous reading for a connection.
     *
     * @param connectionId Connection identifier
     * @return Final reading status
     */
    public ReadingStatus stopReading(String connectionId) {
        ScheduledFuture<?> future = readingTasks.remove(connectionId);

        if (future != null) {
            future.cancel(false);
            log.info("Stopped continuous reading for connection: {}", connectionId);

            ReadingStatus.ReadingStatusBuilder statusBuilder = readingStats.get(connectionId);
            if (statusBuilder != null) {
                statusBuilder.running(false);
            }
        }

        return getReadingStatus(connectionId);
    }

    /**
     * Get current reading status.
     *
     * @param connectionId Connection identifier
     * @return Reading status
     */
    public ReadingStatus getReadingStatus(String connectionId) {
        ReadingStatus.ReadingStatusBuilder statusBuilder = readingStats.get(connectionId);

        if (statusBuilder == null) {
            return ReadingStatus.builder()
                    .connectionId(connectionId)
                    .running(false)
                    .build();
        }

        Map<String, Object> values = lastValues.getOrDefault(connectionId, Map.of());
        List<String> errors = errorBuffers.getOrDefault(connectionId, List.of());

        return statusBuilder
                .lastValues(new HashMap<>(values))
                .errors(new ArrayList<>(errors.subList(
                        Math.max(0, errors.size() - 10), errors.size()))) // Last 10 errors
                .build();
    }

    /**
     * Check if reading is active for a connection.
     *
     * @param connectionId Connection identifier
     * @return true if reading is active
     */
    public boolean isReading(String connectionId) {
        ScheduledFuture<?> future = readingTasks.get(connectionId);
        return future != null && !future.isCancelled() && !future.isDone();
    }

    /**
     * Get all active reading sessions.
     *
     * @return List of connection IDs with active reading
     */
    public List<String> getActiveReadingSessions() {
        return readingTasks.entrySet().stream()
                .filter(e -> !e.getValue().isCancelled() && !e.getValue().isDone())
                .map(Map.Entry::getKey)
                .collect(Collectors.toList());
    }

    /**
     * Execute a single read cycle.
     */
    private void executeReadCycle(String connectionId) {
        if (!plcReader.isConnected(connectionId)) {
            addError(connectionId, "PLC not connected");
            return;
        }

        List<TagMapping> mappings = mappingConfig.getEnabledMappings(connectionId);
        if (mappings.isEmpty()) {
            return;
        }

        // Build tag address map from mappings
        Map<String, String> tagAddresses = mappings.stream()
                .collect(Collectors.toMap(
                        TagMapping::getId,
                        TagMapping::getPlcTag,
                        (a, b) -> a
                ));

        // Read all tags
        Map<String, PlcTag> readResults = plcReader.readTags(connectionId, tagAddresses);

        // Update statistics
        ReadingStatus.ReadingStatusBuilder stats = readingStats.get(connectionId);
        if (stats != null) {
            stats.totalCycles(stats.build().getTotalCycles() + 1);
        }

        // Update AAS for each mapping
        for (TagMapping mapping : mappings) {
            PlcTag tag = readResults.get(mapping.getId());

            if (tag == null || tag.getQuality() != PlcTag.TagQuality.GOOD) {
                incrementFailedUpdates(connectionId);
                addError(connectionId, "Failed to read tag: " + mapping.getPlcTag());
                continue;
            }

            // Store last value
            lastValues.computeIfAbsent(connectionId, k -> new ConcurrentHashMap<>())
                    .put(mapping.getPlcTag(), tag.getValue());

            // Update AAS
            try {
                boolean success = aasUpdater.updateElement(mapping, tag.getValue());
                if (success) {
                    incrementSuccessfulUpdates(connectionId);
                } else {
                    incrementFailedUpdates(connectionId);
                }
            } catch (Exception e) {
                incrementFailedUpdates(connectionId);
                addError(connectionId, "Error updating AAS: " + e.getMessage());
            }
        }
    }

    /**
     * Add error to buffer.
     */
    private void addError(String connectionId, String error) {
        List<String> errors = errorBuffers.computeIfAbsent(connectionId,
                k -> Collections.synchronizedList(new ArrayList<>()));

        String timestampedError = Instant.now() + ": " + error;
        errors.add(timestampedError);

        // Keep only last 100 errors
        while (errors.size() > 100) {
            errors.remove(0);
        }
    }

    /**
     * Increment successful updates counter.
     */
    private void incrementSuccessfulUpdates(String connectionId) {
        ReadingStatus.ReadingStatusBuilder stats = readingStats.get(connectionId);
        if (stats != null) {
            ReadingStatus current = stats.build();
            stats.successfulUpdates(current.getSuccessfulUpdates() + 1);
        }
    }

    /**
     * Increment failed updates counter.
     */
    private void incrementFailedUpdates(String connectionId) {
        ReadingStatus.ReadingStatusBuilder stats = readingStats.get(connectionId);
        if (stats != null) {
            ReadingStatus current = stats.build();
            stats.failedUpdates(current.getFailedUpdates() + 1);
        }
    }

    /**
     * Clean up on shutdown.
     */
    @PreDestroy
    public void cleanup() {
        log.info("Shutting down continuous reader...");
        readingTasks.keySet().forEach(this::stopReading);
        scheduler.shutdown();
        try {
            if (!scheduler.awaitTermination(5, TimeUnit.SECONDS)) {
                scheduler.shutdownNow();
            }
        } catch (InterruptedException e) {
            scheduler.shutdownNow();
            Thread.currentThread().interrupt();
        }
    }
}
