/**
 * Hook for managing PCF Calculator & Validator state.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { UseFormReturn } from 'react-hook-form';
import type { SubmodelUISchema } from '../../types/ui-schema';
import type { SubmodelFormData } from '../../types/aas-elements';
import type {
  EmissionFactor,
  PCFActivity,
  PCFCalculateResponse,
  PCFHealthResponse,
  PCFValidateResponse,
} from '../../types/pcf';
import { PCF_SEMANTIC_IDS } from '../../types/pcf';
import {
  calculatePCF,
  checkPCFHealth,
  searchEmissionFactors,
  validatePCF,
} from '../../services/pcfApi';
import {
  findPcfCO2eqPath,
  findPcfActivityList,
  buildActivityListItems,
  generateActivityId,
  findFieldPathInElementsByIdShort,
  findFieldPathInElementsBySemanticId,
  findProductCarbonFootprintContainer,
  pathToFormItemsPath,
  pathToFormPath,
} from './pcfUtils';

interface PCFWorkspace {
  activities: PCFActivity[];
  totalCo2eKg: number;
  warnings: string[];
  referenceUnit: string;
  referenceQuantity: string;
  publicationDate: string;
}

interface UsePCFPanelOptions {
  schema: SubmodelUISchema | null;
  form: UseFormReturn<SubmodelFormData>;
}

interface UsePCFPanelReturn {
  /** Current workspace state */
  workspace: PCFWorkspace;
  /** Validation result */
  validationResult: PCFValidateResponse | null;
  /** Loading state for calculation */
  calculating: boolean;
  /** Loading state for validation */
  validating: boolean;
  /** Loading state for factor search */
  searchingFactors: boolean;
  /** Emission factor search results */
  factorResults: EmissionFactor[];
  /** Emission factors metadata */
  factorsMeta: PCFHealthResponse['factors'] | null;
  /** Error message */
  error: string | null;
  /** Add a new activity */
  addActivity: (activity?: Partial<PCFActivity>) => void;
  /** Update an existing activity */
  updateActivity: (id: string, updates: Partial<PCFActivity>) => void;
  /** Remove an activity */
  removeActivity: (id: string) => void;
  /** Clear all activities */
  clearActivities: () => void;
  /** Calculate CO2e for all activities */
  calculate: () => Promise<void>;
  /** Validate PCF form data */
  validate: () => Promise<void>;
  /** Apply calculated total to form */
  applyToForm: () => void;
  /** Active ProductCarbonFootprint instance index */
  activeInstanceIndex: number;
  /** Total ProductCarbonFootprint instance count */
  instanceCount: number;
  /** Instance kind (list vs collection) */
  instanceKind: 'list' | 'collection' | null;
  /** Select a ProductCarbonFootprint instance */
  setActiveInstanceIndex: (index: number) => void;
  /** Reference impact unit for calculation */
  referenceUnit: string;
  /** Update reference impact unit */
  setReferenceUnit: (unit: string) => void;
  /** Quantity of measure for calculation */
  referenceQuantity: string;
  /** Update quantity of measure */
  setReferenceQuantity: (quantity: string) => void;
  /** Publication date */
  publicationDate: string;
  /** Update publication date */
  setPublicationDate: (date: string) => void;
  /** Life cycle phase count for the active instance */
  lifeCyclePhaseCount: number;
  /** Search emission factors */
  searchFactors: (query: string) => Promise<void>;
  /** Clear factor search results */
  clearFactorResults: () => void;
  /** Apply a factor to an activity */
  applyFactorToActivity: (activityId: string, factor: EmissionFactor) => void;
}

const DEFAULT_WORKSPACE: PCFWorkspace = {
  activities: [],
  totalCo2eKg: 0,
  warnings: [],
  referenceUnit: '',
  referenceQuantity: '',
  publicationDate: '',
};

/**
 * Hook for managing PCF calculator and validator state.
 */
export function usePCFPanel(options: UsePCFPanelOptions): UsePCFPanelReturn {
  const { schema, form } = options;

  const [workspace, setWorkspace] = useState<PCFWorkspace>(DEFAULT_WORKSPACE);
  const [activeInstanceIndex, setActiveInstanceIndex] = useState(0);
  const [instanceCount, setInstanceCount] = useState(1);
  const [lifeCyclePhaseCount, setLifeCyclePhaseCount] = useState(0);
  const [validationResult, setValidationResult] =
    useState<PCFValidateResponse | null>(null);
  const [calculating, setCalculating] = useState(false);
  const [validating, setValidating] = useState(false);
  const [searchingFactors, setSearchingFactors] = useState(false);
  const [factorResults, setFactorResults] = useState<EmissionFactor[]>([]);
  const [factorsMeta, setFactorsMeta] = useState<
    PCFHealthResponse['factors'] | null
  >(null);
  const [error, setError] = useState<string | null>(null);

  const instanceContainer = useMemo(
    () => findProductCarbonFootprintContainer(schema),
    [schema]
  );

  const instanceKind = instanceContainer?.kind ?? null;

  const fieldDefinitions: Record<
    string,
    { semanticId: string; idShorts: string[] }
  > = {
    PcfCO2eq: {
      semanticId: PCF_SEMANTIC_IDS.PcfCO2eq,
      idShorts: ['PcfCO2eq', 'PCFCo2eq'],
    },
    ReferenceImpactUnitForCalculation: {
      semanticId: PCF_SEMANTIC_IDS.ReferenceImpactUnitForCalculation,
      idShorts: ['ReferenceImpactUnitForCalculation'],
    },
    QuantityOfMeasureForCalculation: {
      semanticId: PCF_SEMANTIC_IDS.QuantityOfMeasureForCalculation,
      idShorts: ['QuantityOfMeasureForCalculation'],
    },
    PublicationDate: {
      semanticId: PCF_SEMANTIC_IDS.PublicationDate,
      idShorts: ['PublicationDate'],
    },
    LifeCyclePhases: {
      semanticId: PCF_SEMANTIC_IDS.LifeCyclePhases,
      idShorts: ['LifeCyclePhases'],
    },
  };

  const resolveFieldPath = useCallback(
    (fieldKey: keyof typeof fieldDefinitions): string | null => {
      if (!instanceContainer) return null;
      const definition = fieldDefinitions[fieldKey];
      const containerElements = [
        ...(instanceContainer.itemSchema.elements ?? []),
        ...(instanceContainer.itemSchema.statements ?? []),
      ];
      const bySemantic = findFieldPathInElementsBySemanticId(
        containerElements,
        definition.semanticId
      );
      const relativePath =
        bySemantic ||
        findFieldPathInElementsByIdShort(containerElements, definition.idShorts);
      if (!relativePath) return null;

      if (instanceContainer.kind === 'list') {
        return `${instanceContainer.path}[${activeInstanceIndex}].${relativePath}`;
      }

      return `${instanceContainer.path}.${relativePath}`;
    },
    [activeInstanceIndex, instanceContainer]
  );

  const pcfFieldPaths = useMemo(
    () => ({
      pcfCo2eq: resolveFieldPath('PcfCO2eq'),
      referenceUnit: resolveFieldPath('ReferenceImpactUnitForCalculation'),
      referenceQuantity: resolveFieldPath('QuantityOfMeasureForCalculation'),
      publicationDate: resolveFieldPath('PublicationDate'),
      lifeCyclePhases: resolveFieldPath('LifeCyclePhases'),
    }),
    [resolveFieldPath]
  );

  useEffect(() => {
    let active = true;
    if (!schema) return () => undefined;
    checkPCFHealth()
      .then((response) => {
        if (!active) return;
        setFactorsMeta(response.factors ?? null);
      })
      .catch(() => {
        if (!active) return;
        setFactorsMeta(null);
      });
    return () => {
      active = false;
    };
  }, [schema]);

  useEffect(() => {
    if (!instanceContainer) {
      setInstanceCount(1);
      setActiveInstanceIndex(0);
      return;
    }

    if (instanceContainer.kind === 'list') {
      const itemsPath = pathToFormItemsPath(instanceContainer.path);
      const items = (form.getValues as any)(itemsPath);
      const count = Array.isArray(items) ? items.length : 0;
      setInstanceCount(count);
      setActiveInstanceIndex((prev) => {
        if (count === 0) return 0;
        return Math.min(prev, count - 1);
      });
      return;
    }

    setInstanceCount(1);
    setActiveInstanceIndex(0);
  }, [form, instanceContainer]);

  useEffect(() => {
    const readValue = (path: string | null): string => {
      if (!path) return '';
      const value = (form.getValues as any)(pathToFormPath(path));
      if (value == null) return '';
      return String(value);
    };

    setWorkspace((prev) => ({
      ...prev,
      referenceUnit: readValue(pcfFieldPaths.referenceUnit),
      referenceQuantity: readValue(pcfFieldPaths.referenceQuantity),
      publicationDate: readValue(pcfFieldPaths.publicationDate),
    }));

    if (pcfFieldPaths.lifeCyclePhases) {
      const items = (form.getValues as any)(
        pathToFormItemsPath(pcfFieldPaths.lifeCyclePhases)
      );
      setLifeCyclePhaseCount(Array.isArray(items) ? items.length : 0);
    } else {
      setLifeCyclePhaseCount(0);
    }
  }, [form, pcfFieldPaths]);

  // Add a new activity
  const addActivity = useCallback((activity?: Partial<PCFActivity>) => {
    const newActivity: PCFActivity = {
      id: generateActivityId(),
      name: activity?.name ?? '',
      category: activity?.category ?? 'scope1',
      quantity: activity?.quantity ?? 0,
      unit: activity?.unit ?? 'kg',
      factor_value: activity?.factor_value ?? 0,
      factor_unit: activity?.factor_unit ?? 'kg CO2e/kg',
      factor_id: activity?.factor_id ?? null,
      factor_name: activity?.factor_name ?? null,
      factor_source: activity?.factor_source ?? null,
      factor_region: activity?.factor_region ?? null,
      factor_year: activity?.factor_year ?? null,
      co2e_kg: null,
    };

    setWorkspace((prev) => ({
      ...prev,
      activities: [...prev.activities, newActivity],
    }));
  }, []);

  // Update an existing activity
  const updateActivity = useCallback(
    (id: string, updates: Partial<PCFActivity>) => {
      setWorkspace((prev) => ({
        ...prev,
        activities: prev.activities.map((a) =>
          a.id === id ? { ...a, ...updates, co2e_kg: null } : a
        ),
      }));
    },
    []
  );

  // Remove an activity
  const removeActivity = useCallback((id: string) => {
    setWorkspace((prev) => ({
      ...prev,
      activities: prev.activities.filter((a) => a.id !== id),
      totalCo2eKg: 0,
    }));
  }, []);

  // Clear all activities
  const clearActivities = useCallback(() => {
    setWorkspace(DEFAULT_WORKSPACE);
    setValidationResult(null);
  }, []);

  // Calculate CO2e for all activities
  const calculate = useCallback(async () => {
    if (workspace.activities.length === 0) {
      setError('No activities to calculate');
      return;
    }

    setCalculating(true);
    setError(null);

    try {
      const response: PCFCalculateResponse = await calculatePCF({
        activities: workspace.activities,
      });

      setWorkspace((prev) => ({
        ...prev,
        activities: response.activities,
        totalCo2eKg: response.total_co2e_kg,
        warnings: response.warnings,
      }));
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Calculation failed';
      setError(message);
    } finally {
      setCalculating(false);
    }
  }, [workspace.activities]);

  // Validate PCF form data
  const validate = useCallback(async () => {
    if (!schema) {
      setError('No schema loaded');
      return;
    }

    setValidating(true);
    setError(null);

    try {
      const formData = form.getValues();
      const response: PCFValidateResponse = await validatePCF({
        form_data: formData as unknown as Record<string, unknown>,
        template_schema: schema as unknown as Record<string, unknown>,
      });

      setValidationResult(response);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Validation failed';
      setError(message);
    } finally {
      setValidating(false);
    }
  }, [schema, form]);

  // Apply calculated total to form
  const applyToForm = useCallback(() => {
    const hasCalculated =
      workspace.activities.length > 0 &&
      workspace.activities.every((activity) => activity.co2e_kg != null);
    if (!hasCalculated) {
      setError('Calculate all activities before applying to form');
      return;
    }

    if (!schema) {
      setError('No schema loaded');
      return;
    }

    const pcfPath = pcfFieldPaths.pcfCo2eq || findPcfCO2eqPath(schema);
    if (!pcfPath) {
      setError('Could not find PcfCO2eq field in schema');
      return;
    }

    const formPath = pathToFormPath(pcfPath);

    // Set the value in the form using deep path
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (form.setValue as any)(formPath, String(workspace.totalCo2eKg));

    const activityList = findPcfActivityList(schema);
    if (activityList) {
      const itemsPath = pathToFormItemsPath(activityList.path);
      const items = buildActivityListItems(
        workspace.activities,
        activityList.itemSchema
      );
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (form.setValue as any)(itemsPath, items, { shouldDirty: true });
    }

    const tracePayload = {
      generatedAt: new Date().toISOString(),
      totalCo2eKg: workspace.totalCo2eKg,
      warnings: workspace.warnings,
      activities: workspace.activities.map((activity) => ({
        id: activity.id,
        name: activity.name,
        category: activity.category,
        quantity: activity.quantity,
        unit: activity.unit,
        factor_value: activity.factor_value,
        factor_unit: activity.factor_unit,
        factor_id: activity.factor_id ?? null,
        factor_name: activity.factor_name ?? null,
        factor_source: activity.factor_source ?? null,
        factor_region: activity.factor_region ?? null,
        factor_year: activity.factor_year ?? null,
        co2e_kg: activity.co2e_kg ?? null,
      })),
    };

    // Persist trace payload in metadata for export/audit purposes
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (form.setValue as any)('metadata.pcf', tracePayload, {
      shouldDirty: true,
    });

    setError(null);
  }, [
    workspace.totalCo2eKg,
    workspace.activities,
    workspace.warnings,
    schema,
    form,
    pcfFieldPaths.pcfCo2eq,
  ]);

  const setReferenceUnit = useCallback(
    (unit: string) => {
      setWorkspace((prev) => ({
        ...prev,
        referenceUnit: unit,
      }));
      if (pcfFieldPaths.referenceUnit) {
        (form.setValue as any)(
          pathToFormPath(pcfFieldPaths.referenceUnit),
          unit,
          { shouldDirty: true }
        );
      }
    },
    [form, pcfFieldPaths.referenceUnit]
  );

  const setReferenceQuantity = useCallback(
    (quantity: string) => {
      setWorkspace((prev) => ({
        ...prev,
        referenceQuantity: quantity,
      }));
      if (pcfFieldPaths.referenceQuantity) {
        (form.setValue as any)(
          pathToFormPath(pcfFieldPaths.referenceQuantity),
          quantity,
          { shouldDirty: true }
        );
      }
    },
    [form, pcfFieldPaths.referenceQuantity]
  );

  const setPublicationDate = useCallback(
    (date: string) => {
      setWorkspace((prev) => ({
        ...prev,
        publicationDate: date,
      }));
      if (pcfFieldPaths.publicationDate) {
        (form.setValue as any)(
          pathToFormPath(pcfFieldPaths.publicationDate),
          date,
          { shouldDirty: true }
        );
      }
    },
    [form, pcfFieldPaths.publicationDate]
  );


  // Search emission factors
  const searchFactors = useCallback(async (query: string) => {
    setSearchingFactors(true);
    setError(null);

    try {
      const results = await searchEmissionFactors(query);
      setFactorResults(results);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Factor search failed';
      setError(message);
      setFactorResults([]);
    } finally {
      setSearchingFactors(false);
    }
  }, []);

  // Clear factor search results
  const clearFactorResults = useCallback(() => {
    setFactorResults([]);
  }, []);

  // Apply a factor to an activity
  const applyFactorToActivity = useCallback(
    (activityId: string, factor: EmissionFactor) => {
      setWorkspace((prev) => ({
        ...prev,
        activities: prev.activities.map((a) =>
          a.id === activityId
            ? {
                ...a,
                factor_value: factor.factor_value,
                factor_unit: factor.factor_unit,
                factor_source: factor.source,
                factor_id: factor.id,
                factor_name: factor.name,
                factor_region: factor.region ?? null,
                factor_year: factor.year ?? null,
                name: a.name || factor.name,
                co2e_kg: null, // Reset calculated value
              }
            : a
        ),
      }));
      // Clear results after selection
      setFactorResults([]);
    },
    []
  );

  return {
    workspace,
    validationResult,
    calculating,
    validating,
    searchingFactors,
    factorResults,
    factorsMeta,
    error,
    addActivity,
    updateActivity,
    removeActivity,
    clearActivities,
    calculate,
    validate,
    applyToForm,
    activeInstanceIndex,
    instanceCount,
    instanceKind,
    setActiveInstanceIndex,
    referenceUnit: workspace.referenceUnit,
    setReferenceUnit,
    referenceQuantity: workspace.referenceQuantity,
    setReferenceQuantity,
    publicationDate: workspace.publicationDate,
    setPublicationDate,
    lifeCyclePhaseCount,
    searchFactors,
    clearFactorResults,
    applyFactorToActivity,
  };
}

export default usePCFPanel;
