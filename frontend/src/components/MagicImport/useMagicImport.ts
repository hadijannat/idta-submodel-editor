/**
 * Hook for managing Magic Import state.
 */

import { useState, useCallback, useRef } from 'react';
import type { UseFormReturn, FieldPath } from 'react-hook-form';
import type { SubmodelFormData } from '../../types/aas-elements';
import {
  createMagicImportJob,
  getMagicImportJob,
  getMagicImportResult,
  deleteMagicImportJob,
  getMagicImportPdfUrl,
  type MagicImportJob,
  type MagicImportResult,
  type FieldExtraction,
} from '../../services/magicImportApi';

interface UseMagicImportOptions {
  templateName: string;
  templateStatus: 'published' | 'deprecated';
  templateVersion?: string | null;
  form: UseFormReturn<SubmodelFormData>;
}

interface UseMagicImportReturn {
  // State
  job: MagicImportJob | null;
  result: MagicImportResult | null;
  extractions: FieldExtraction[];
  selectedExtractionPath: string | null;
  isUploading: boolean;
  isProcessing: boolean;
  error: string | null;

  // Actions
  uploadPdf: (file: File) => Promise<void>;
  cancelJob: () => Promise<void>;
  selectExtraction: (path: string | null) => void;
  updateExtraction: (path: string, value: string) => void;
  approveExtraction: (path: string) => void;
  approveAll: () => void;
  applyToForm: () => void;
  reset: () => void;

  // PDF viewer
  pdfUrl: string | null;
}

export function useMagicImport({
  templateName,
  templateStatus,
  templateVersion,
  form,
}: UseMagicImportOptions): UseMagicImportReturn {
  const [job, setJob] = useState<MagicImportJob | null>(null);
  const [result, setResult] = useState<MagicImportResult | null>(null);
  const [extractions, setExtractions] = useState<FieldExtraction[]>([]);
  const [selectedExtractionPath, setSelectedExtractionPath] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Clear polling interval
  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  // Poll job status
  const startPolling = useCallback(
    (jobId: string) => {
      stopPolling();

      const poll = async () => {
        try {
          const updatedJob = await getMagicImportJob(jobId);
          setJob(updatedJob);

          if (updatedJob.status === 'done') {
            stopPolling();
            setIsProcessing(false);

            // Fetch results
            const jobResult = await getMagicImportResult(jobId);
            setResult(jobResult);
            setExtractions(jobResult.extractions);
          } else if (updatedJob.status === 'failed') {
            stopPolling();
            setIsProcessing(false);
            setError(updatedJob.error_message || 'Processing failed');
          }
        } catch (err) {
          console.error('Polling error:', err);
        }
      };

      pollingRef.current = setInterval(poll, 1500);
      poll(); // Initial poll
    },
    [stopPolling]
  );

  // Upload PDF and start processing
  const uploadPdf = useCallback(
    async (file: File) => {
      setIsUploading(true);
      setError(null);

      try {
        const newJob = await createMagicImportJob(
          file,
          templateName,
          templateStatus,
          templateVersion ?? undefined
        );

        setJob(newJob);
        setIsUploading(false);
        setIsProcessing(true);

        // Start polling
        startPolling(newJob.job_id);
      } catch (err) {
        setIsUploading(false);
        setError(err instanceof Error ? err.message : 'Upload failed');
      }
    },
    [templateName, templateStatus, templateVersion, startPolling]
  );

  // Cancel current job
  const cancelJob = useCallback(async () => {
    stopPolling();

    if (job) {
      try {
        await deleteMagicImportJob(job.job_id);
      } catch (err) {
        console.error('Failed to delete job:', err);
      }
    }

    setJob(null);
    setResult(null);
    setExtractions([]);
    setIsProcessing(false);
    setError(null);
  }, [job, stopPolling]);

  // Select an extraction for highlighting
  const selectExtraction = useCallback((path: string | null) => {
    setSelectedExtractionPath(path);
  }, []);

  // Update an extraction value (user edit)
  const updateExtraction = useCallback((path: string, value: string) => {
    setExtractions((prev) =>
      prev.map((e) =>
        e.path === path
          ? {
              ...e,
              value_raw: value,
              value_normalized: value,
              user_edited: true,
              needs_review: false,
              confidence: 1.0,
            }
          : e
      )
    );
  }, []);

  // Approve an extraction
  const approveExtraction = useCallback((path: string) => {
    setExtractions((prev) =>
      prev.map((e) =>
        e.path === path
          ? {
              ...e,
              user_approved: true,
              needs_review: false,
            }
          : e
      )
    );
  }, []);

  // Approve all extractions
  const approveAll = useCallback(() => {
    setExtractions((prev) =>
      prev.map((e) => ({
        ...e,
        user_approved: true,
        needs_review: false,
      }))
    );
  }, []);

  // Apply extractions to form
  const applyToForm = useCallback(() => {
    const approvedExtractions = extractions.filter(
      (e) => e.user_approved || !e.needs_review
    );

    for (const extraction of approvedExtractions) {
      const formPath = pathToFormPath(extraction.path);
      const value = extraction.value_normalized ?? extraction.value_raw;

      try {
        // Dynamic form paths from extraction - cast to FieldPath
        form.setValue(formPath as FieldPath<SubmodelFormData>, value, { shouldDirty: true });
      } catch (err) {
        console.warn(`Failed to set value for ${formPath}:`, err);
      }
    }

    // Store metadata about the import - cast to FieldPath for dynamic path
    form.setValue('metadata.magicImport' as FieldPath<SubmodelFormData>, {
      importedAt: new Date().toISOString(),
      jobId: job?.job_id,
      fieldsApplied: approvedExtractions.length,
      llmProvider: result?.llm_provider,
      llmModel: result?.llm_model,
    });
  }, [extractions, form, job, result]);

  // Reset state
  const reset = useCallback(() => {
    stopPolling();
    setJob(null);
    setResult(null);
    setExtractions([]);
    setSelectedExtractionPath(null);
    setIsUploading(false);
    setIsProcessing(false);
    setError(null);
  }, [stopPolling]);

  // PDF URL for viewer
  const pdfUrl = job ? getMagicImportPdfUrl(job.job_id) : null;

  return {
    job,
    result,
    extractions,
    selectedExtractionPath,
    isUploading,
    isProcessing,
    error,
    uploadPdf,
    cancelJob,
    selectExtraction,
    updateExtraction,
    approveExtraction,
    approveAll,
    applyToForm,
    reset,
    pdfUrl,
  };
}

/**
 * Convert AAS idShortPath to form path.
 *
 * Example: "ManufacturerName" -> "elements.ManufacturerName.value"
 * Example: "ContactInfo.Street" -> "elements.ContactInfo.elements.Street.value"
 */
function pathToFormPath(idShortPath: string): string {
  const segments = idShortPath.split('.');
  const formSegments: string[] = ['elements'];

  for (let i = 0; i < segments.length; i++) {
    const segment = segments[i];

    // Handle list markers
    if (segment.endsWith('[]')) {
      const listName = segment.slice(0, -2);
      formSegments.push(listName, 'items', '0'); // Default to first item
    } else if (i === segments.length - 1) {
      // Last segment - add value field
      formSegments.push(segment, 'value');
    } else {
      formSegments.push(segment, 'elements');
    }
  }

  return formSegments.join('.');
}
