/**
 * Tests for usePublications hook.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { usePublications } from '../usePublications';
import * as dataspaceApi from '../../../services/dataspaceApi';

// Mock the dataspace API
vi.mock('../../../services/dataspaceApi', () => ({
  createPublication: vi.fn(),
  listPublications: vi.fn(),
  getPublication: vi.fn(),
  deletePublication: vi.fn(),
  pollPublicationStatus: vi.fn(),
}));

const mockPublication: dataspaceApi.SubmodelPublication = {
  publication_id: 'pub-123',
  connection_id: 'conn-123',
  template_name: 'DigitalNameplate',
  submodel_id: 'urn:submodel:nameplate:123',
  status: 'published',
  aas_endpoint: 'http://basyx:8081/shells/aas123',
  dtr_asset_id: 'dtr-asset-123',
  edc_offer_id: 'edc-offer-123',
  policy_id: 'policy-123',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

const mockPublications: dataspaceApi.SubmodelPublication[] = [
  mockPublication,
  {
    ...mockPublication,
    publication_id: 'pub-456',
    template_name: 'PCF',
    submodel_id: 'urn:submodel:pcf:456',
    status: 'pending',
  },
  {
    ...mockPublication,
    publication_id: 'pub-789',
    template_name: 'ContactInfo',
    submodel_id: 'urn:submodel:contact:789',
    status: 'failed',
  },
];

describe('usePublications hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('loadPublications', () => {
    it('should load publications successfully', async () => {
      vi.mocked(dataspaceApi.listPublications).mockResolvedValue({
        publications: mockPublications,
        total: 3,
      });

      const { result } = renderHook(() => usePublications());

      expect(result.current.isLoading).toBe(false);
      expect(result.current.publications).toEqual([]);

      await act(async () => {
        await result.current.loadPublications('conn-123');
      });

      expect(result.current.publications).toEqual(mockPublications);
      expect(result.current.isLoading).toBe(false);
      expect(dataspaceApi.listPublications).toHaveBeenCalledWith('conn-123', undefined);
    });

    it('should handle load error', async () => {
      vi.mocked(dataspaceApi.listPublications).mockRejectedValue(
        new Error('Failed to fetch')
      );

      const onError = vi.fn();
      const { result } = renderHook(() => usePublications({ onError }));

      await act(async () => {
        await result.current.loadPublications('conn-123');
      });

      expect(result.current.error).toBe('Failed to fetch');
      expect(onError).toHaveBeenCalledWith('Failed to fetch');
    });

    it('should use default connectionId from options', async () => {
      vi.mocked(dataspaceApi.listPublications).mockResolvedValue({
        publications: mockPublications,
        total: 3,
      });

      const { result } = renderHook(() =>
        usePublications({ connectionId: 'default-conn' })
      );

      await act(async () => {
        await result.current.loadPublications();
      });

      expect(dataspaceApi.listPublications).toHaveBeenCalledWith(
        'default-conn',
        undefined
      );
    });

    it('should filter by template name', async () => {
      vi.mocked(dataspaceApi.listPublications).mockResolvedValue({
        publications: [mockPublication],
        total: 1,
      });

      const { result } = renderHook(() => usePublications());

      await act(async () => {
        await result.current.loadPublications('conn-123', 'DigitalNameplate');
      });

      expect(dataspaceApi.listPublications).toHaveBeenCalledWith(
        'conn-123',
        'DigitalNameplate'
      );
    });
  });

  describe('publish', () => {
    it('should create publication and poll for status', async () => {
      const pendingPublication = { ...mockPublication, status: 'pending' as const };
      vi.mocked(dataspaceApi.createPublication).mockResolvedValue({
        publication: pendingPublication,
        message: 'Publication initiated',
      });
      vi.mocked(dataspaceApi.pollPublicationStatus).mockImplementation(
        async (_id, onProgress) => {
          onProgress?.(mockPublication);
          return mockPublication;
        }
      );

      const onPublished = vi.fn();
      const { result } = renderHook(() => usePublications({ onPublished }));

      let publishedResult: dataspaceApi.SubmodelPublication | undefined;

      await act(async () => {
        publishedResult = await result.current.publish(
          'conn-123',
          'DigitalNameplate',
          { elements: { SerialNumber: { value: '12345' } } }
        );
      });

      expect(dataspaceApi.createPublication).toHaveBeenCalledWith({
        connection_id: 'conn-123',
        template_name: 'DigitalNameplate',
        form_data: { elements: { SerialNumber: { value: '12345' } } },
        template_status: 'published',
        template_version: undefined,
        aas_id: undefined,
        submodel_id: undefined,
        policy: undefined,
      });

      expect(publishedResult).toEqual(mockPublication);
      expect(onPublished).toHaveBeenCalledWith(mockPublication);
      // The publication should be updated in the list after polling
      expect(result.current.publications).toHaveLength(1);
      expect(result.current.publications[0].status).toBe('published');
    });

    it('should include all options when publishing', async () => {
      const pendingPublication = { ...mockPublication, status: 'pending' as const };
      vi.mocked(dataspaceApi.createPublication).mockResolvedValue({
        publication: pendingPublication,
        message: 'Publication initiated',
      });
      vi.mocked(dataspaceApi.pollPublicationStatus).mockImplementation(
        async (_id, onProgress) => {
          onProgress?.(mockPublication);
          return mockPublication;
        }
      );

      const { result } = renderHook(() => usePublications());

      const policy: dataspaceApi.PolicyConfig = {
        access_type: 'restricted',
        allowed_partners: ['BPNL000000001234'],
      };

      await act(async () => {
        await result.current.publish('conn-123', 'DigitalNameplate', { elements: {} }, {
          templateStatus: 'deprecated',
          templateVersion: '1.0.0',
          aasId: 'urn:aas:123',
          submodelId: 'urn:submodel:456',
          policy,
        });
      });

      expect(dataspaceApi.createPublication).toHaveBeenCalledWith({
        connection_id: 'conn-123',
        template_name: 'DigitalNameplate',
        form_data: { elements: {} },
        template_status: 'deprecated',
        template_version: '1.0.0',
        aas_id: 'urn:aas:123',
        submodel_id: 'urn:submodel:456',
        policy,
      });
    });

    it('should handle publication failure', async () => {
      vi.mocked(dataspaceApi.createPublication).mockRejectedValue(
        new Error('Publication failed')
      );

      const onError = vi.fn();
      const { result } = renderHook(() => usePublications({ onError }));

      let thrownError: Error | null = null;
      await act(async () => {
        try {
          await result.current.publish('conn-123', 'DigitalNameplate', { elements: {} });
        } catch (err) {
          thrownError = err as Error;
        }
      });

      expect(thrownError).not.toBeNull();
      expect(result.current.error).toBe('Publication failed');
      expect(onError).toHaveBeenCalledWith('Publication failed');
      expect(result.current.isPublishing).toBe(false);
    });

    it('should handle failed publication status', async () => {
      const failedPublication = { ...mockPublication, status: 'failed' as const };
      vi.mocked(dataspaceApi.createPublication).mockResolvedValue({
        publication: { ...mockPublication, status: 'pending' },
        message: 'Publication initiated',
      });
      vi.mocked(dataspaceApi.pollPublicationStatus).mockImplementation(
        async (_id, onProgress) => {
          onProgress?.(failedPublication);
          return failedPublication;
        }
      );

      const onError = vi.fn();
      const { result } = renderHook(() => usePublications({ onError }));

      await act(async () => {
        await result.current.publish('conn-123', 'DigitalNameplate', { elements: {} });
      });

      // Allow state to settle
      await act(async () => {
        await new Promise((resolve) => setTimeout(resolve, 0));
      });

      expect(result.current.error).toBe('Publication failed');
      expect(onError).toHaveBeenCalledWith('Publication failed');
    });
  });

  describe('unpublish', () => {
    it('should unpublish a publication', async () => {
      vi.mocked(dataspaceApi.listPublications).mockResolvedValue({
        publications: mockPublications,
        total: 3,
      });
      vi.mocked(dataspaceApi.deletePublication).mockResolvedValue({
        publication_id: 'pub-123',
        status: 'unpublished',
        message: 'Unpublished successfully',
      });

      const { result } = renderHook(() => usePublications());

      // Load publications first
      await act(async () => {
        await result.current.loadPublications('conn-123');
      });

      // Then unpublish
      await act(async () => {
        await result.current.unpublish('pub-123');
      });

      expect(dataspaceApi.deletePublication).toHaveBeenCalledWith('pub-123');

      // Check that the publication status was updated in the list
      const unpublishedPub = result.current.publications.find(
        (p) => p.publication_id === 'pub-123'
      );
      expect(unpublishedPub?.status).toBe('unpublished');
    });

    it('should handle unpublish error', async () => {
      vi.mocked(dataspaceApi.deletePublication).mockRejectedValue(
        new Error('Failed to unpublish')
      );

      const onError = vi.fn();
      const { result } = renderHook(() => usePublications({ onError }));

      let thrownError: Error | null = null;
      await act(async () => {
        try {
          await result.current.unpublish('pub-123');
        } catch (err) {
          thrownError = err as Error;
        }
      });

      expect(thrownError).not.toBeNull();
      expect(result.current.error).toBe('Failed to unpublish');
      expect(onError).toHaveBeenCalledWith('Failed to unpublish');
    });

    it('should clear active publication when unpublishing it', async () => {
      vi.mocked(dataspaceApi.listPublications).mockResolvedValue({
        publications: mockPublications,
        total: 3,
      });
      vi.mocked(dataspaceApi.deletePublication).mockResolvedValue({
        publication_id: 'pub-123',
        status: 'unpublished',
        message: 'Unpublished successfully',
      });

      const { result } = renderHook(() => usePublications());

      // Load and set active
      await act(async () => {
        await result.current.loadPublications('conn-123');
      });

      act(() => {
        result.current.setActivePublication(mockPublication);
      });

      expect(result.current.activePublication).toEqual(mockPublication);

      // Unpublish the active one
      await act(async () => {
        await result.current.unpublish('pub-123');
      });

      expect(result.current.activePublication).toBeNull();
    });
  });

  describe('refreshPublication', () => {
    it('should refresh a single publication status', async () => {
      const updatedPublication = {
        ...mockPublication,
        progress_message: 'Updated',
      };
      vi.mocked(dataspaceApi.listPublications).mockResolvedValue({
        publications: mockPublications,
        total: 3,
      });
      vi.mocked(dataspaceApi.getPublication).mockResolvedValue(updatedPublication);

      const { result } = renderHook(() => usePublications());

      // Load publications first
      await act(async () => {
        await result.current.loadPublications('conn-123');
      });

      // Refresh one publication
      await act(async () => {
        await result.current.refreshPublication('pub-123');
      });

      expect(dataspaceApi.getPublication).toHaveBeenCalledWith('pub-123');

      // Check that the publication was updated in the list
      const refreshedPub = result.current.publications.find(
        (p) => p.publication_id === 'pub-123'
      );
      expect(refreshedPub).toEqual(updatedPublication);
    });

    it('should update active publication when refreshing it', async () => {
      const updatedPublication = {
        ...mockPublication,
        progress_message: 'Updated',
      };
      vi.mocked(dataspaceApi.listPublications).mockResolvedValue({
        publications: mockPublications,
        total: 3,
      });
      vi.mocked(dataspaceApi.getPublication).mockResolvedValue(updatedPublication);

      const { result } = renderHook(() => usePublications());

      // Load and set active
      await act(async () => {
        await result.current.loadPublications('conn-123');
      });

      act(() => {
        result.current.setActivePublication(mockPublication);
      });

      // Refresh the active one
      await act(async () => {
        await result.current.refreshPublication('pub-123');
      });

      expect(result.current.activePublication).toEqual(updatedPublication);
    });
  });

  describe('state management', () => {
    it('should set active publication', () => {
      const { result } = renderHook(() => usePublications());

      expect(result.current.activePublication).toBeNull();

      act(() => {
        result.current.setActivePublication(mockPublication);
      });

      expect(result.current.activePublication).toEqual(mockPublication);
    });

    it('should reset all state', async () => {
      vi.mocked(dataspaceApi.listPublications).mockResolvedValue({
        publications: mockPublications,
        total: 3,
      });

      const { result } = renderHook(() => usePublications());

      await act(async () => {
        await result.current.loadPublications('conn-123');
      });

      act(() => {
        result.current.setActivePublication(mockPublication);
      });

      act(() => {
        result.current.reset();
      });

      expect(result.current.publications).toEqual([]);
      expect(result.current.activePublication).toBeNull();
      expect(result.current.isLoading).toBe(false);
      expect(result.current.isPublishing).toBe(false);
      expect(result.current.error).toBeNull();
    });
  });
});
