/**
 * Hook for managing submodel form state with React Hook Form and Zod validation.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useForm, UseFormReturn } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import type { SubmodelUISchema, UIElementSchema } from '../types/ui-schema';
import type { SubmodelFormData, ElementFormData } from '../types/aas-elements';
import { getTemplateSchema, validateFormData, exportAsAasx, exportAsJson, exportAsPdf } from '../services/api';
import { isRequired } from '../types/aas-elements';

interface UseSubmodelFormOptions {
  /** Template name to load */
  templateName?: string;
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
  loadSchema: (templateName: string) => Promise<void>;
  /** Validate the form */
  validate: () => Promise<boolean>;
  /** Export as AASX */
  exportAasx: (filename?: string) => Promise<void>;
  /** Export as JSON */
  exportJson: (filename?: string) => Promise<void>;
  /** Export as PDF */
  exportPdf: (filename?: string) => Promise<void>;
  /** Reset form to default values */
  resetForm: () => void;
}

/**
 * Generate Zod schema from UI element schema.
 */
function generateZodSchema(element: UIElementSchema): z.ZodTypeAny {
  const required = isRequired(element.cardinality);

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

      return z.object({
        value: required ? propSchema : propSchema.optional().nullable(),
      });
    }

    case 'MultiLanguageProperty': {
      return z.object({
        value: z.record(z.string()).optional(),
      });
    }

    case 'SubmodelElementCollection': {
      const elementsSchema: Record<string, z.ZodTypeAny> = {};
      for (const child of element.elements || []) {
        elementsSchema[child.idShort] = generateZodSchema(child);
      }
      return z.object({
        elements: z.object(elementsSchema),
      });
    }

    case 'SubmodelElementList': {
      const itemSchema = element.itemTemplate
        ? generateZodSchema(element.itemTemplate)
        : z.any();
      const minItems = element.cardinality === '[1..*]' ? 1 : 0;
      return z.object({
        items: z.array(itemSchema).min(minItems),
      });
    }

    case 'File': {
      return z.object({
        value: required ? z.string().min(1) : z.string().optional(),
        contentType: z.string().optional(),
      });
    }

    case 'Range': {
      const valueType = element.valueType || 'xs:double';
      const numSchema = valueType.includes('int')
        ? z.coerce.number().int()
        : z.coerce.number();

      return z.object({
        min: required ? numSchema : numSchema.optional().nullable(),
        max: required ? numSchema : numSchema.optional().nullable(),
      });
    }

    case 'ReferenceElement': {
      return z.object({
        value: required ? z.string().min(1) : z.string().optional(),
      });
    }

    case 'Entity': {
      const statementsSchema: Record<string, z.ZodTypeAny> = {};
      for (const stmt of element.statements || []) {
        statementsSchema[stmt.idShort] = generateZodSchema(stmt);
      }
      return z.object({
        globalAssetId: z.string().optional(),
        statements: z.object(statementsSchema),
      });
    }

    default:
      return z.any();
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

  return { elements };
}

/**
 * Generate default value for a single element.
 */
function generateElementDefaults(element: UIElementSchema): ElementFormData {
  switch (element.modelType) {
    case 'Property':
      return { value: element.value ?? '' };

    case 'MultiLanguageProperty':
      return {
        value: (element.value as Record<string, string>) ?? {},
      };

    case 'SubmodelElementCollection': {
      const childElements: Record<string, ElementFormData> = {};
      for (const child of element.elements || []) {
        childElements[child.idShort] = generateElementDefaults(child);
      }
      return { elements: childElements };
    }

    case 'SubmodelElementList': {
      const items: ElementFormData[] = [];
      for (const item of element.items || []) {
        items.push(generateElementDefaults(item));
      }
      return { items };
    }

    case 'File':
      return {
        value: element.value ?? '',
        contentType: element.contentType ?? '',
      };

    case 'Range':
      return {
        min: element.min ?? '',
        max: element.max ?? '',
      };

    case 'ReferenceElement':
      return { value: element.value ?? '' };

    case 'Entity': {
      const statements: Record<string, ElementFormData> = {};
      for (const stmt of element.statements || []) {
        statements[stmt.idShort] = generateElementDefaults(stmt);
      }
      return {
        globalAssetId: element.globalAssetId ?? '',
        statements,
      };
    }

    default:
      return { value: element.value ?? '' };
  }
}

/**
 * Hook for managing submodel form with validation.
 */
export function useSubmodelForm(
  options: UseSubmodelFormOptions = {}
): UseSubmodelFormReturn {
  const { templateName, initialSchema, onSubmit } = options;

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
  const loadSchema = useCallback(async (name: string) => {
    setLoading(true);
    setError(null);

    try {
      const loadedSchema = await getTemplateSchema(name);
      setSchema(loadedSchema);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load schema';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Load on mount if templateName provided
  useEffect(() => {
    if (templateName && !initialSchema) {
      loadSchema(templateName);
    }
  }, [templateName, initialSchema, loadSchema]);

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
      const result = await validateFormData(templateName, formData);

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
  }, [schema, templateName, form]);

  // Export functions
  const handleExportAasx = useCallback(
    async (filename?: string) => {
      if (!templateName) throw new Error('No template loaded');
      const formData = form.getValues();
      await exportAsAasx(templateName, formData, filename);
    },
    [templateName, form]
  );

  const handleExportJson = useCallback(
    async (filename?: string) => {
      if (!templateName) throw new Error('No template loaded');
      const formData = form.getValues();
      await exportAsJson(templateName, formData, filename);
    },
    [templateName, form]
  );

  const handleExportPdf = useCallback(
    async (filename?: string) => {
      if (!templateName) throw new Error('No template loaded');
      const formData = form.getValues();
      await exportAsPdf(templateName, formData, filename);
    },
    [templateName, form]
  );

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
    resetForm,
  };
}

export default useSubmodelForm;
