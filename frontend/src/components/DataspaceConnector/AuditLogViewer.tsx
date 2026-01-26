/**
 * AuditLogViewer - Dataspace audit log viewer component.
 *
 * Displays a timeline of dataspace events with filtering by event type,
 * date range, and expandable details.
 */

import { useEffect, useState, useCallback } from 'react';
import { useAuditLog } from './useAuditLog';
import type { AuditEvent, AuditEventType } from '../../services/dataspaceApi';
import './DataspaceConnector.css';

interface AuditLogViewerProps {
  /**
   * Connection ID to show audit logs for.
   */
  connectionId?: string;
  /**
   * Called when an entry is selected.
   */
  onEntrySelect?: (entry: AuditEvent) => void;
}

const EVENT_TYPE_GROUPS: { label: string; types: AuditEventType[] }[] = [
  {
    label: 'Connections',
    types: [
      'connection_created',
      'connection_connected',
      'connection_disconnected',
      'connection_failed',
      'connection_health_check',
    ],
  },
  {
    label: 'Publications',
    types: [
      'publication_started',
      'publication_completed',
      'publication_failed',
      'publication_updated',
      'publication_unpublished',
    ],
  },
  {
    label: 'Catalog',
    types: ['catalog_searched', 'provider_added'],
  },
  {
    label: 'Negotiations',
    types: [
      'negotiation_initiated',
      'negotiation_completed',
      'negotiation_failed',
      'negotiation_terminated',
    ],
  },
  {
    label: 'Transfers',
    types: [
      'transfer_initiated',
      'transfer_started',
      'transfer_completed',
      'transfer_failed',
      'transfer_terminated',
    ],
  },
  {
    label: 'Policies',
    types: ['policy_created', 'policy_updated', 'policy_deleted'],
  },
];

function getEventIcon(eventType: AuditEventType): string {
  if (eventType.includes('created') || eventType.includes('started') || eventType.includes('initiated')) {
    return '+';
  }
  if (eventType.includes('completed') || eventType.includes('connected')) {
    return '✓';
  }
  if (eventType.includes('failed') || eventType.includes('error')) {
    return '✕';
  }
  if (eventType.includes('deleted') || eventType.includes('unpublished') || eventType.includes('terminated') || eventType.includes('disconnected')) {
    return '−';
  }
  if (eventType.includes('updated')) {
    return '↻';
  }
  if (eventType.includes('searched')) {
    return '⌕';
  }
  return '•';
}

function getEventIconClass(eventType: AuditEventType, success: boolean): string {
  if (!success) {
    return 'audit-icon audit-icon-error';
  }
  if (eventType.includes('completed') || eventType.includes('connected')) {
    return 'audit-icon audit-icon-success';
  }
  if (eventType.includes('failed') || eventType.includes('error')) {
    return 'audit-icon audit-icon-error';
  }
  if (eventType.includes('terminated') || eventType.includes('disconnected')) {
    return 'audit-icon audit-icon-warning';
  }
  return 'audit-icon audit-icon-info';
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) {
    return date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
  } else if (diffDays === 1) {
    return `Yesterday ${date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}`;
  } else if (diffDays < 7) {
    return date.toLocaleDateString(undefined, { weekday: 'short', hour: '2-digit', minute: '2-digit' });
  } else {
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  }
}

function formatEventType(eventType: AuditEventType): string {
  return eventType
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

export function AuditLogViewer({ connectionId, onEntrySelect }: AuditLogViewerProps) {
  const {
    entries,
    isLoading,
    error,
    total,
    hasMore,
    filters,
    loadEntries,
    loadMore,
    reset,
  } = useAuditLog({
    connectionId,
    onError: (err) => console.error('Audit log error:', err),
  });

  const [expandedEntryId, setExpandedEntryId] = useState<string | null>(null);
  const [eventTypeFilter, setEventTypeFilter] = useState<AuditEventType | ''>('');

  // Load entries on mount
  useEffect(() => {
    loadEntries();
  }, [loadEntries]);

  // Reset on unmount
  useEffect(() => {
    return () => reset();
  }, [reset]);

  // Handle event type filter change
  const handleEventTypeChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const value = e.target.value as AuditEventType | '';
      setEventTypeFilter(value);
      loadEntries({
        ...filters,
        event_type: value || undefined,
      });
    },
    [filters, loadEntries]
  );

  // Handle entry click
  const handleEntryClick = useCallback(
    (entry: AuditEvent) => {
      if (expandedEntryId === entry.entry_id) {
        setExpandedEntryId(null);
      } else {
        setExpandedEntryId(entry.entry_id);
        onEntrySelect?.(entry);
      }
    },
    [expandedEntryId, onEntrySelect]
  );

  // Handle refresh
  const handleRefresh = useCallback(() => {
    loadEntries();
  }, [loadEntries]);

  return (
    <div className="audit-log-viewer">
      <div className="audit-log-header">
        <h3>Audit Log</h3>
        <button
          className="audit-refresh-btn"
          onClick={handleRefresh}
          disabled={isLoading}
        >
          {isLoading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      {/* Filters */}
      <div className="audit-log-filters">
        <div className="audit-filter-group">
          <label htmlFor="event-type-filter">Event Type:</label>
          <select
            id="event-type-filter"
            value={eventTypeFilter}
            onChange={handleEventTypeChange}
            className="audit-filter-select"
          >
            <option value="">All Events</option>
            {EVENT_TYPE_GROUPS.map((group) => (
              <optgroup key={group.label} label={group.label}>
                {group.types.map((type) => (
                  <option key={type} value={type}>
                    {formatEventType(type)}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>
      </div>

      {/* Error message */}
      {error && <div className="audit-error">{error}</div>}

      {/* Empty state */}
      {!isLoading && entries.length === 0 && (
        <div className="audit-empty">
          <p>No audit events found.</p>
          <p className="audit-empty-hint">
            {eventTypeFilter
              ? 'Try a different event type filter.'
              : 'Events will appear here as you use the dataspace features.'}
          </p>
        </div>
      )}

      {/* Timeline */}
      {entries.length > 0 && (
        <div className="audit-timeline">
          {entries.map((entry) => (
            <div
              key={entry.entry_id}
              className={`audit-entry ${expandedEntryId === entry.entry_id ? 'expanded' : ''}`}
              onClick={() => handleEntryClick(entry)}
            >
              <div className="audit-entry-icon-wrapper">
                <span className={getEventIconClass(entry.event_type, entry.success)}>
                  {getEventIcon(entry.event_type)}
                </span>
                <div className="audit-timeline-line" />
              </div>

              <div className="audit-entry-content">
                <div className="audit-entry-header">
                  <span className="audit-entry-action">{entry.action}</span>
                  <span className="audit-entry-time">{formatTimestamp(entry.timestamp)}</span>
                </div>

                <div className="audit-entry-meta">
                  <span className="audit-event-type">{formatEventType(entry.event_type)}</span>
                  {entry.resource_type && (
                    <span className="audit-resource-type">{entry.resource_type}</span>
                  )}
                  {!entry.success && (
                    <span className="audit-failed-badge">Failed</span>
                  )}
                </div>

                {/* Expanded details */}
                {expandedEntryId === entry.entry_id && (
                  <div className="audit-entry-details">
                    {entry.error_message && (
                      <div className="audit-error-message">
                        {entry.error_message}
                      </div>
                    )}

                    <div className="audit-details-grid">
                      <div className="audit-detail">
                        <span className="audit-detail-label">Entry ID:</span>
                        <span className="audit-detail-value">{entry.entry_id}</span>
                      </div>

                      {entry.resource_id && (
                        <div className="audit-detail">
                          <span className="audit-detail-label">Resource ID:</span>
                          <span className="audit-detail-value">{entry.resource_id}</span>
                        </div>
                      )}

                      {entry.actor && (
                        <div className="audit-detail">
                          <span className="audit-detail-label">Actor:</span>
                          <span className="audit-detail-value">{entry.actor}</span>
                        </div>
                      )}

                      <div className="audit-detail">
                        <span className="audit-detail-label">Timestamp:</span>
                        <span className="audit-detail-value">
                          {new Date(entry.timestamp).toLocaleString()}
                        </span>
                      </div>
                    </div>

                    {Object.keys(entry.details).length > 0 && (
                      <div className="audit-extra-details">
                        <span className="audit-detail-label">Additional Details:</span>
                        <pre className="audit-json">
                          {JSON.stringify(entry.details, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Load more */}
      {hasMore && (
        <div className="audit-load-more">
          <button
            className="audit-load-more-btn"
            onClick={loadMore}
            disabled={isLoading}
          >
            {isLoading ? 'Loading...' : 'Load More'}
          </button>
        </div>
      )}

      {/* Total count */}
      {total > 0 && (
        <div className="audit-total">
          Showing {entries.length} of {total} events
        </div>
      )}
    </div>
  );
}

export default AuditLogViewer;
