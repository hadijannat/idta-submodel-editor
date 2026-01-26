/**
 * Hook for managing dataspace publications.
 *
 * Provides state management for publishing and managing submodels
 * in Manufacturing-X / Catena-X dataspaces.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  createPublication,
  listPublications,
  getPublication,
  deletePublication,
  pollPublicationStatus,
  type SubmodelPublication,
  type PublishSubmodelRequest,
  type PolicyConfig,
  type PublicationStatus,
} from '../../services/dataspaceApi';

interface UsePublicationsOptions {
  /**
   * Connection ID to filter publications.
   */
  connectionId?: string;
  /**
   * Called when a publication is created.
   */
  onPublished?: (publication: SubmodelPublication) => void;
  /**
   * Called when a publication fails.
   */
  onError?: (error: string) => void;
}

interface UsePublicationsReturn {
  // State
  publications: SubmodelPublication[];
  activePublication: SubmodelPublication | null;
  isLoading: boolean;
  isPublishing: boolean;
  error: string | null;

  // Actions
  loadPublications: (connectionId?: string, templateName?: string) => Promise<void>;
  publish: (
    connectionId: string,
    templateName: string,
    formData: Record<string, unknown>,
    options?: {
      templateStatus?: 'published' | 'deprecated';
      templateVersion?: string | null;
      aasId?: string | null;
      submodelId?: string | null;
      policy?: PolicyConfig | null;
    }
  ) => Promise<SubmodelPublication>;
  unpublish: (publicationId: string) => Promise<void>;
  refreshPublication: (publicationId: string) => Promise<void>;
  setActivePublication: (publication: SubmodelPublication | null) => void;
  reset: () => void;
}

export function usePublications(
  options: UsePublicationsOptions = {}
): UsePublicationsReturn {
  const { connectionId: defaultConnectionId, onPublished, onError } = options;

  // State
  const [publications, setPublications] = useState<SubmodelPublication[]>([]);
  const [activePublication, setActivePublication] = useState<SubmodelPublication | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Polling ref
  const pollingRef = useRef<boolean>(false);

  // Stop polling
  const stopPolling = useCallback(() => {
    pollingRef.current = false;
  }, []);

  // Load publications
  const loadPublications = useCallback(
    async (connectionId?: string, templateName?: string) => {
      setIsLoading(true);
      setError(null);

      try {
        const response = await listPublications(
          connectionId || defaultConnectionId,
          templateName
        );
        setPublications(response.publications);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load publications';
        setError(message);
        onError?.(message);
      } finally {
        setIsLoading(false);
      }
    },
    [defaultConnectionId, onError]
  );

  // Publish a submodel
  const publish = useCallback(
    async (
      connectionId: string,
      templateName: string,
      formData: Record<string, unknown>,
      publishOptions?: {
        templateStatus?: 'published' | 'deprecated';
        templateVersion?: string | null;
        aasId?: string | null;
        submodelId?: string | null;
        policy?: PolicyConfig | null;
      }
    ): Promise<SubmodelPublication> => {
      setIsPublishing(true);
      setError(null);

      try {
        const request: PublishSubmodelRequest = {
          connection_id: connectionId,
          template_name: templateName,
          form_data: formData,
          template_status: publishOptions?.templateStatus || 'published',
          template_version: publishOptions?.templateVersion,
          aas_id: publishOptions?.aasId,
          submodel_id: publishOptions?.submodelId,
          policy: publishOptions?.policy,
        };

        const response = await createPublication(request);
        const publication = response.publication;

        // Add to list
        setPublications((prev) => [publication, ...prev]);
        setActivePublication(publication);

        // Start polling for publication progress
        pollingRef.current = true;
        const finalPublication = await pollPublicationStatus(
          publication.publication_id,
          (pub) => {
            if (!pollingRef.current) return;
            setActivePublication(pub);
            // Update in list
            setPublications((prev) =>
              prev.map((p) =>
                p.publication_id === pub.publication_id ? pub : p
              )
            );
          },
          2000
        );

        stopPolling();
        setIsPublishing(false);

        if (finalPublication.status === 'published') {
          onPublished?.(finalPublication);
        } else if (finalPublication.status === 'failed') {
          const errMsg = 'Publication failed';
          setError(errMsg);
          onError?.(errMsg);
        }

        return finalPublication;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to publish';
        setError(message);
        setIsPublishing(false);
        onError?.(message);
        throw err;
      }
    },
    [onPublished, onError, stopPolling]
  );

  // Unpublish a submodel
  const unpublish = useCallback(
    async (publicationId: string) => {
      setError(null);

      try {
        await deletePublication(publicationId);

        // Update in list
        setPublications((prev) =>
          prev.map((p) =>
            p.publication_id === publicationId
              ? { ...p, status: 'unpublished' as PublicationStatus }
              : p
          )
        );

        // Clear active if it was the unpublished one
        if (activePublication?.publication_id === publicationId) {
          setActivePublication(null);
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to unpublish';
        setError(message);
        onError?.(message);
        throw err;
      }
    },
    [activePublication, onError]
  );

  // Refresh a publication's status
  const refreshPublication = useCallback(
    async (publicationId: string) => {
      try {
        const publication = await getPublication(publicationId);

        // Update in list
        setPublications((prev) =>
          prev.map((p) => (p.publication_id === publicationId ? publication : p))
        );

        // Update active if it's the same one
        if (activePublication?.publication_id === publicationId) {
          setActivePublication(publication);
        }
      } catch (err) {
        const message =
          err instanceof Error ? err.message : 'Failed to refresh publication';
        setError(message);
      }
    },
    [activePublication]
  );

  // Reset state
  const reset = useCallback(() => {
    stopPolling();
    setPublications([]);
    setActivePublication(null);
    setIsLoading(false);
    setIsPublishing(false);
    setError(null);
  }, [stopPolling]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      pollingRef.current = false;
    };
  }, []);

  return {
    // State
    publications,
    activePublication,
    isLoading,
    isPublishing,
    error,

    // Actions
    loadPublications,
    publish,
    unpublish,
    refreshPublication,
    setActivePublication,
    reset,
  };
}
