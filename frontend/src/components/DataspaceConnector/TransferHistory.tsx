/**
 * TransferHistory - Data transfer history and management component.
 *
 * Displays a list of data transfers with status filtering, progress tracking,
 * and EDR access for completed transfers.
 */

import { useEffect, useState, useCallback } from 'react';
import { useTransfers } from './useTransfers';
import type { Transfer, TransferStatus, TransferEDR } from '../../services/dataspaceApi';
import './DataspaceConnector.css';

interface TransferHistoryProps {
  /**
   * Connection ID to show transfers for.
   */
  connectionId: string;
  /**
   * Called when a transfer is selected.
   */
  onTransferSelect?: (transfer: Transfer) => void;
  /**
   * Called when data access is requested for a completed transfer.
   */
  onAccessData?: (transfer: Transfer, edr: TransferEDR) => void;
}

type StatusFilter = 'all' | 'active' | 'completed' | 'failed';

const STATUS_FILTERS: { id: StatusFilter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'active', label: 'In Progress' },
  { id: 'completed', label: 'Completed' },
  { id: 'failed', label: 'Failed' },
];

function getStatusForFilter(filter: StatusFilter): TransferStatus | undefined {
  switch (filter) {
    case 'completed':
      return 'completed';
    case 'failed':
      return 'error';
    default:
      return undefined;
  }
}

function isActiveStatus(status: TransferStatus): boolean {
  return ['initial', 'provisioning', 'provisioned', 'requesting', 'started'].includes(status);
}

function getStatusBadgeClass(status: TransferStatus): string {
  switch (status) {
    case 'completed':
      return 'transfer-status-badge transfer-status-completed';
    case 'started':
      return 'transfer-status-badge transfer-status-started';
    case 'error':
    case 'terminated':
      return 'transfer-status-badge transfer-status-failed';
    case 'provisioning':
    case 'requesting':
      return 'transfer-status-badge transfer-status-progress';
    default:
      return 'transfer-status-badge transfer-status-pending';
  }
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleString();
}

function formatDuration(startDate: string, endDate: string | null): string {
  const start = new Date(startDate);
  const end = endDate ? new Date(endDate) : new Date();
  const diffMs = end.getTime() - start.getTime();

  if (diffMs < 1000) return '<1s';
  if (diffMs < 60000) return `${Math.round(diffMs / 1000)}s`;
  if (diffMs < 3600000) return `${Math.round(diffMs / 60000)}m`;
  return `${Math.round(diffMs / 3600000)}h`;
}

export function TransferHistory({
  connectionId,
  onTransferSelect,
  onAccessData,
}: TransferHistoryProps) {
  const {
    transfers,
    isLoading,
    error,
    totalTransfers,
    loadTransfers,
    refreshTransfer,
    cancelTransfer,
    fetchEDR,
    reset,
  } = useTransfers({
    connectionId,
    onError: (err) => console.error('Transfer error:', err),
  });

  const [activeFilter, setActiveFilter] = useState<StatusFilter>('all');
  const [selectedTransferId, setSelectedTransferId] = useState<string | null>(null);
  const [loadingEDR, setLoadingEDR] = useState<string | null>(null);

  // Load transfers on mount and when filter changes
  useEffect(() => {
    const status = getStatusForFilter(activeFilter);
    loadTransfers(connectionId, status);
  }, [connectionId, activeFilter, loadTransfers]);

  // Reset on unmount
  useEffect(() => {
    return () => reset();
  }, [reset]);

  // Filter transfers based on active filter
  const filteredTransfers = transfers.filter((transfer) => {
    if (activeFilter === 'active') {
      return isActiveStatus(transfer.state);
    }
    return true;
  });

  // Handle transfer selection
  const handleSelectTransfer = useCallback(
    (transfer: Transfer) => {
      setSelectedTransferId(transfer.transfer_id);
      onTransferSelect?.(transfer);
    },
    [onTransferSelect]
  );

  // Handle access data button
  const handleAccessData = useCallback(
    async (transfer: Transfer) => {
      setLoadingEDR(transfer.transfer_id);
      try {
        const edr = await fetchEDR(transfer.transfer_id);
        if (edr && onAccessData) {
          onAccessData(transfer, edr);
        }
      } finally {
        setLoadingEDR(null);
      }
    },
    [fetchEDR, onAccessData]
  );

  // Handle cancel/terminate
  const handleCancel = useCallback(
    async (transferId: string) => {
      if (window.confirm('Are you sure you want to terminate this transfer?')) {
        await cancelTransfer(transferId);
      }
    },
    [cancelTransfer]
  );

  // Handle refresh
  const handleRefresh = useCallback(() => {
    const status = getStatusForFilter(activeFilter);
    loadTransfers(connectionId, status);
  }, [activeFilter, connectionId, loadTransfers]);

  return (
    <div className="transfer-history">
      <div className="transfer-history-header">
        <h3>Data Transfers</h3>
        <button
          className="transfer-refresh-btn"
          onClick={handleRefresh}
          disabled={isLoading}
        >
          {isLoading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      {/* Status filter tabs */}
      <div className="transfer-filter-tabs">
        {STATUS_FILTERS.map((filter) => (
          <button
            key={filter.id}
            className={`transfer-filter-tab ${activeFilter === filter.id ? 'active' : ''}`}
            onClick={() => setActiveFilter(filter.id)}
          >
            {filter.label}
          </button>
        ))}
      </div>

      {/* Error message */}
      {error && (
        <div className="transfer-error">
          {error}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && filteredTransfers.length === 0 && (
        <div className="transfer-empty">
          <p>No transfers found.</p>
          <p className="transfer-empty-hint">
            {activeFilter === 'all'
              ? 'Negotiate a contract and initiate a transfer to access data from providers.'
              : `No ${activeFilter} transfers.`}
          </p>
        </div>
      )}

      {/* Transfer list */}
      {filteredTransfers.length > 0 && (
        <div className="transfer-list">
          {filteredTransfers.map((transfer) => (
            <div
              key={transfer.transfer_id}
              className={`transfer-item ${
                selectedTransferId === transfer.transfer_id ? 'selected' : ''
              }`}
              onClick={() => handleSelectTransfer(transfer)}
            >
              <div className="transfer-item-header">
                <div className="transfer-item-info">
                  <span className="transfer-asset-id" title={transfer.asset_id}>
                    {transfer.asset_id.length > 40
                      ? `${transfer.asset_id.substring(0, 40)}...`
                      : transfer.asset_id}
                  </span>
                  <span className={getStatusBadgeClass(transfer.state)}>
                    {transfer.state}
                  </span>
                </div>
                <div className="transfer-item-meta">
                  <span className="transfer-provider">
                    From: {transfer.provider_bpn}
                  </span>
                  <span className="transfer-type">{transfer.transfer_type}</span>
                </div>
              </div>

              <div className="transfer-item-details">
                <div className="transfer-timestamps">
                  <span>Created: {formatDate(transfer.created_at)}</span>
                  {transfer.started_at && (
                    <span>
                      Duration: {formatDuration(transfer.started_at, transfer.completed_at)}
                    </span>
                  )}
                </div>

                {/* Progress indicator for active transfers */}
                {isActiveStatus(transfer.state) && (
                  <div className="transfer-progress">
                    <div className="transfer-progress-bar">
                      <div
                        className="transfer-progress-fill"
                        style={{
                          width: transfer.state === 'started' ? '75%' : '25%',
                        }}
                      />
                    </div>
                    <span className="transfer-progress-text">
                      {transfer.state === 'started'
                        ? 'Transferring data...'
                        : 'Preparing transfer...'}
                    </span>
                  </div>
                )}

                {/* Error message */}
                {transfer.error_message && (
                  <div className="transfer-error-message">
                    {transfer.error_message}
                  </div>
                )}

                {/* Actions */}
                <div className="transfer-actions">
                  {/* Access Data button for completed/started transfers */}
                  {(transfer.state === 'completed' || transfer.state === 'started') && (
                    <button
                      className="transfer-action-btn transfer-access-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleAccessData(transfer);
                      }}
                      disabled={loadingEDR === transfer.transfer_id}
                    >
                      {loadingEDR === transfer.transfer_id
                        ? 'Loading...'
                        : 'Access Data'}
                    </button>
                  )}

                  {/* Cancel button for active transfers */}
                  {isActiveStatus(transfer.state) && transfer.state !== 'started' && (
                    <button
                      className="transfer-action-btn transfer-cancel-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleCancel(transfer.transfer_id);
                      }}
                    >
                      Cancel
                    </button>
                  )}

                  {/* Refresh button */}
                  <button
                    className="transfer-action-btn transfer-refresh-action-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      refreshTransfer(transfer.transfer_id);
                    }}
                    title="Refresh status"
                  >
                    Refresh
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Total count */}
      {totalTransfers > 0 && (
        <div className="transfer-total">
          Showing {filteredTransfers.length} of {totalTransfers} transfers
        </div>
      )}
    </div>
  );
}

export default TransferHistory;
