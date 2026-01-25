/**
 * Hook for managing submodel form state with React Hook Form and Zod validation.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useForm, UseFormReturn } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import type { SubmodelUISchema, UIElementSchema } from '../types/ui-schema';
import type { SubmodelFormData, ElementFormData } from '../types/aas-elements';
import {
  getTemplateSchema,
  validateFormData,
  exportAsAasx,
  exportAsJson,
  exportAsPdf,
  verifyExport,
} from '../services/api';
import { getMaxItems, getMinItems, isRequired } from '../types/aas-elements';

interface UseSubmodelFormOptions {
  /** Template name to load */
  templateName?: string;
  /** Template status to load */
  templateStatus?: 'published' | 'deprecated';
  /** Template version to load */
  templateVersion?: string | null;
  /** Pre-loaded schema (skip API call) */
  initialSchema?: SubmodelUISchema;
  /** Called when form is submitted successfully */
  onSubmit?: (data: SubmodelFormData) => void;
}

interface UseSubmodelFormReturn {
  /** The UI schema */
  schema: SubmodelUISchema | null;
  /** React Hook Form instance */
  form: UseFormReturn<SubmodelFormData>;
  /** Loading state */
  loading: boolean;
  /** Error message */
  error: string | null;
  /** Validation state */
  validating: boolean;
  /** Validation result */
  validationResult: { valid: boolean; errors: string[]; warnings: string[] } | null;
  /** Load or reload schema */
  loadSchema: (
    templateName: string,
    status?: 'published' | 'deprecated',
    version?: string | null
  ) => Promise<void>;
  /** Validate the form */
  validate: () => Promise<boolean>;
  /** Export as AASX */
  exportAasx: (filename?: string) => Promise<void>;
  /** Export as JSON */
  exportJson: (filename?: string) => Promise<void>;
  /** Export as PDF */
  exportPdf: (filename?: string) => Promise<void>;
  /** Verify export without downloading */
  verifyExport: () => Promise<void>;
  /** Reset form to default values */
  resetForm: () => void;
}

/**
 * Generate Zod schema from UI element schema.
 */
function generateZodSchema(element: UIElementSchema): z.ZodTypeAny {
  const required = isRequired(element.cardinality);
  const withSemanticFields = (schema: z.AnyZodObject) =>
    schema.extend({
      semanticId: z.string().optional().nullable(),
      valueId: z.string().optional().nullable(),
      semanticIdListElement: z.string().optional().nullable(),
    });

  switch (element.modelType) {
    case 'Property': {
      let propSchema: z.ZodTypeAny;
      const valueType = element.valueType || 'xs:string';

      if (valueType.includes('int') || valueType.includes('Integer')) {
        propSchema = z.coerce.number().int();
      } else if (
        valueType.includes('float') ||
        valueType.includes('double') ||
        valueType.includes('decimal')
      ) {
        propSchema = z.coerce.number();
      } else if (valueType.includes('bool')) {
        propSchema = z.boolean();
      } else if (valueType.includes('date')) {
        propSchema = z.string();
      } else {
        propSchema = z.string();
      }

      const valueSchema =
        required && propSchema instanceof z.ZodString
          ? propSchema.min(1)
          : propSchema;

      return withSemanticFields(
        z.object({
          value: required ? valueSchema : valueSchema.optional().nullable(),
        })
      );
    }

    case 'MultiLanguageProperty': {
      return withSemanticFields(
        z.object({
          value: z.record(z.string()).optional(),
        })
      );
    }

    case 'SubmodelElementCollection': {
      const elementsSchema: Record<string, z.ZodTypeAny> = {};
      for (const child of element.elements || []) {
        elementsSchema[child.idShort] = generateZodSchema(child);
      }
      return withSemanticFields(
        z.object({
          elements: z.object(elementsSchema),
        })
      );
    }

    case 'SubmodelElementList': {
      const itemSchema = element.itemTemplate
        ? generateZodSchema(element.itemTemplate)
        : z.any();
      const minItems = getMinItems(element.cardinality);
      const maxItems = getMaxItems(element.cardinality);
      const itemsSchema = maxItems
        ? z.array(itemSchema).min(minItems).max(maxItems)
        : z.array(itemSchema).min(minItems);
      return withSemanticFields(
        z.object({
          items: itemsSchema,
          semanticIdListElement: z.string().optional().nullable(),
        })
      );
    }

    case 'File': {
      return withSemanticFields(
        z.object({
          value: required ? z.string().min(1) : z.string().optional(),
          contentType: z.string().optional(),
        })
      );
    }

    case 'Range': {
      const valueType = element.valueType || 'xs:double';
      const numSchema = valueType.includes('int')
        ? z.coerce.number().int()
        : z.coerce.number();

      return withSemanticFields(
        z.object({
          min: required ? numSchema : numSchema.optional().nullable(),
          max: required ? numSchema : numSchema.optional().nullable(),
        })
      );
    }

    case 'ReferenceElement': {
      return withSemanticFields(
        z.object({
          value: required ? z.string().min(1) : z.string().optional(),
        })
      );
    }

    case 'Entity': {
      const statementsSchema: Record<string, z.ZodTypeAny> = {};
      for (const stmt of element.statements || []) {
        statementsSchema[stmt.idShort] = generateZodSchema(stmt);
      }
      return withSemanticFields(
        z.object({
          globalAssetId: z.string().optional(),
          statements: z.object(statementsSchema),
        })
      );
    }

    default:
      return withSemanticFields(z.object({ value: z.any().optional() }));
  }
}

/**
 * Generate default values from UI schema.
 */
function generateDefaultValues(schema: SubmodelUISchema): SubmodelFormData {
  const elements: Record<string, ElementFormData> = {};

  for (const element of schema.elements) {
    elements[element.idShort] = generateElementDefaults(element);
  }

  return {
    elements,
    metadata: {
      idShort: schema.idShort ?? '',
      submodelId: schema.submodelId ?? '',
      administration: {
        version: schema.administration?.version ?? '',
        revision: schema.administration?.revision ?? '',
        templateId: schema.administration?.templateId ?? '',
      },
    },
  };
}

/**
 * Generate default value for a single element.
 */
function generateElementDefaults(element: UIElementSchema): ElementFormData {
  const withSemanticDefaults = (defaults: ElementFormData): ElementFormData => ({
    ...defaults,
    semanticId: element.semanticId ?? null,
    valueId: element.valueId ?? null,
    semanticIdListElement: element.semanticIdListElement ?? null,
  });

  switch (element.modelType) {
    case 'Property':
      return withSemanticDefaults({ value: element.value ?? '' });

    case 'MultiLanguageProperty':
      return withSemanticDefaults({
        value: (element.value as Record<string, string>) ?? {},
      });

    case 'SubmodelElementCollection': {
      const childElements: Record<string, ElementFormData> = {};
      for (const child of element.elements || []) {
        childElements[child.idShort] = generateElementDefaults(child);
      }
      return withSemanticDefaults({ elements: childElements });
    }

    case 'SubmodelElementList': {
      const items: ElementFormData[] = [];
      for (const item of element.items || []) {
        items.push(generateElementDefaults(item));
      }
      return withSemanticDefaults({
        items,
        semanticIdListElement: element.semanticIdListElement ?? null,
      });
    }

    case 'File':
      return withSemanticDefaults({
        value: element.value ?? '',
        contentType: element.contentType ?? '',
      });

    case 'Range':
      return withSemanticDefaults({
        min: element.min ?? '',
        max: element.max ?? '',
      });

    case 'ReferenceElement':
      return withSemanticDefaults({ value: element.value ?? '' });

    case 'Entity': {
      const statements: Record<string, ElementFormData> = {};
      for (const stmt of element.statements || []) {
        statements[stmt.idShort] = generateElementDefaults(stmt);
      }
      return withSemanticDefaults({
        globalAssetId: element.globalAssetId ?? '',
        statements,
      });
    }

    default:
      return withSemanticDefaults({ value: element.value ?? '' });
  }
}

/**
 * Hook for managing submodel form with validation.
 */
export function useSubmodelForm(
  options: UseSubmodelFormOptions = {}
): UseSubmodelFormReturn {
  const { templateName, initialSchema, templateStatus, templateVersion } =
    options;

  const [schema, setSchema] = useState<SubmodelUISchema | null>(
    initialSchema || null
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<{
    valid: boolean;
    errors: string[];
    warnings: string[];
  } | null>(null);

  // Generate Zod schema from UI schema
  const zodSchema = useMemo(() => {
    if (!schema) return z.object({ elements: z.record(z.any()) });

    const elementsSchema: Record<string, z.ZodTypeAny> = {};
    for (const element of schema.elements) {
      elementsSchema[element.idShort] = generateZodSchema(element);
    }

    return z.object({
      elements: z.object(elementsSchema),
      metadata: z
        .object({
          idShort: z.string().optional(),
          submodelId: z.string().optional(),
          administration: z
            .object({
              version: z.string().optional(),
              revision: z.string().optional(),
              templateId: z.string().optional(),
            })
            .optional(),
        })
        .optional(),
    });
  }, [schema]);

  // Generate default values
  const defaultValues = useMemo(() => {
    if (!schema) return { elements: {} };
    return generateDefaultValues(schema);
  }, [schema]);

  // Initialize form
  const form = useForm<SubmodelFormData>({
    resolver: zodResolver(zodSchema),
    defaultValues,
    mode: 'onBlur',
  });

  // Load schema from API
  const loadSchema = useCallback(
    async (
      name: string,
      status?: 'published' | 'deprecated',
      version?: string | null
    ) => {
      setLoading(true);
      setError(null);

      try {
        const loadedSchema = await getTemplateSchema(name, status, version);
        setSchema(loadedSchema);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load schema';
        setError(message);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  // Load on mount if templateName provided
  useEffect(() => {
    if (templateName && !initialSchema) {
      loadSchema(templateName, templateStatus, templateVersion);
    }
  }, [templateName, initialSchema, loadSchema, templateStatus, templateVersion]);

  // Reset form when schema changes
  useEffect(() => {
    if (schema) {
      const newDefaults = generateDefaultValues(schema);
      form.reset(newDefaults);
    }
  }, [schema, form]);

  // Validate form against backend
  const validate = useCallback(async (): Promise<boolean> => {
    if (!schema || !templateName) return false;

    setValidating(true);
    try {
      const formData = form.getValues();
      const result = await validateFormData(
        templateName,
        formData,
        templateStatus,
        templateVersion
      );

      setValidationResult({
        valid: result.valid,
        errors: result.errors.map((e) => `${e.field}: ${e.message}`),
        warnings: result.warnings.map((w) => `${w.field}: ${w.message}`),
      });

      return result.valid;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Validation failed';
      setError(message);
      return false;
    } finally {
      setValidating(false);
    }
  }, [schema, templateName, form, templateStatus, templateVersion]);

  // Export functions
  const handleExportAasx = useCallback(
    async (filename?: string) => {
      if (!templateName) throw new Error('No template loaded');
      const formData = form.getValues();
      await exportAsAasx(
        templateName,
        formData,
        filename,
        templateStatus,
        templateVersion
      );
    },
    [templateName, form, templateStatus, templateVersion]
  );

  const handleExportJson = useCallback(
    async (filename?: string) => {
      if (!templateName) throw new Error('No template loaded');
      const formData = form.getValues();
      await exportAsJson(
        templateName,
        formData,
        filename,
        templateStatus,
        templateVersion
      );
    },
    [templateName, form, templateStatus, templateVersion]
  );

  const handleExportPdf = useCallback(
    async (filename?: string) => {
      if (!templateName) throw new Error('No template loaded');
      const formData = form.getValues();
      await exportAsPdf(
        templateName,
        formData,
        filename,
        templateStatus,
        templateVersion
      );
    },
    [templateName, form, templateStatus, templateVersion]
  );

  const handleVerifyExport = useCallback(async () => {
    if (!templateName) throw new Error('No template loaded');
    const formData = form.getValues();
    await verifyExport(
      templateName,
      formData,
      'aasx',
      templateStatus,
      templateVersion
    );
  }, [templateName, form, templateStatus, templateVersion]);

  // Reset form
  const resetForm = useCallback(() => {
    if (schema) {
      const newDefaults = generateDefaultValues(schema);
      form.reset(newDefaults);
      setValidationResult(null);
    }
  }, [schema, form]);

  return {
    schema,
    form,
    loading,
    error,
    validating,
    validationResult,
    loadSchema,
    validate,
    exportAasx: handleExportAasx,
    exportJson: handleExportJson,
    exportPdf: handleExportPdf,
    verifyExport: handleVerifyExport,
    resetForm,
  };
}

export default useSubmodelForm;
