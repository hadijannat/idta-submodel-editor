/**
 * PublicationManager - List and manage dataspace publications.
 *
 * Displays all published submodels with status, endpoints, and
 * actions for viewing details or unpublishing.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { usePublications } from './usePublications';
import type {
  SubmodelPublication,
  PublicationStatus,
} from '../../services/dataspaceApi';

interface PublicationManagerProps {
  connectionId: string;
  onPublish?: () => void;
  onSelectPublication?: (publication: SubmodelPublication) => void;
  className?: string;
}

const STATUS_CONFIG: Record<
  PublicationStatus,
  { label: string; color: 'gray' | 'blue' | 'green' | 'yellow' | 'red' }
> = {
  pending: { label: 'Pending', color: 'blue' },
  registering: { label: 'Registering', color: 'blue' },
  publishing: { label: 'Publishing', color: 'blue' },
  published: { label: 'Published', color: 'green' },
  updating: { label: 'Updating', color: 'yellow' },
  unpublishing: { label: 'Unpublishing', color: 'yellow' },
  unpublished: { label: 'Unpublished', color: 'gray' },
  failed: { label: 'Failed', color: 'red' },
};

export default function PublicationManager({
  connectionId,
  onPublish,
  onSelectPublication,
  className = '',
}: PublicationManagerProps) {
  const [filter, setFilter] = useState<'all' | 'published' | 'failed'>('all');
  const [searchQuery, setSearchQuery] = useState('');

  const {
    publications,
    isLoading,
    error,
    loadPublications,
    unpublish,
    refreshPublication,
  } = usePublications({ connectionId });

  // Load publications on mount
  useEffect(() => {
    loadPublications(connectionId);
  }, [connectionId, loadPublications]);

  // Filter publications
  const filteredPublications = useMemo(() => {
    let result = publications;

    // Apply status filter
    if (filter === 'published') {
      result = result.filter((p) => p.status === 'published');
    } else if (filter === 'failed') {
      result = result.filter(
        (p) => p.status === 'failed' || p.status === 'unpublished'
      );
    }

    // Apply search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(
        (p) =>
          p.template_name.toLowerCase().includes(query) ||
          p.submodel_id.toLowerCase().includes(query) ||
          p.publication_id.toLowerCase().includes(query)
      );
    }

    return result;
  }, [publications, filter, searchQuery]);

  // Handle unpublish
  const handleUnpublish = useCallback(
    async (publicationId: string) => {
      if (
        window.confirm(
          'Are you sure you want to unpublish this submodel? This will remove it from the dataspace.'
        )
      ) {
        await unpublish(publicationId);
      }
    },
    [unpublish]
  );

  // Format date
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  // Get status badge
  const getStatusBadge = (status: PublicationStatus) => {
    const config = STATUS_CONFIG[status] || { label: status, color: 'gray' };
    return (
      <span
        className={`dataspace-publication__status dataspace-publication__status--${config.color}`}
      >
        {config.label}
      </span>
    );
  };

  return (
    <div className={`dataspace-publication-manager ${className}`}>
      {/* Header */}
      <div className="dataspace-publication-manager__header">
        <h3>Publications</h3>
        <div className="dataspace-publication-manager__actions">
          <button
            type="button"
            className="dataspace-publication-manager__refresh"
            onClick={() => loadPublications(connectionId)}
            disabled={isLoading}
            title="Refresh publications"
          >
            &#x21bb;
          </button>
          {onPublish && (
            <button
              type="button"
              className="dataspace-publication-manager__btn--primary"
              onClick={onPublish}
            >
              + Publish Submodel
            </button>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="dataspace-publication-manager__filters">
        <div className="dataspace-publication-manager__filter-buttons">
          <button
            type="button"
            className={`dataspace-publication-manager__filter ${
              filter === 'all' ? 'dataspace-publication-manager__filter--active' : ''
            }`}
            onClick={() => setFilter('all')}
          >
            All ({publications.length})
          </button>
          <button
            type="button"
            className={`dataspace-publication-manager__filter ${
              filter === 'published'
                ? 'dataspace-publication-manager__filter--active'
                : ''
            }`}
            onClick={() => setFilter('published')}
          >
            Published ({publications.filter((p) => p.status === 'published').length})
          </button>
          <button
            type="button"
            className={`dataspace-publication-manager__filter ${
              filter === 'failed'
                ? 'dataspace-publication-manager__filter--active'
                : ''
            }`}
            onClick={() => setFilter('failed')}
          >
            Failed/Unpublished (
            {
              publications.filter(
                (p) => p.status === 'failed' || p.status === 'unpublished'
              ).length
            }
            )
          </button>
        </div>
        <div className="dataspace-publication-manager__search">
          <input
            type="text"
            placeholder="Search publications..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="dataspace-publication-manager__error">
          <span>Error: {error}</span>
          <button onClick={() => loadPublications(connectionId)}>Retry</button>
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="dataspace-publication-manager__loading">
          <div className="dataspace-publication-manager__spinner" />
          <span>Loading publications...</span>
        </div>
      )}

      {/* Empty state */}
      {!isLoading && filteredPublications.length === 0 && (
        <div className="dataspace-publication-manager__empty">
          {publications.length === 0 ? (
            <>
              <span className="dataspace-publication-manager__empty-icon">&#128196;</span>
              <p>No publications yet</p>
              <p className="dataspace-publication-manager__empty-hint">
                Publish your first submodel to the dataspace
              </p>
              {onPublish && (
                <button
                  type="button"
                  className="dataspace-publication-manager__btn--primary"
                  onClick={onPublish}
                >
                  + Publish Submodel
                </button>
              )}
            </>
          ) : (
            <>
              <p>No publications match your filters</p>
              <button
                type="button"
                className="dataspace-publication-manager__btn--secondary"
                onClick={() => {
                  setFilter('all');
                  setSearchQuery('');
                }}
              >
                Clear filters
              </button>
            </>
          )}
        </div>
      )}

      {/* Publication list */}
      {!isLoading && filteredPublications.length > 0 && (
        <div className="dataspace-publication-manager__list">
          {filteredPublications.map((publication) => (
            <div
              key={publication.publication_id}
              className="dataspace-publication"
              onClick={() => onSelectPublication?.(publication)}
            >
              <div className="dataspace-publication__header">
                <span className="dataspace-publication__template">
                  {publication.template_name}
                </span>
                {getStatusBadge(publication.status)}
              </div>

              <div className="dataspace-publication__details">
                <div className="dataspace-publication__detail">
                  <span className="dataspace-publication__detail-label">
                    Submodel ID:
                  </span>
                  <span className="dataspace-publication__detail-value">
                    {publication.submodel_id}
                  </span>
                </div>
                {publication.aas_endpoint && (
                  <div className="dataspace-publication__detail">
                    <span className="dataspace-publication__detail-label">
                      AAS Endpoint:
                    </span>
                    <a
                      href={publication.aas_endpoint}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="dataspace-publication__detail-link"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {publication.aas_endpoint}
                    </a>
                  </div>
                )}
                {publication.edc_offer_id && (
                  <div className="dataspace-publication__detail">
                    <span className="dataspace-publication__detail-label">
                      EDC Offer:
                    </span>
                    <span className="dataspace-publication__detail-value">
                      {publication.edc_offer_id}
                    </span>
                  </div>
                )}
                <div className="dataspace-publication__detail">
                  <span className="dataspace-publication__detail-label">Created:</span>
                  <span className="dataspace-publication__detail-value">
                    {formatDate(publication.created_at)}
                  </span>
                </div>
              </div>

              <div className="dataspace-publication__actions">
                <button
                  type="button"
                  className="dataspace-publication__action"
                  onClick={(e) => {
                    e.stopPropagation();
                    refreshPublication(publication.publication_id);
                  }}
                  title="Refresh status"
                >
                  &#x21bb;
                </button>
                {publication.status === 'published' && (
                  <button
                    type="button"
                    className="dataspace-publication__action dataspace-publication__action--danger"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleUnpublish(publication.publication_id);
                    }}
                    title="Unpublish"
                  >
                    &#x2715;
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Summary */}
      {!isLoading && publications.length > 0 && (
        <div className="dataspace-publication-manager__summary">
          <span>
            {filteredPublications.length} of {publications.length} publications
          </span>
        </div>
      )}
    </div>
  );
}
