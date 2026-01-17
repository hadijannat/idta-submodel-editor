/**
 * Hook for managing PCF Calculator & Validator state.
 */

import { useCallback, useState } from 'react';
import type { UseFormReturn } from 'react-hook-form';
import type { SubmodelUISchema } from '../../types/ui-schema';
import type { SubmodelFormData } from '../../types/aas-elements';
import type {
  EmissionFactor,
  PCFActivity,
  PCFCalculateResponse,
  PCFValidateResponse,
} from '../../types/pcf';
import {
  calculatePCF,
  searchEmissionFactors,
  validatePCF,
} from '../../services/pcfApi';
import {
  findPcfCO2eqPath,
  generateActivityId,
  pathToFormPath,
} from './pcfUtils';

interface PCFWorkspace {
  activities: PCFActivity[];
  totalCo2eKg: number;
  warnings: string[];
  declaredUnit: string;
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
  /** Set declared unit */
  setDeclaredUnit: (unit: string) => void;
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
  declaredUnit: 'kg CO2e / piece',
};

/**
 * Hook for managing PCF calculator and validator state.
 */
export function usePCFPanel(options: UsePCFPanelOptions): UsePCFPanelReturn {
  const { schema, form } = options;

  const [workspace, setWorkspace] = useState<PCFWorkspace>(DEFAULT_WORKSPACE);
  const [validationResult, setValidationResult] =
    useState<PCFValidateResponse | null>(null);
  const [calculating, setCalculating] = useState(false);
  const [validating, setValidating] = useState(false);
  const [searchingFactors, setSearchingFactors] = useState(false);
  const [factorResults, setFactorResults] = useState<EmissionFactor[]>([]);
  const [error, setError] = useState<string | null>(null);

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
      factor_source: activity?.factor_source ?? null,
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
    if (workspace.totalCo2eKg === 0) {
      setError('Calculate first before applying to form');
      return;
    }

    if (!schema) {
      setError('No schema loaded');
      return;
    }

    const pcfPath = findPcfCO2eqPath(schema);
    if (!pcfPath) {
      setError('Could not find PcfCO2eq field in schema');
      return;
    }

    const formPath = pathToFormPath(pcfPath);

    // Set the value in the form using deep path
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (form.setValue as any)(formPath, String(workspace.totalCo2eKg));

    setError(null);
  }, [workspace.totalCo2eKg, schema, form]);

  // Set declared unit
  const setDeclaredUnit = useCallback((unit: string) => {
    setWorkspace((prev) => ({
      ...prev,
      declaredUnit: unit,
    }));
  }, []);

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
    error,
    addActivity,
    updateActivity,
    removeActivity,
    clearActivities,
    calculate,
    validate,
    applyToForm,
    setDeclaredUnit,
    searchFactors,
    clearFactorResults,
    applyFactorToActivity,
  };
}

export default usePCFPanel;
