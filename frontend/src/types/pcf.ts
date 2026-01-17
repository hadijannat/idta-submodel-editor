/**
 * Types for PCF (Product Carbon Footprint) Calculator & Validator.
 *
 * Mirrors backend schemas in app/schemas/pcf.py
 */

/** Activity category (GHG Protocol scope classification) */
export type PCFActivityCategory = 'scope1' | 'scope2' | 'scope3';

/** Validation rule severity */
export type PCFRuleSeverity = 'error' | 'warning';

/**
 * A single emission activity for CO2e calculation.
 */
export interface PCFActivity {
  id: string;
  name: string;
  category: PCFActivityCategory;
  quantity: number;
  unit: string;
  factor_value: number;
  factor_unit: string;
  factor_source?: string | null;
  co2e_kg?: number | null;
}

/**
 * Request to calculate CO2e from activities.
 */
export interface PCFCalculateRequest {
  activities: PCFActivity[];
}

/**
 * Response with calculated CO2e values.
 */
export interface PCFCalculateResponse {
  activities: PCFActivity[];
  total_co2e_kg: number;
  warnings: string[];
}

/**
 * A PCF-specific validation rule result.
 */
export interface PCFValidationRule {
  rule_id: string;
  field: string;
  severity: PCFRuleSeverity;
  message: string;
  code?: string | null;
}

/**
 * Request to validate PCF form data.
 */
export interface PCFValidateRequest {
  form_data: Record<string, unknown>;
  template_schema: Record<string, unknown>;
}

/**
 * Response from PCF validation.
 */
export interface PCFValidateResponse {
  valid: boolean;
  errors: PCFValidationRule[];
  warnings: PCFValidationRule[];
  completeness_score: number;
}

/**
 * An emission factor for CO2e calculation.
 */
export interface EmissionFactor {
  id: string;
  name: string;
  factor_value: number;
  factor_unit: string;
  source: string;
  region?: string | null;
  year?: number | null;
}

/**
 * PCF health check response.
 */
export interface PCFHealthResponse {
  status: string;
  services: {
    calculator: string;
    validator: string;
  };
}

// ============================================================================
// IDTA 02023 Semantic IDs for Carbon Footprint
// ============================================================================

/**
 * Semantic IDs for IDTA 02023 Carbon Footprint fields.
 * Used to identify PCF-specific fields in form schemas.
 */
export const PCF_SEMANTIC_IDS = {
  // Required fields (blocking errors)
  PcfCO2eq: '0173-1#02-ABG855#003',
  ReferenceImpactUnitForCalculation: '0173-1#02-ABG856#003',
  QuantityOfMeasureForCalculation: '0173-1#02-ABG857#003',
  PublicationDate:
    'https://admin-shell.io/idta/CarbonFootprint/PublicationDate/1/0',
  LifeCyclePhases:
    'https://admin-shell.io/idta/CarbonFootprint/LifeCyclePhases/1/0',

  // Recommended fields (warnings)
  PcfCalculationMethod: '0173-1#02-ABG854#003',
  ExpirationDate:
    'https://admin-shell.io/idta/CarbonFootprint/ExpirationDate/1/0',

  // Template identification
  CarbonFootprint:
    'https://admin-shell.io/idta/CarbonFootprint/CarbonFootprint/1/0',
} as const;

/**
 * Type for PCF semantic ID keys.
 */
export type PCFSemanticIdKey = keyof typeof PCF_SEMANTIC_IDS;
