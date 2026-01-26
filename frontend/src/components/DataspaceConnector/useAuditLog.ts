/**
 * Hook for viewing dataspace audit logs.
 *
 * Provides state management for fetching and filtering audit log entries.
 */

import { useState, useCallback } from 'react';
import {
  listAuditLogs,
  getAuditEntry,
  type AuditEvent,
  type AuditFilters,
} from '../../services/dataspaceApi';

interface UseAuditLogOptions {
  /**
   * Connection ID to filter by.
   */
  connectionId?: string;
  /**
   * Called on errors.
   */
  onError?: (error: string) => void;
}

interface UseAuditLogReturn {
  // State
  entries: AuditEvent[];
  selectedEntry: AuditEvent | null;
  isLoading: boolean;
  error: string | null;
  total: number;
  hasMore: boolean;
  filters: AuditFilters;

  // Actions
  loadEntries: (filters?: AuditFilters) => Promise<void>;
  loadMore: () => Promise<void>;
  selectEntry: (entryId: string) => Promise<void>;
  setFilters: (filters: Partial<AuditFilters>) => void;
  reset: () => void;
}

const DEFAULT_LIMIT = 50;

export function useAuditLog(options: UseAuditLogOptions = {}): UseAuditLogReturn {
  const { connectionId: defaultConnectionId, onError } = options;

  // State
  const [entries, setEntries] = useState<AuditEvent[]>([]);
  const [selectedEntry, setSelectedEntry] = useState<AuditEvent | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [filters, setFiltersState] = useState<AuditFilters>({
    connection_id: defaultConnectionId,
    limit: DEFAULT_LIMIT,
    offset: 0,
  });

  // Load entries
  const loadEntries = useCallback(
    async (newFilters?: AuditFilters) => {
      setIsLoading(true);
      setError(null);

      const activeFilters = {
        ...filters,
        ...newFilters,
        connection_id: newFilters?.connection_id ?? defaultConnectionId,
        offset: 0, // Reset offset when loading fresh
      };

      try {
        const response = await listAuditLogs(activeFilters);
        setEntries(response.entries);
        setTotal(response.total);
        setHasMore(response.has_more);
        setFiltersState(activeFilters);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load audit logs';
        setError(message);
        onError?.(message);
      } finally {
        setIsLoading(false);
      }
    },
    [defaultConnectionId, filters, onError]
  );

  // Load more entries (pagination)
  const loadMore = useCallback(async () => {
    if (isLoading || !hasMore) return;

    setIsLoading(true);
    setError(null);

    const newOffset = (filters.offset ?? 0) + (filters.limit ?? DEFAULT_LIMIT);
    const activeFilters = {
      ...filters,
      offset: newOffset,
    };

    try {
      const response = await listAuditLogs(activeFilters);
      setEntries((prev) => [...prev, ...response.entries]);
      setTotal(response.total);
      setHasMore(response.has_more);
      setFiltersState(activeFilters);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load more entries';
      setError(message);
      onError?.(message);
    } finally {
      setIsLoading(false);
    }
  }, [filters, hasMore, isLoading, onError]);

  // Select a specific entry
  const selectEntry = useCallback(
    async (entryId: string) => {
      try {
        const entry = await getAuditEntry(entryId);
        setSelectedEntry(entry);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load entry';
        setError(message);
        onError?.(message);
      }
    },
    [onError]
  );

  // Update filters
  const setFilters = useCallback((newFilters: Partial<AuditFilters>) => {
    setFiltersState((prev) => ({
      ...prev,
      ...newFilters,
      offset: 0, // Reset offset when filters change
    }));
  }, []);

  // Reset state
  const reset = useCallback(() => {
    setEntries([]);
    setSelectedEntry(null);
    setIsLoading(false);
    setError(null);
    setTotal(0);
    setHasMore(false);
    setFiltersState({
      connection_id: defaultConnectionId,
      limit: DEFAULT_LIMIT,
      offset: 0,
    });
  }, [defaultConnectionId]);

  return {
    // State
    entries,
    selectedEntry,
    isLoading,
    error,
    total,
    hasMore,
    filters,

    // Actions
    loadEntries,
    loadMore,
    selectEntry,
    setFilters,
    reset,
  };
}
