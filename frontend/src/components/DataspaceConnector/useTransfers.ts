/**
 * Hook for managing dataspace data transfers.
 *
 * Provides state management for initiating transfers, tracking progress,
 * and accessing transferred data via EDR.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  listTransfers,
  getTransfer,
  initiateTransfer,
  terminateTransfer,
  getTransferEDR,
  pollTransferStatus,
  type Transfer,
  type TransferStatus,
  type TransferEDR,
  type InitiateTransferRequest,
} from '../../services/dataspaceApi';

interface UseTransfersOptions {
  /**
   * Connection ID to filter transfers by.
   */
  connectionId?: string;
  /**
   * Called when a transfer completes.
   */
  onTransferComplete?: (transfer: Transfer) => void;
  /**
   * Called on errors.
   */
  onError?: (error: string) => void;
}

interface UseTransfersReturn {
  // State
  transfers: Transfer[];
  activeTransfer: Transfer | null;
  activeEDR: TransferEDR | null;
  isLoading: boolean;
  isInitiating: boolean;
  error: string | null;
  totalTransfers: number;

  // Actions
  loadTransfers: (
    connectionId?: string,
    status?: TransferStatus,
    limit?: number
  ) => Promise<void>;
  startTransfer: (request: InitiateTransferRequest) => Promise<Transfer>;
  refreshTransfer: (transferId: string) => Promise<void>;
  cancelTransfer: (transferId: string) => Promise<void>;
  fetchEDR: (transferId: string) => Promise<TransferEDR | null>;
  reset: () => void;
}

export function useTransfers(options: UseTransfersOptions = {}): UseTransfersReturn {
  const { connectionId: defaultConnectionId, onTransferComplete, onError } = options;

  // State
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [activeTransfer, setActiveTransfer] = useState<Transfer | null>(null);
  const [activeEDR, setActiveEDR] = useState<TransferEDR | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isInitiating, setIsInitiating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalTransfers, setTotalTransfers] = useState(0);

  // Polling ref
  const pollingRef = useRef<boolean>(false);

  // Stop polling
  const stopPolling = useCallback(() => {
    pollingRef.current = false;
  }, []);

  // Load transfers
  const loadTransfers = useCallback(
    async (
      connectionId?: string,
      status?: TransferStatus,
      limit: number = 50
    ) => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await listTransfers(
          connectionId || defaultConnectionId,
          status,
          limit
        );
        setTransfers(response.transfers);
        setTotalTransfers(response.total);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load transfers';
        setError(message);
        onError?.(message);
      } finally {
        setIsLoading(false);
      }
    },
    [defaultConnectionId, onError]
  );

  // Start transfer
  const startTransfer = useCallback(
    async (request: InitiateTransferRequest): Promise<Transfer> => {
      setIsInitiating(true);
      setError(null);

      try {
        const response = await initiateTransfer(request);
        const transfer = response.transfer;

        // Add to transfers list
        setTransfers((prev) => [transfer, ...prev]);
        setTotalTransfers((prev) => prev + 1);
        setActiveTransfer(transfer);

        // Start polling for transfer progress
        pollingRef.current = true;
        const finalTransfer = await pollTransferStatus(
          transfer.transfer_id,
          (t) => {
            if (!pollingRef.current) return;
            setActiveTransfer(t);
            // Update in list
            setTransfers((prev) =>
              prev.map((existing) =>
                existing.transfer_id === t.transfer_id ? t : existing
              )
            );
          },
          2000
        );

        stopPolling();
        setIsInitiating(false);

        if (finalTransfer.state === 'completed' || finalTransfer.state === 'started') {
          onTransferComplete?.(finalTransfer);
        } else if (finalTransfer.state === 'error') {
          const errMsg = finalTransfer.error_message || 'Transfer failed';
          setError(errMsg);
          onError?.(errMsg);
        } else if (finalTransfer.state === 'terminated') {
          setError('Transfer was terminated');
          onError?.('Transfer was terminated');
        }

        return finalTransfer;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to start transfer';
        setError(message);
        setIsInitiating(false);
        onError?.(message);
        throw err;
      }
    },
    [onTransferComplete, onError, stopPolling]
  );

  // Refresh transfer status
  const refreshTransfer = useCallback(async (transferId: string) => {
    try {
      const transfer = await getTransfer(transferId);
      setActiveTransfer(transfer);
      // Update in list
      setTransfers((prev) =>
        prev.map((existing) =>
          existing.transfer_id === transferId ? transfer : existing
        )
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to refresh transfer';
      setError(message);
    }
  }, []);

  // Cancel/terminate transfer
  const cancelTransfer = useCallback(
    async (transferId: string) => {
      try {
        const transfer = await terminateTransfer(transferId);
        setActiveTransfer(transfer);
        // Update in list
        setTransfers((prev) =>
          prev.map((existing) =>
            existing.transfer_id === transferId ? transfer : existing
          )
        );
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to terminate transfer';
        setError(message);
        onError?.(message);
      }
    },
    [onError]
  );

  // Fetch EDR for accessing data
  const fetchEDR = useCallback(
    async (transferId: string): Promise<TransferEDR | null> => {
      try {
        const response = await getTransferEDR(transferId);
        if (response.valid) {
          setActiveEDR(response.edr);
          return response.edr;
        } else {
          setError('EDR has expired');
          return null;
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to get EDR';
        setError(message);
        onError?.(message);
        return null;
      }
    },
    [onError]
  );

  // Reset state
  const reset = useCallback(() => {
    stopPolling();
    setTransfers([]);
    setActiveTransfer(null);
    setActiveEDR(null);
    setIsLoading(false);
    setIsInitiating(false);
    setError(null);
    setTotalTransfers(0);
  }, [stopPolling]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      pollingRef.current = false;
    };
  }, []);

  return {
    // State
    transfers,
    activeTransfer,
    activeEDR,
    isLoading,
    isInitiating,
    error,
    totalTransfers,

    // Actions
    loadTransfers,
    startTransfer,
    refreshTransfer,
    cancelTransfer,
    fetchEDR,
    reset,
  };
}
