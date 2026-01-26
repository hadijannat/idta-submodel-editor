/**
 * Tests for useDataspace hook.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useDataspace } from '../useDataspace';
import * as dataspaceApi from '../../../services/dataspaceApi';

// Mock the dataspace API
vi.mock('../../../services/dataspaceApi', () => ({
  createConnection: vi.fn(),
  getConnection: vi.fn(),
  deleteConnection: vi.fn(),
  reconnectConnection: vi.fn(),
  pollConnectionStatus: vi.fn(),
  getEnvironments: vi.fn(),
  getEDCModes: vi.fn(),
}));

const mockEnvironments: dataspaceApi.EnvironmentInfo[] = [
  {
    id: 'sandbox',
    name: 'Sandbox',
    description: 'Local development sandbox',
    requires_bpn: false,
    requires_credentials: false,
    is_default: true,
  },
  {
    id: 'catena-x-test',
    name: 'Catena-X Test',
    description: 'Test environment',
    requires_bpn: true,
    requires_credentials: true,
    is_default: false,
  },
];

const mockEDCModes: dataspaceApi.EDCModeInfo[] = [
  {
    id: 'tractus-x',
    name: 'Tractus-X EDC',
    description: 'Standard Tractus-X EDC connector',
    is_default: true,
  },
  {
    id: 'aas-extension',
    name: 'AAS Extension',
    description: 'AAS Extension mode',
    is_default: false,
  },
];

const mockConnection: dataspaceApi.DataspaceConnection = {
  connection_id: 'conn-123',
  status: 'connected',
  environment: 'sandbox',
  edc_mode: 'tractus-x',
  bpn: null,
  basyx_url: 'http://basyx:8081',
  dtr_url: 'http://dtr:8082',
  edc_control_url: 'http://edc:8083',
  edc_data_url: 'http://edc:8084',
  progress: 100,
  progress_message: 'Connected',
  error_message: null,
  last_health_check: '2024-01-01T00:00:00Z',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

describe('useDataspace hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('loadConfig', () => {
    it('should load environments and EDC modes successfully', async () => {
      vi.mocked(dataspaceApi.getEnvironments).mockResolvedValue(mockEnvironments);
      vi.mocked(dataspaceApi.getEDCModes).mockResolvedValue(mockEDCModes);

      const { result } = renderHook(() => useDataspace());

      expect(result.current.isLoadingConfig).toBe(false);
      expect(result.current.environments).toEqual([]);

      await act(async () => {
        await result.current.loadConfig();
      });

      expect(result.current.environments).toEqual(mockEnvironments);
      expect(result.current.edcModes).toEqual(mockEDCModes);
      expect(result.current.selectedEnvironment).toBe('sandbox');
      expect(result.current.selectedEDCMode).toBe('tractus-x');
    });

    it('should use fallback defaults on config load failure', async () => {
      vi.mocked(dataspaceApi.getEnvironments).mockRejectedValue(new Error('Network error'));
      vi.mocked(dataspaceApi.getEDCModes).mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useDataspace());

      await act(async () => {
        await result.current.loadConfig();
      });

      expect(result.current.environments).toHaveLength(1);
      expect(result.current.environments[0].id).toBe('sandbox');
      expect(result.current.edcModes).toHaveLength(1);
      expect(result.current.edcModes[0].id).toBe('tractus-x');
    });
  });

  describe('connect', () => {
    it('should create connection and start polling', async () => {
      vi.mocked(dataspaceApi.createConnection).mockResolvedValue({
        connection: { ...mockConnection, status: 'configuring_edc' },
        message: 'Connection initiated',
      });
      // Mock pollConnectionStatus to resolve immediately
      vi.mocked(dataspaceApi.pollConnectionStatus).mockImplementation(
        async (_id, onProgress) => {
          onProgress(mockConnection);
          return mockConnection;
        }
      );

      const onConnected = vi.fn();
      const { result } = renderHook(() => useDataspace({ onConnected }));

      await act(async () => {
        await result.current.connect();
      });

      expect(dataspaceApi.createConnection).toHaveBeenCalledWith({
        environment: 'sandbox',
        edc_mode: 'tractus-x',
        bpn: undefined,
        credentials: undefined,
      });
      expect(dataspaceApi.pollConnectionStatus).toHaveBeenCalled();
    });

    it('should handle connection failure', async () => {
      vi.mocked(dataspaceApi.createConnection).mockRejectedValue(
        new Error('Connection refused')
      );

      const onError = vi.fn();
      const { result } = renderHook(() => useDataspace({ onError }));

      await act(async () => {
        await result.current.connect();
      });

      expect(result.current.isConnecting).toBe(false);
      expect(result.current.error).toBe('Connection refused');
      expect(onError).toHaveBeenCalledWith('Connection refused');
    });

    it('should include BPN and credentials when provided', async () => {
      vi.mocked(dataspaceApi.createConnection).mockResolvedValue({
        connection: mockConnection,
        message: 'Connection initiated',
      });
      vi.mocked(dataspaceApi.pollConnectionStatus).mockImplementation(
        async (_id, onProgress) => {
          onProgress(mockConnection);
          return mockConnection;
        }
      );

      const { result } = renderHook(() => useDataspace());

      act(() => {
        result.current.setSelectedEnvironment('catena-x-test');
        result.current.setBpn('BPNL000000001234');
        result.current.setCredentials({ client_id: 'test', client_secret: 'secret' });
      });

      await act(async () => {
        await result.current.connect();
      });

      expect(dataspaceApi.createConnection).toHaveBeenCalledWith({
        environment: 'catena-x-test',
        edc_mode: 'tractus-x',
        bpn: 'BPNL000000001234',
        credentials: { client_id: 'test', client_secret: 'secret' },
      });
    });

    it('should call onConnected when connection succeeds', async () => {
      vi.mocked(dataspaceApi.createConnection).mockResolvedValue({
        connection: { ...mockConnection, status: 'configuring_edc' },
        message: 'Connection initiated',
      });
      vi.mocked(dataspaceApi.pollConnectionStatus).mockImplementation(
        async (_id, onProgress) => {
          onProgress(mockConnection);
          return mockConnection;
        }
      );

      const onConnected = vi.fn();
      const { result } = renderHook(() => useDataspace({ onConnected }));

      await act(async () => {
        await result.current.connect();
      });

      // Allow microtasks to complete
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });

      expect(onConnected).toHaveBeenCalledWith(mockConnection);
    });
  });

  describe('disconnect', () => {
    it('should disconnect from dataspace', async () => {
      vi.mocked(dataspaceApi.createConnection).mockResolvedValue({
        connection: mockConnection,
        message: 'Connected',
      });
      vi.mocked(dataspaceApi.pollConnectionStatus).mockImplementation(
        async (_id, onProgress) => {
          onProgress(mockConnection);
          return mockConnection;
        }
      );
      vi.mocked(dataspaceApi.deleteConnection).mockResolvedValue({
        connection_id: 'conn-123',
        status: 'disconnected',
        unpublished_count: 0,
        message: 'Disconnected',
      });

      const { result } = renderHook(() => useDataspace());

      // First connect
      await act(async () => {
        await result.current.connect();
      });

      // Allow state to settle
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });

      expect(result.current.connection).not.toBeNull();

      // Then disconnect
      await act(async () => {
        await result.current.disconnect();
      });

      expect(dataspaceApi.deleteConnection).toHaveBeenCalledWith('conn-123', {
        force: false,
        unpublish_all: false,
      });
      expect(result.current.connection).toBeNull();
    });

    it('should handle disconnect with unpublish_all flag', async () => {
      vi.mocked(dataspaceApi.createConnection).mockResolvedValue({
        connection: mockConnection,
        message: 'Connected',
      });
      vi.mocked(dataspaceApi.pollConnectionStatus).mockImplementation(
        async (_id, onProgress) => {
          onProgress(mockConnection);
          return mockConnection;
        }
      );
      vi.mocked(dataspaceApi.deleteConnection).mockResolvedValue({
        connection_id: 'conn-123',
        status: 'disconnected',
        unpublished_count: 3,
        message: 'Disconnected',
      });

      const { result } = renderHook(() => useDataspace());

      await act(async () => {
        await result.current.connect();
      });

      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });

      await act(async () => {
        await result.current.disconnect(true, true);
      });

      expect(dataspaceApi.deleteConnection).toHaveBeenCalledWith('conn-123', {
        force: true,
        unpublish_all: true,
      });
    });

    it('should handle disconnect error', async () => {
      vi.mocked(dataspaceApi.createConnection).mockResolvedValue({
        connection: mockConnection,
        message: 'Connected',
      });
      vi.mocked(dataspaceApi.pollConnectionStatus).mockImplementation(
        async (_id, onProgress) => {
          onProgress(mockConnection);
          return mockConnection;
        }
      );
      vi.mocked(dataspaceApi.deleteConnection).mockRejectedValue(
        new Error('Disconnect failed')
      );

      const onError = vi.fn();
      const { result } = renderHook(() => useDataspace({ onError }));

      await act(async () => {
        await result.current.connect();
      });

      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });

      await act(async () => {
        await result.current.disconnect();
      });

      expect(result.current.error).toBe('Disconnect failed');
      expect(onError).toHaveBeenCalledWith('Disconnect failed');
    });
  });

  describe('state management', () => {
    it('should update selected environment', () => {
      const { result } = renderHook(() => useDataspace());

      expect(result.current.selectedEnvironment).toBe('sandbox');

      act(() => {
        result.current.setSelectedEnvironment('catena-x-prod');
      });

      expect(result.current.selectedEnvironment).toBe('catena-x-prod');
    });

    it('should update selected EDC mode', () => {
      const { result } = renderHook(() => useDataspace());

      expect(result.current.selectedEDCMode).toBe('tractus-x');

      act(() => {
        result.current.setSelectedEDCMode('aas-extension');
      });

      expect(result.current.selectedEDCMode).toBe('aas-extension');
    });

    it('should update BPN', () => {
      const { result } = renderHook(() => useDataspace());

      expect(result.current.bpn).toBe('');

      act(() => {
        result.current.setBpn('BPNL000000001234');
      });

      expect(result.current.bpn).toBe('BPNL000000001234');
    });

    it('should update credentials', () => {
      const { result } = renderHook(() => useDataspace());

      expect(result.current.credentials).toEqual({});

      act(() => {
        result.current.setCredentials({ client_id: 'test', client_secret: 'secret' });
      });

      expect(result.current.credentials).toEqual({
        client_id: 'test',
        client_secret: 'secret',
      });
    });

    it('should reset all state', async () => {
      vi.mocked(dataspaceApi.createConnection).mockResolvedValue({
        connection: mockConnection,
        message: 'Connected',
      });
      vi.mocked(dataspaceApi.pollConnectionStatus).mockImplementation(
        async (_id, onProgress) => {
          onProgress(mockConnection);
          return mockConnection;
        }
      );

      const { result } = renderHook(() => useDataspace());

      act(() => {
        result.current.setBpn('BPNL000000001234');
        result.current.setCredentials({ client_id: 'test' });
      });

      await act(async () => {
        await result.current.connect();
      });

      act(() => {
        result.current.reset();
      });

      expect(result.current.connection).toBeNull();
      expect(result.current.bpn).toBe('');
      expect(result.current.credentials).toEqual({});
      expect(result.current.error).toBeNull();
      expect(result.current.isConnecting).toBe(false);
    });
  });

  describe('refreshStatus', () => {
    it('should refresh connection status', async () => {
      const updatedConnection = { ...mockConnection, progress_message: 'Updated' };
      vi.mocked(dataspaceApi.createConnection).mockResolvedValue({
        connection: mockConnection,
        message: 'Connected',
      });
      vi.mocked(dataspaceApi.pollConnectionStatus).mockImplementation(
        async (_id, onProgress) => {
          onProgress(mockConnection);
          return mockConnection;
        }
      );
      vi.mocked(dataspaceApi.getConnection).mockResolvedValue({
        connection: updatedConnection,
        health_checks: [
          {
            component: 'basyx',
            healthy: true,
            latency_ms: 10,
            message: null,
            checked_at: '2024-01-01T00:00:00Z',
          },
        ],
      });

      const onStatusChange = vi.fn();
      const { result } = renderHook(() => useDataspace({ onStatusChange }));

      await act(async () => {
        await result.current.connect();
      });

      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });

      await act(async () => {
        await result.current.refreshStatus();
      });

      expect(dataspaceApi.getConnection).toHaveBeenCalledWith('conn-123');
      expect(result.current.healthChecks).toHaveLength(1);
      expect(result.current.healthChecks[0].component).toBe('basyx');
    });

    it('should not refresh when not connected', async () => {
      const { result } = renderHook(() => useDataspace());

      await act(async () => {
        await result.current.refreshStatus();
      });

      expect(dataspaceApi.getConnection).not.toHaveBeenCalled();
    });
  });

  describe('reconnect', () => {
    it('should reconnect a failed connection', async () => {
      const failedConnection = { ...mockConnection, status: 'failed' as const };
      vi.mocked(dataspaceApi.createConnection).mockResolvedValue({
        connection: failedConnection,
        message: 'Failed',
      });
      vi.mocked(dataspaceApi.pollConnectionStatus)
        .mockImplementationOnce(async (_id, onProgress) => {
          onProgress(failedConnection);
          return failedConnection;
        })
        .mockImplementationOnce(async (_id, onProgress) => {
          onProgress(mockConnection);
          return mockConnection;
        });
      vi.mocked(dataspaceApi.reconnectConnection).mockResolvedValue({
        connection: { ...mockConnection, status: 'configuring_edc' },
        message: 'Reconnecting',
      });

      const { result } = renderHook(() => useDataspace());

      // First connect (which fails)
      await act(async () => {
        await result.current.connect();
      });

      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });

      expect(result.current.connection).not.toBeNull();

      // Then reconnect
      await act(async () => {
        await result.current.reconnect();
      });

      expect(dataspaceApi.reconnectConnection).toHaveBeenCalledWith('conn-123');
    });

    it('should not reconnect when not connected', async () => {
      const { result } = renderHook(() => useDataspace());

      await act(async () => {
        await result.current.reconnect();
      });

      expect(dataspaceApi.reconnectConnection).not.toHaveBeenCalled();
    });
  });
});
