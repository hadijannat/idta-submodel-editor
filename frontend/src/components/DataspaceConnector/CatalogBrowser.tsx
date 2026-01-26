/**
 * CatalogBrowser - Browse and negotiate dataspace catalog offers.
 *
 * Allows users to search provider catalogs, view available offers,
 * and initiate contract negotiations for data access.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useCatalog } from './useCatalog';
import type {
  CatalogOffer,
  CatalogProviderInfo,
  NegotiationStatus,
} from '../../services/dataspaceApi';

interface CatalogBrowserProps {
  connectionId: string;
  onNegotiationComplete?: (agreementId: string) => void;
  className?: string;
}

const NEGOTIATION_STATUS_CONFIG: Record<
  NegotiationStatus,
  { label: string; color: 'gray' | 'blue' | 'green' | 'yellow' | 'red' }
> = {
  initial: { label: 'Starting', color: 'gray' },
  requesting: { label: 'Requesting', color: 'blue' },
  offered: { label: 'Offered', color: 'blue' },
  agreeing: { label: 'Agreeing', color: 'blue' },
  agreed: { label: 'Agreed', color: 'blue' },
  verifying: { label: 'Verifying', color: 'yellow' },
  verified: { label: 'Verified', color: 'yellow' },
  finalized: { label: 'Finalized', color: 'green' },
  terminated: { label: 'Terminated', color: 'gray' },
  error: { label: 'Error', color: 'red' },
};

export default function CatalogBrowser({
  connectionId,
  onNegotiationComplete,
  className = '',
}: CatalogBrowserProps) {
  // Local state
  const [selectedProvider, setSelectedProvider] = useState<CatalogProviderInfo | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [showAddProvider, setShowAddProvider] = useState(false);
  const [newProviderBpn, setNewProviderBpn] = useState('');
  const [newProviderAddress, setNewProviderAddress] = useState('');
  const [newProviderName, setNewProviderName] = useState('');
  const [selectedOffer, setSelectedOffer] = useState<CatalogOffer | null>(null);

  const {
    offers,
    providers,
    activeNegotiation,
    isSearching,
    isLoadingProviders,
    isNegotiating,
    error,
    totalOffers,
    hasMoreOffers,
    search,
    loadProviders,
    addProvider,
    negotiate,
    clearOffers,
  } = useCatalog({
    connectionId,
    onNegotiationComplete: (neg) => {
      if (neg.agreement_id) {
        onNegotiationComplete?.(neg.agreement_id);
      }
    },
  });

  // Load providers on mount
  useEffect(() => {
    loadProviders(connectionId);
  }, [connectionId, loadProviders]);

  // Filter offers by search
  const filteredOffers = useMemo(() => {
    if (!searchQuery) return offers;

    const query = searchQuery.toLowerCase();
    return offers.filter(
      (o) =>
        o.asset_id.toLowerCase().includes(query) ||
        o.offer_id.toLowerCase().includes(query) ||
        (o.name && o.name.toLowerCase().includes(query)) ||
        (o.description && o.description.toLowerCase().includes(query))
    );
  }, [offers, searchQuery]);

  // Handle provider selection
  const handleProviderSelect = useCallback(
    (provider: CatalogProviderInfo) => {
      setSelectedProvider(provider);
      setSelectedOffer(null);
      clearOffers();
      search(connectionId, provider.bpn);
    },
    [connectionId, search, clearOffers]
  );

  // Handle add provider
  const handleAddProvider = useCallback(async () => {
    if (!newProviderBpn || !newProviderAddress) return;

    try {
      const provider = await addProvider(
        connectionId,
        newProviderBpn,
        newProviderAddress,
        newProviderName || undefined
      );

      // Reset form and select new provider
      setNewProviderBpn('');
      setNewProviderAddress('');
      setNewProviderName('');
      setShowAddProvider(false);
      handleProviderSelect(provider);
    } catch {
      // Error handled by hook
    }
  }, [
    connectionId,
    newProviderBpn,
    newProviderAddress,
    newProviderName,
    addProvider,
    handleProviderSelect,
  ]);

  // Handle negotiate
  const handleNegotiate = useCallback(
    async (offer: CatalogOffer) => {
      if (!selectedProvider) return;

      setSelectedOffer(offer);
      await negotiate(connectionId, offer, selectedProvider.protocol_address);
    },
    [connectionId, selectedProvider, negotiate]
  );

  // Load more offers
  const handleLoadMore = useCallback(() => {
    if (!selectedProvider || isSearching) return;
    search(connectionId, selectedProvider.bpn, { offset: offers.length });
  }, [connectionId, selectedProvider, offers.length, isSearching, search]);

  // Get negotiation status badge
  const getNegotiationBadge = (status: NegotiationStatus) => {
    const config = NEGOTIATION_STATUS_CONFIG[status] || { label: status, color: 'gray' };
    return (
      <span className={`catalog-browser__status catalog-browser__status--${config.color}`}>
        {config.label}
      </span>
    );
  };

  return (
    <div className={`catalog-browser ${className}`}>
      {/* Header */}
      <div className="catalog-browser__header">
        <h3>Catalog Browser</h3>
        <p className="catalog-browser__subtitle">
          Search available data offers from dataspace providers
        </p>
      </div>

      {/* Provider Selection */}
      <div className="catalog-browser__providers">
        <div className="catalog-browser__providers-header">
          <span className="catalog-browser__providers-title">Select Provider</span>
          <button
            type="button"
            className="catalog-browser__btn--link"
            onClick={() => setShowAddProvider(!showAddProvider)}
          >
            {showAddProvider ? 'Cancel' : '+ Add Provider'}
          </button>
        </div>

        {/* Add Provider Form */}
        {showAddProvider && (
          <div className="catalog-browser__add-provider">
            <input
              type="text"
              placeholder="BPN (e.g., BPNL000000000001)"
              value={newProviderBpn}
              onChange={(e) => setNewProviderBpn(e.target.value)}
              className="catalog-browser__input"
            />
            <input
              type="text"
              placeholder="Protocol Address (e.g., https://provider.example.com/api/dsp)"
              value={newProviderAddress}
              onChange={(e) => setNewProviderAddress(e.target.value)}
              className="catalog-browser__input"
            />
            <input
              type="text"
              placeholder="Display Name (optional)"
              value={newProviderName}
              onChange={(e) => setNewProviderName(e.target.value)}
              className="catalog-browser__input"
            />
            <button
              type="button"
              className="catalog-browser__btn--primary"
              onClick={handleAddProvider}
              disabled={!newProviderBpn || !newProviderAddress}
            >
              Add Provider
            </button>
          </div>
        )}

        {/* Provider List */}
        {isLoadingProviders ? (
          <div className="catalog-browser__loading">
            <div className="catalog-browser__spinner" />
            <span>Loading providers...</span>
          </div>
        ) : providers.length === 0 ? (
          <div className="catalog-browser__empty-providers">
            <p>No providers configured</p>
            <p className="catalog-browser__hint">
              Add a provider to start browsing their catalog
            </p>
          </div>
        ) : (
          <div className="catalog-browser__provider-list">
            {providers.map((provider) => (
              <button
                key={provider.bpn}
                type="button"
                className={`catalog-browser__provider ${
                  selectedProvider?.bpn === provider.bpn
                    ? 'catalog-browser__provider--selected'
                    : ''
                }`}
                onClick={() => handleProviderSelect(provider)}
              >
                <span className="catalog-browser__provider-name">
                  {provider.name || provider.bpn}
                </span>
                {provider.name && (
                  <span className="catalog-browser__provider-bpn">{provider.bpn}</span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Catalog Search */}
      {selectedProvider && (
        <div className="catalog-browser__catalog">
          <div className="catalog-browser__search-bar">
            <input
              type="text"
              placeholder="Search offers by asset ID, name, or description..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="catalog-browser__search-input"
            />
            <button
              type="button"
              className="catalog-browser__refresh"
              onClick={() => search(connectionId, selectedProvider.bpn)}
              disabled={isSearching}
              title="Refresh catalog"
            >
              &#x21bb;
            </button>
          </div>

          {/* Error */}
          {error && (
            <div className="catalog-browser__error">
              <span>Error: {error}</span>
              <button onClick={() => search(connectionId, selectedProvider.bpn)}>
                Retry
              </button>
            </div>
          )}

          {/* Loading */}
          {isSearching && offers.length === 0 && (
            <div className="catalog-browser__loading">
              <div className="catalog-browser__spinner" />
              <span>Searching catalog...</span>
            </div>
          )}

          {/* Offers */}
          {!isSearching && filteredOffers.length === 0 && offers.length === 0 && (
            <div className="catalog-browser__empty">
              <span className="catalog-browser__empty-icon">&#128269;</span>
              <p>No offers found in this provider's catalog</p>
            </div>
          )}

          {filteredOffers.length > 0 && (
            <>
              <div className="catalog-browser__offers">
                {filteredOffers.map((offer) => (
                  <div
                    key={offer.offer_id}
                    className={`catalog-browser__offer ${
                      selectedOffer?.offer_id === offer.offer_id
                        ? 'catalog-browser__offer--selected'
                        : ''
                    }`}
                  >
                    <div className="catalog-browser__offer-header">
                      <span className="catalog-browser__offer-name">
                        {offer.name || offer.asset_id}
                      </span>
                      {offer.content_type && (
                        <span className="catalog-browser__offer-type">
                          {offer.content_type}
                        </span>
                      )}
                    </div>

                    {offer.description && (
                      <p className="catalog-browser__offer-desc">{offer.description}</p>
                    )}

                    <div className="catalog-browser__offer-details">
                      <div className="catalog-browser__offer-detail">
                        <span className="catalog-browser__offer-label">Asset ID:</span>
                        <span className="catalog-browser__offer-value">{offer.asset_id}</span>
                      </div>
                      <div className="catalog-browser__offer-detail">
                        <span className="catalog-browser__offer-label">Provider:</span>
                        <span className="catalog-browser__offer-value">
                          {offer.provider_bpn}
                        </span>
                      </div>
                    </div>

                    <div className="catalog-browser__offer-actions">
                      <button
                        type="button"
                        className="catalog-browser__btn--primary"
                        onClick={() => handleNegotiate(offer)}
                        disabled={isNegotiating}
                      >
                        {isNegotiating && selectedOffer?.offer_id === offer.offer_id
                          ? 'Negotiating...'
                          : 'Negotiate Access'}
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {/* Load more */}
              {hasMoreOffers && (
                <div className="catalog-browser__load-more">
                  <button
                    type="button"
                    className="catalog-browser__btn--secondary"
                    onClick={handleLoadMore}
                    disabled={isSearching}
                  >
                    {isSearching ? 'Loading...' : `Load More (${totalOffers - offers.length} remaining)`}
                  </button>
                </div>
              )}

              {/* Summary */}
              <div className="catalog-browser__summary">
                <span>
                  Showing {filteredOffers.length} of {totalOffers} offers
                </span>
              </div>
            </>
          )}
        </div>
      )}

      {/* Active Negotiation */}
      {activeNegotiation && (
        <div className="catalog-browser__negotiation">
          <div className="catalog-browser__negotiation-header">
            <span>Contract Negotiation</span>
            {getNegotiationBadge(activeNegotiation.state)}
          </div>
          <div className="catalog-browser__negotiation-details">
            <div className="catalog-browser__negotiation-detail">
              <span className="catalog-browser__negotiation-label">Negotiation ID:</span>
              <span className="catalog-browser__negotiation-value">
                {activeNegotiation.negotiation_id}
              </span>
            </div>
            {activeNegotiation.agreement_id && (
              <div className="catalog-browser__negotiation-detail">
                <span className="catalog-browser__negotiation-label">Agreement ID:</span>
                <span className="catalog-browser__negotiation-value">
                  {activeNegotiation.agreement_id}
                </span>
              </div>
            )}
            {activeNegotiation.error_message && (
              <div className="catalog-browser__negotiation-error">
                {activeNegotiation.error_message}
              </div>
            )}
          </div>
          {activeNegotiation.state === 'finalized' && activeNegotiation.agreement_id && (
            <div className="catalog-browser__negotiation-success">
              <span className="catalog-browser__success-icon">&#10003;</span>
              <span>Contract negotiation complete. You can now initiate a data transfer.</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
