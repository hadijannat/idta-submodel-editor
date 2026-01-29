/**
 * Hook for managing Magic Import state.
 */

import { useState, useCallback, useRef } from 'react';
import type { UseFormReturn, FieldPath } from 'react-hook-form';
import type { SubmodelFormData, ElementFormData } from '../../types/aas-elements';
import type { SubmodelUISchema, UIElementSchema } from '../../types/ui-schema';
import {
  createMagicImportJob,
  getMagicImportJob,
  getMagicImportResult,
  deleteMagicImportJob,
  getMagicImportPdfUrl,
  reExtractFields,
  type MagicImportJob,
  type MagicImportResult,
  type FieldExtraction,
  type UnmappedFinding,
} from '../../services/magicImportApi';

interface UseMagicImportOptions {
  templateName: string;
  templateStatus: 'published' | 'deprecated';
  templateVersion?: string | null;
  form: UseFormReturn<SubmodelFormData>;
  schema?: SubmodelUISchema | null;
}

interface UseMagicImportReturn {
  // State
  job: MagicImportJob | null;
  result: MagicImportResult | null;
  extractions: FieldExtraction[];
  unmappedFindings: UnmappedFinding[];
  selectedExtractionPath: string | null;
  isUploading: boolean;
  isProcessing: boolean;
  isReextracting: boolean;
  error: string | null;

  // Actions
  uploadPdf: (file: File) => Promise<void>;
  cancelJob: () => Promise<void>;
  selectExtraction: (path: string | null) => void;
  updateExtraction: (path: string, value: string) => void;
  approveExtraction: (path: string) => void;
  approveAll: () => void;
  approveMany: (paths: string[]) => void;
  unapproveMany: (paths: string[]) => void;
  reextractPaths: (paths: string[], hint?: string) => Promise<void>;
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
  schema,
}: UseMagicImportOptions): UseMagicImportReturn {
  const [job, setJob] = useState<MagicImportJob | null>(null);
  const [result, setResult] = useState<MagicImportResult | null>(null);
  const [extractions, setExtractions] = useState<FieldExtraction[]>([]);
  const [unmappedFindings, setUnmappedFindings] = useState<UnmappedFinding[]>([]);
  const [selectedExtractionPath, setSelectedExtractionPath] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isReextracting, setIsReextracting] = useState(false);
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
            setUnmappedFindings(jobResult.unmapped_findings || []);
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
    setUnmappedFindings([]);
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
              status: 'filled',
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
              status: e.status === 'empty' ? e.status : 'filled',
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
        status: e.status === 'empty' ? e.status : 'filled',
      }))
    );
  }, []);

  // Approve multiple extractions by path
  const approveMany = useCallback((paths: string[]) => {
    const pathSet = new Set(paths);
    setExtractions((prev) =>
      prev.map((e) =>
        pathSet.has(e.path)
          ? {
              ...e,
              user_approved: true,
              needs_review: false,
              status: e.status === 'empty' ? e.status : 'filled',
            }
          : e
      )
    );
  }, []);

  // Unapprove multiple extractions (for undo functionality)
  const unapproveMany = useCallback((paths: string[]) => {
    const pathSet = new Set(paths);
    setExtractions((prev) =>
      prev.map((e) =>
        pathSet.has(e.path)
          ? {
              ...e,
              user_approved: false,
              needs_review: true,
              status: 'needs_review' as const,
            }
          : e
      )
    );
  }, []);

  // Re-extract specific fields
  const reextractPaths = useCallback(
    async (paths: string[], hint?: string) => {
      if (!job || paths.length === 0) {
        return;
      }

      setIsReextracting(true);
      setError(null);

      try {
        const updated = await reExtractFields(job.job_id, paths, hint);
        const updatedPaths = new Set(paths);

        setResult(updated);
        setExtractions((prev) => mergeReextractResults(prev, updated.extractions, updatedPaths));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Re-extraction failed');
      } finally {
        setIsReextracting(false);
      }
    },
    [job]
  );

  // Apply extractions to form
  const applyToForm = useCallback(() => {
    // Only apply extractions that are approved/ready AND have valid status
    const approvedExtractions = extractions.filter(
      (e) => e.user_approved || e.status === 'filled' || e.user_edited
    );
    const listIndexCache = new Map<string, number>();

    for (const extraction of approvedExtractions) {
      const resolved = resolveFormPath(
        extraction.path,
        schema,
        form,
        listIndexCache
      );
      const value = extraction.value_normalized ?? extraction.value_raw;

      try {
        const formPath = resolved.formPath;
        if (resolved.elementSchema?.modelType === 'MultiLanguageProperty') {
          const current = form.getValues(
            formPath as FieldPath<SubmodelFormData>
          ) as unknown;
          const base =
            current && typeof current === 'object' && !Array.isArray(current)
              ? (current as Record<string, unknown>)
              : {};
          const lang =
            resolved.elementSchema.supportedLanguages?.[0] ||
            DEFAULT_LANGUAGE;
          const next = {
            ...base,
            [lang]: value == null ? '' : String(value),
          };
          form.setValue(formPath as FieldPath<SubmodelFormData>, next, {
            shouldDirty: true,
          });
        } else {
          // Dynamic form paths from extraction - cast to FieldPath
          form.setValue(formPath as FieldPath<SubmodelFormData>, value, {
            shouldDirty: true,
          });
        }
      } catch (err) {
        console.warn(`Failed to set value for ${resolved.formPath}:`, err);
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
  }, [extractions, form, job, result, schema]);

  // Reset state
  const reset = useCallback(() => {
    stopPolling();
    setJob(null);
    setResult(null);
    setExtractions([]);
    setUnmappedFindings([]);
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
    unmappedFindings,
    selectedExtractionPath,
    isUploading,
    isProcessing,
    isReextracting,
    error,
    uploadPdf,
    cancelJob,
    selectExtraction,
    updateExtraction,
    approveExtraction,
    approveAll,
    approveMany,
    unapproveMany,
    reextractPaths,
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

const mergeReextractResults = (
  previous: FieldExtraction[],
  updated: FieldExtraction[],
  reextractPaths: Set<string>
): FieldExtraction[] => {
  const prevByPath = new Map(previous.map((item) => [item.path, item]));
  const updatedPaths = new Set(updated.map((item) => item.path));

  const merged = updated.map((item) => {
    if (reextractPaths.has(item.path)) {
      return item;
    }

    const existing = prevByPath.get(item.path);
    if (existing && (existing.user_edited || existing.user_approved)) {
      return existing;
    }

    return item;
  });

  // Preserve any extractions that exist only client-side
  for (const item of previous) {
    if (!updatedPaths.has(item.path)) {
      merged.push(item);
    }
  }

  return merged;
};

type PathSegment = { name: string; isList: boolean };

const parseIdShortPath = (path: string): PathSegment[] =>
  path
    .split('.')
    .filter(Boolean)
    .map((segment) =>
      segment.endsWith('[]')
        ? { name: segment.slice(0, -2), isList: true }
        : { name: segment, isList: false }
    );

const getListItemSchema = (listSchema: UIElementSchema | null | undefined): UIElementSchema | null => {
  if (!listSchema) return null;
  if (listSchema.itemTemplate) return listSchema.itemTemplate;
  if (listSchema.items && listSchema.items.length > 0) return listSchema.items[0];
  return null;
};

const createDefaultItem = (template: UIElementSchema | null): ElementFormData => {
  const withSemanticDefaults = (
    defaults: ElementFormData,
    source?: UIElementSchema | null
  ): ElementFormData => ({
    ...defaults,
    semanticId: source?.semanticId ?? null,
    valueId: source?.valueId ?? null,
    semanticIdListElement: source?.semanticIdListElement ?? null,
  });

  if (!template) return withSemanticDefaults({ value: '' });

  switch (template.modelType) {
    case 'Property':
      return withSemanticDefaults({ value: template.value ?? '' }, template);

    case 'MultiLanguageProperty':
      return withSemanticDefaults({ value: {} }, template);

    case 'SubmodelElementCollection': {
      const elements: Record<string, ElementFormData> = {};
      for (const child of template.elements || []) {
        elements[child.idShort] = createDefaultItem(child);
      }
      return withSemanticDefaults({ elements }, template);
    }

    case 'SubmodelElementList': {
      const itemSchema = getListItemSchema(template);
      const items = itemSchema ? [createDefaultItem(itemSchema)] : [];
      return withSemanticDefaults(
        {
          items,
          semanticIdListElement: template.semanticIdListElement ?? null,
        },
        template
      );
    }

    case 'Range':
      return withSemanticDefaults({ min: '', max: '' }, template);

    case 'File':
      return withSemanticDefaults(
        { value: template.value ?? '', contentType: template.contentType ?? '' },
        template
      );

    case 'ReferenceElement':
      return withSemanticDefaults({ value: template.value ?? '' }, template);

    case 'Entity': {
      const statements: Record<string, ElementFormData> = {};
      for (const stmt of template.statements || []) {
        statements[stmt.idShort] = createDefaultItem(stmt);
      }
      return withSemanticDefaults(
        { statements, globalAssetId: template.globalAssetId ?? '' },
        template
      );
    }

    default:
      return withSemanticDefaults({ value: template.value ?? '' }, template);
  }
};

const isGuidelineSpecificList = (listSchema: UIElementSchema | null | undefined): boolean =>
  listSchema?.idShort === 'GuidelineSpecificProperties';

const DEFAULT_GUIDELINE_DECLARATION = 'Manufacturer Datasheet';
const DEFAULT_LANGUAGE = 'en';

const ensureListIndex = (
  listPath: string,
  listSchema: UIElementSchema | null | undefined,
  form: UseFormReturn<SubmodelFormData>,
  listIndexCache: Map<string, number>
): number => {
  const cached = listIndexCache.get(listPath);
  if (cached !== undefined) return cached;

  const current = form.getValues(
    listPath as FieldPath<SubmodelFormData>
  ) as unknown;
  const items = Array.isArray(current)
    ? [...(current as ElementFormData[])]
    : [];
  let index = -1;

  if (items.length > 0 && isGuidelineSpecificList(listSchema)) {
    index = items.findIndex((item) => {
      const value =
        item.elements &&
        typeof item.elements === 'object' &&
        item.elements.GuidelineForConformityDeclaration &&
        (item.elements.GuidelineForConformityDeclaration as ElementFormData).value;
      return !value;
    });
  }

  if (index < 0 && items.length > 0) {
    index = 0;
  }

  if (index < 0) {
    const itemSchema = getListItemSchema(listSchema);
    items.push(createDefaultItem(itemSchema));
    index = items.length - 1;
    if (isGuidelineSpecificList(listSchema)) {
      const item = items[index];
      if (item && item.elements && typeof item.elements === 'object') {
        const guideline = item.elements.GuidelineForConformityDeclaration as
          | ElementFormData
          | undefined;
        if (guideline && (guideline.value === undefined || guideline.value === '')) {
          guideline.value = DEFAULT_GUIDELINE_DECLARATION;
        }
      }
    }
    form.setValue(listPath as FieldPath<SubmodelFormData>, items, {
      shouldDirty: true,
    });
  }

  listIndexCache.set(listPath, index);
  return index;
};

const resolveFormPath = (
  idShortPath: string,
  schema: SubmodelUISchema | null | undefined,
  form: UseFormReturn<SubmodelFormData>,
  listIndexCache: Map<string, number>
): { formPath: string; elementSchema: UIElementSchema | null } => {
  if (!schema) {
    return { formPath: pathToFormPath(idShortPath), elementSchema: null };
  }

  const segments = parseIdShortPath(idShortPath);
  let elements: UIElementSchema[] = schema.elements ?? [];
  const formParts: string[] = ['elements'];
  let skipIdShort: string | null = null;
  let nextContainerKey: 'elements' | 'statements' | null = null;
  let leafSchema: UIElementSchema | null = null;

  for (const segment of segments) {
    if (skipIdShort && segment.name === skipIdShort) {
      skipIdShort = null;
      continue;
    }

    if (nextContainerKey) {
      formParts.push(nextContainerKey);
      nextContainerKey = null;
    }

    if (segment.isList) {
      const listSchema = elements.find((el) => el.idShort === segment.name);
      if (!listSchema) {
        return { formPath: pathToFormPath(idShortPath), elementSchema: null };
      }

      formParts.push(segment.name, 'items');
      const listPath = formParts.join('.');
      const index = ensureListIndex(listPath, listSchema, form, listIndexCache);
      formParts.push(String(index));

      const itemSchema = getListItemSchema(listSchema);
      if (itemSchema?.modelType === 'SubmodelElementCollection') {
        if (itemSchema.idShort) {
          skipIdShort = itemSchema.idShort;
        }
        elements = itemSchema.elements ?? [];
        nextContainerKey = 'elements';
      } else if (itemSchema?.modelType === 'Entity') {
        elements = itemSchema.statements ?? [];
        nextContainerKey = 'statements';
      } else {
        elements = [];
        nextContainerKey = null;
      }
      continue;
    }

    formParts.push(segment.name);
    const elementSchema = elements.find((el) => el.idShort === segment.name);
    if (!elementSchema) {
      return { formPath: pathToFormPath(idShortPath), elementSchema: null };
    }

    leafSchema = elementSchema;

    if (elementSchema.modelType === 'SubmodelElementCollection') {
      elements = elementSchema.elements ?? [];
      nextContainerKey = 'elements';
    } else if (elementSchema.modelType === 'Entity') {
      elements = elementSchema.statements ?? [];
      nextContainerKey = 'statements';
    } else {
      elements = [];
      nextContainerKey = null;
    }
  }

  formParts.push('value');
  return { formPath: formParts.join('.'), elementSchema: leafSchema };
};
