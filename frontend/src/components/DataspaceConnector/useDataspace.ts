/**
 * Hook for managing dataspace connection state.
 *
 * Provides state management for connecting to Manufacturing-X / Catena-X
 * dataspaces with polling and error handling.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  createConnection,
  getConnection,
  deleteConnection,
  reconnectConnection,
  pollConnectionStatus,
  getEnvironments,
  getEDCModes,
  type DataspaceConnection,
  type CreateConnectionRequest,
  type HealthCheckResult,
  type EnvironmentInfo,
  type EDCModeInfo,
  type Environment,
  type EDCMode,
} from '../../services/dataspaceApi';

interface UseDataspaceOptions {
  /**
   * Called when connection status changes.
   */
  onStatusChange?: (connection: DataspaceConnection) => void;
  /**
   * Called when connection succeeds.
   */
  onConnected?: (connection: DataspaceConnection) => void;
  /**
   * Called when connection fails.
   */
  onError?: (error: string) => void;
}

interface UseDataspaceReturn {
  // State
  connection: DataspaceConnection | null;
  healthChecks: HealthCheckResult[];
  environments: EnvironmentInfo[];
  edcModes: EDCModeInfo[];
  isConnecting: boolean;
  isLoadingConfig: boolean;
  error: string | null;

  // Selected options
  selectedEnvironment: Environment;
  selectedEDCMode: EDCMode;
  bpn: string;
  credentials: Record<string, string>;

  // Actions
  setSelectedEnvironment: (env: Environment) => void;
  setSelectedEDCMode: (mode: EDCMode) => void;
  setBpn: (bpn: string) => void;
  setCredentials: (creds: Record<string, string>) => void;
  connect: () => Promise<void>;
  disconnect: (force?: boolean, unpublishAll?: boolean) => Promise<void>;
  reconnect: () => Promise<void>;
  refreshStatus: () => Promise<void>;
  loadConfig: () => Promise<void>;
  reset: () => void;
}

export function useDataspace(options: UseDataspaceOptions = {}): UseDataspaceReturn {
  const { onStatusChange, onConnected, onError } = options;

  // Connection state
  const [connection, setConnection] = useState<DataspaceConnection | null>(null);
  const [healthChecks, setHealthChecks] = useState<HealthCheckResult[]>([]);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Configuration state
  const [environments, setEnvironments] = useState<EnvironmentInfo[]>([]);
  const [edcModes, setEDCModes] = useState<EDCModeInfo[]>([]);
  const [isLoadingConfig, setIsLoadingConfig] = useState(false);

  // Form state
  const [selectedEnvironment, setSelectedEnvironment] = useState<Environment>('sandbox');
  const [selectedEDCMode, setSelectedEDCMode] = useState<EDCMode>('tractus-x');
  const [bpn, setBpn] = useState('');
  const [credentials, setCredentials] = useState<Record<string, string>>({});

  // Polling ref
  const pollingRef = useRef<boolean>(false);

  // Stop polling
  const stopPolling = useCallback(() => {
    pollingRef.current = false;
  }, []);

  // Load configuration (environments and EDC modes)
  const loadConfig = useCallback(async () => {
    setIsLoadingConfig(true);
    try {
      const [envs, modes] = await Promise.all([getEnvironments(), getEDCModes()]);
      setEnvironments(envs);
      setEDCModes(modes);

      // Set defaults
      const defaultEnv = envs.find((e) => e.is_default);
      if (defaultEnv) {
        setSelectedEnvironment(defaultEnv.id);
      }
      const defaultMode = modes.find((m) => m.is_default);
      if (defaultMode) {
        setSelectedEDCMode(defaultMode.id);
      }
    } catch (err) {
      console.error('Failed to load dataspace config:', err);
      // Set fallback defaults
      setEnvironments([
        {
          id: 'sandbox',
          name: 'Sandbox',
          description: 'Local development sandbox',
          requires_bpn: false,
          requires_credentials: false,
          is_default: true,
        },
      ]);
      setEDCModes([
        {
          id: 'tractus-x',
          name: 'Tractus-X EDC',
          description: 'Standard Tractus-X EDC connector',
          is_default: true,
        },
      ]);
    } finally {
      setIsLoadingConfig(false);
    }
  }, []);

  // Connect to dataspace
  const connect = useCallback(async () => {
    setIsConnecting(true);
    setError(null);

    try {
      const request: CreateConnectionRequest = {
        environment: selectedEnvironment,
        edc_mode: selectedEDCMode,
        bpn: bpn || undefined,
        credentials: Object.keys(credentials).length > 0 ? credentials : undefined,
      };

      const response = await createConnection(request);
      setConnection(response.connection);
      onStatusChange?.(response.connection);

      // Start polling for connection progress
      pollingRef.current = true;
      pollConnectionStatus(
        response.connection.connection_id,
        (conn) => {
          if (!pollingRef.current) return;
          setConnection(conn);
          onStatusChange?.(conn);

          if (conn.status === 'connected') {
            stopPolling();
            setIsConnecting(false);
            onConnected?.(conn);
          } else if (conn.status === 'failed') {
            stopPolling();
            setIsConnecting(false);
            setError(conn.error_message || 'Connection failed');
            onError?.(conn.error_message || 'Connection failed');
          }
        },
        2000
      ).catch((err) => {
        if (pollingRef.current) {
          setError(err.message);
          setIsConnecting(false);
          onError?.(err.message);
        }
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to connect';
      setError(message);
      setIsConnecting(false);
      onError?.(message);
    }
  }, [
    selectedEnvironment,
    selectedEDCMode,
    bpn,
    credentials,
    onStatusChange,
    onConnected,
    onError,
    stopPolling,
  ]);

  // Disconnect from dataspace
  const disconnect = useCallback(
    async (force = false, unpublishAll = false) => {
      if (!connection) return;

      stopPolling();
      setError(null);

      try {
        await deleteConnection(connection.connection_id, { force, unpublish_all: unpublishAll });
        setConnection(null);
        setHealthChecks([]);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to disconnect';
        setError(message);
        onError?.(message);
      }
    },
    [connection, stopPolling, onError]
  );

  // Reconnect a failed connection
  const reconnect = useCallback(async () => {
    if (!connection) return;

    setIsConnecting(true);
    setError(null);

    try {
      const response = await reconnectConnection(connection.connection_id);
      setConnection(response.connection);
      onStatusChange?.(response.connection);

      // Start polling
      pollingRef.current = true;
      pollConnectionStatus(
        response.connection.connection_id,
        (conn) => {
          if (!pollingRef.current) return;
          setConnection(conn);
          onStatusChange?.(conn);

          if (conn.status === 'connected') {
            stopPolling();
            setIsConnecting(false);
            onConnected?.(conn);
          } else if (conn.status === 'failed') {
            stopPolling();
            setIsConnecting(false);
            setError(conn.error_message || 'Reconnection failed');
            onError?.(conn.error_message || 'Reconnection failed');
          }
        },
        2000
      ).catch((err) => {
        if (pollingRef.current) {
          setError(err.message);
          setIsConnecting(false);
          onError?.(err.message);
        }
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to reconnect';
      setError(message);
      setIsConnecting(false);
      onError?.(message);
    }
  }, [connection, onStatusChange, onConnected, onError, stopPolling]);

  // Refresh connection status
  const refreshStatus = useCallback(async () => {
    if (!connection) return;

    try {
      const response = await getConnection(connection.connection_id);
      setConnection(response.connection);
      setHealthChecks(response.health_checks);
      onStatusChange?.(response.connection);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to refresh status';
      setError(message);
    }
  }, [connection, onStatusChange]);

  // Reset state
  const reset = useCallback(() => {
    stopPolling();
    setConnection(null);
    setHealthChecks([]);
    setIsConnecting(false);
    setError(null);
    setBpn('');
    setCredentials({});
  }, [stopPolling]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      pollingRef.current = false;
    };
  }, []);

  return {
    // State
    connection,
    healthChecks,
    environments,
    edcModes,
    isConnecting,
    isLoadingConfig,
    error,

    // Selected options
    selectedEnvironment,
    selectedEDCMode,
    bpn,
    credentials,

    // Actions
    setSelectedEnvironment,
    setSelectedEDCMode,
    setBpn,
    setCredentials,
    connect,
    disconnect,
    reconnect,
    refreshStatus,
    loadConfig,
    reset,
  };
}
