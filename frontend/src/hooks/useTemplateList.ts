/**
 * Hook for managing template list state.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type { TemplateInfo, TemplateListResponse } from '../types/ui-schema';
import { listTemplates, refreshTemplateCache } from '../services/api';

interface UseTemplateListOptions {
  /** Initial search query */
  initialSearch?: string;
  /** Auto-load on mount */
  autoLoad?: boolean;
  /** Filter by template status */
  status?: 'published' | 'deprecated' | 'all';
}

interface UseTemplateListReturn {
  /** List of templates */
  templates: TemplateInfo[];
  /** Total count */
  total: number;
  /** Whether data is from cache */
  cached: boolean;
  /** Loading state */
  loading: boolean;
  /** Error message if any */
  error: string | null;
  /** Search query */
  search: string;
  /** Update search query */
  setSearch: (search: string) => void;
  /** Reload templates */
  reload: () => Promise<void>;
  /** Force refresh from GitHub */
  refresh: () => Promise<void>;
}

/**
 * Hook for fetching and managing the template list.
 */
export function useTemplateList(
  options: UseTemplateListOptions = {}
): UseTemplateListReturn {
  const { initialSearch = '', autoLoad = true, status } = options;

  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [total, setTotal] = useState(0);
  const [cached, setCached] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState(initialSearch);
  const initialLoadRef = useRef(true);

  const loadTemplates = useCallback(async (searchQuery?: string) => {
    setLoading(true);
    setError(null);

    try {
      const response: TemplateListResponse = await listTemplates(
        searchQuery,
        undefined,
        status
      );
      setTemplates(response.templates);
      setTotal(response.total);
      setCached(response.cached);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load templates';
      setError(message);
      setTemplates([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [status]);

  const reload = useCallback(async () => {
    await loadTemplates(search);
  }, [loadTemplates, search]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      await refreshTemplateCache();
      await loadTemplates(search);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to refresh templates';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [loadTemplates, search]);

  // Load on mount if autoLoad is true
  useEffect(() => {
    if (!autoLoad) return;
    if (!initialLoadRef.current) return;
    initialLoadRef.current = false;
    loadTemplates(search);
  }, [autoLoad, loadTemplates, search]);

  // Debounced search effect
  useEffect(() => {
    if (!autoLoad) return;
    if (initialLoadRef.current) return;
    const timer = setTimeout(() => {
      loadTemplates(search);
    }, 300);

    return () => clearTimeout(timer);
  }, [search, loadTemplates, autoLoad]);

  return {
    templates,
    total,
    cached,
    loading,
    error,
    search,
    setSearch,
    reload,
    refresh,
  };
}

export default useTemplateList;
