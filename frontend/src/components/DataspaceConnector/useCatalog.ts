/**
 * Hook for browsing dataspace catalogs and negotiating contracts.
 *
 * Provides state management for searching provider catalogs and
 * initiating data transfer negotiations in dataspaces.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  searchCatalog,
  listCatalogProviders,
  addCatalogProvider,
  initiateCatalogNegotiation,
  getNegotiationStatus,
  pollNegotiationStatus,
  type CatalogOffer,
  type CatalogProviderInfo,
  type NegotiationResponse,
} from '../../services/dataspaceApi';

interface UseCatalogOptions {
  /**
   * Connection ID to use for catalog operations.
   */
  connectionId?: string;
  /**
   * Called when a negotiation is finalized.
   */
  onNegotiationComplete?: (negotiation: NegotiationResponse) => void;
  /**
   * Called on errors.
   */
  onError?: (error: string) => void;
}

interface UseCatalogReturn {
  // State
  offers: CatalogOffer[];
  providers: CatalogProviderInfo[];
  activeNegotiation: NegotiationResponse | null;
  isSearching: boolean;
  isLoadingProviders: boolean;
  isNegotiating: boolean;
  error: string | null;
  totalOffers: number;
  hasMoreOffers: boolean;

  // Actions
  search: (
    connectionId: string,
    providerBpn: string,
    options?: {
      semanticId?: string;
      limit?: number;
      offset?: number;
    }
  ) => Promise<void>;
  loadProviders: (connectionId: string) => Promise<void>;
  addProvider: (
    connectionId: string,
    bpn: string,
    protocolAddress: string,
    name?: string
  ) => Promise<CatalogProviderInfo>;
  negotiate: (
    connectionId: string,
    offer: CatalogOffer,
    providerAddress: string
  ) => Promise<NegotiationResponse>;
  refreshNegotiation: (negotiationId: string) => Promise<void>;
  clearOffers: () => void;
  reset: () => void;
}

export function useCatalog(options: UseCatalogOptions = {}): UseCatalogReturn {
  const { onNegotiationComplete, onError } = options;

  // State
  const [offers, setOffers] = useState<CatalogOffer[]>([]);
  const [providers, setProviders] = useState<CatalogProviderInfo[]>([]);
  const [activeNegotiation, setActiveNegotiation] = useState<NegotiationResponse | null>(
    null
  );
  const [isSearching, setIsSearching] = useState(false);
  const [isLoadingProviders, setIsLoadingProviders] = useState(false);
  const [isNegotiating, setIsNegotiating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalOffers, setTotalOffers] = useState(0);
  const [hasMoreOffers, setHasMoreOffers] = useState(false);

  // Polling ref
  const pollingRef = useRef<boolean>(false);

  // Stop polling
  const stopPolling = useCallback(() => {
    pollingRef.current = false;
  }, []);

  // Search catalog
  const search = useCallback(
    async (
      connectionId: string,
      providerBpn: string,
      searchOptions?: {
        semanticId?: string;
        limit?: number;
        offset?: number;
      }
    ) => {
      setIsSearching(true);
      setError(null);

      try {
        const response = await searchCatalog({
          connection_id: connectionId,
          provider_bpn: providerBpn,
          semantic_id: searchOptions?.semanticId,
          limit: searchOptions?.limit ?? 50,
          offset: searchOptions?.offset ?? 0,
        });

        // If offset > 0, append; otherwise replace
        if (searchOptions?.offset && searchOptions.offset > 0) {
          setOffers((prev) => [...prev, ...response.offers]);
        } else {
          setOffers(response.offers);
        }

        setTotalOffers(response.total);
        setHasMoreOffers(response.has_more);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to search catalog';
        setError(message);
        onError?.(message);
      } finally {
        setIsSearching(false);
      }
    },
    [onError]
  );

  // Load providers
  const loadProviders = useCallback(
    async (connectionId: string) => {
      setIsLoadingProviders(true);
      setError(null);

      try {
        const response = await listCatalogProviders(connectionId);
        setProviders(response.providers);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load providers';
        setError(message);
        onError?.(message);
      } finally {
        setIsLoadingProviders(false);
      }
    },
    [onError]
  );

  // Add provider
  const addProvider = useCallback(
    async (
      connectionId: string,
      bpn: string,
      protocolAddress: string,
      name?: string
    ): Promise<CatalogProviderInfo> => {
      setError(null);

      try {
        const provider = await addCatalogProvider(connectionId, bpn, protocolAddress, name);

        // Update providers list
        setProviders((prev) => {
          const existing = prev.findIndex((p) => p.bpn === bpn);
          if (existing >= 0) {
            const updated = [...prev];
            updated[existing] = provider;
            return updated;
          }
          return [...prev, provider];
        });

        return provider;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to add provider';
        setError(message);
        onError?.(message);
        throw err;
      }
    },
    [onError]
  );

  // Negotiate contract
  const negotiate = useCallback(
    async (
      connectionId: string,
      offer: CatalogOffer,
      providerAddress: string
    ): Promise<NegotiationResponse> => {
      setIsNegotiating(true);
      setError(null);

      try {
        const response = await initiateCatalogNegotiation({
          connection_id: connectionId,
          provider_address: providerAddress,
          offer_id: offer.offer_id,
          asset_id: offer.asset_id,
          policy: offer.policy,
        });

        setActiveNegotiation(response);

        // Start polling for negotiation progress
        pollingRef.current = true;
        const finalNegotiation = await pollNegotiationStatus(
          response.negotiation_id,
          (neg) => {
            if (!pollingRef.current) return;
            setActiveNegotiation(neg);
          },
          2000
        );

        stopPolling();
        setIsNegotiating(false);

        if (finalNegotiation.state === 'finalized') {
          onNegotiationComplete?.(finalNegotiation);
        } else if (finalNegotiation.state === 'error') {
          const errMsg = finalNegotiation.error_message || 'Negotiation failed';
          setError(errMsg);
          onError?.(errMsg);
        } else if (finalNegotiation.state === 'terminated') {
          setError('Negotiation was terminated');
          onError?.('Negotiation was terminated');
        }

        return finalNegotiation;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to negotiate';
        setError(message);
        setIsNegotiating(false);
        onError?.(message);
        throw err;
      }
    },
    [onNegotiationComplete, onError, stopPolling]
  );

  // Refresh negotiation status
  const refreshNegotiation = useCallback(
    async (negotiationId: string) => {
      try {
        const negotiation = await getNegotiationStatus(negotiationId);
        setActiveNegotiation(negotiation);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Failed to refresh negotiation';
        setError(message);
      }
    },
    []
  );

  // Clear offers
  const clearOffers = useCallback(() => {
    setOffers([]);
    setTotalOffers(0);
    setHasMoreOffers(false);
  }, []);

  // Reset state
  const reset = useCallback(() => {
    stopPolling();
    setOffers([]);
    setProviders([]);
    setActiveNegotiation(null);
    setIsSearching(false);
    setIsLoadingProviders(false);
    setIsNegotiating(false);
    setError(null);
    setTotalOffers(0);
    setHasMoreOffers(false);
  }, [stopPolling]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      pollingRef.current = false;
    };
  }, []);

  return {
    // State
    offers,
    providers,
    activeNegotiation,
    isSearching,
    isLoadingProviders,
    isNegotiating,
    error,
    totalOffers,
    hasMoreOffers,

    // Actions
    search,
    loadProviders,
    addProvider,
    negotiate,
    refreshNegotiation,
    clearOffers,
    reset,
  };
}
