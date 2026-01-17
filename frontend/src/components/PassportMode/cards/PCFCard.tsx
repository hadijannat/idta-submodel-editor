/**
 * PCFCard - IDTA 02023 Product Carbon Footprint visualization.
 *
 * Renders a CO2e metric display with optional pie chart breakdown
 * showing lifecycle phase contributions.
 */

import type { SubmodelUISchema } from '../../../types/ui-schema';
import type { SubmodelFormData, ElementFormData } from '../../../types/aas-elements';
import {
  extractNumber,
  extractPrimitive,
  extractCollection,
  extractList,
  isProvided,
} from '../utils/valueExtractors';

interface PCFCardProps {
  schema: SubmodelUISchema;
  formData: SubmodelFormData | undefined;
}

/**
 * Life cycle phase data for pie chart.
 */
interface LifeCyclePhase {
  name: string;
  value: number;
  color: string;
}

/**
 * Colors for life cycle phases (CSS variables).
 */
const PHASE_COLORS = [
  '#059669', // Primary green
  '#10b981', // Secondary green
  '#34d399', // Tertiary green
  '#6ee7b7', // Light green
  '#a7f3d0', // Very light green
  '#047857', // Dark green
];

/**
 * Map life cycle phase codes to readable names.
 */
function getPhaseLabel(code: string | number | boolean | undefined): string {
  if (!code) return 'Unknown';
  const codeStr = String(code);

  const mapping: Record<string, string> = {
    A1: 'Raw Material Supply',
    A2: 'Transport',
    A3: 'Manufacturing',
    'A1-A3': 'Cradle to Gate',
    A4: 'Distribution',
    A5: 'Installation',
    B1: 'Use',
    B2: 'Maintenance',
    B3: 'Repair',
    B4: 'Replacement',
    B5: 'Refurbishment',
    B6: 'Operational Energy',
    B7: 'Operational Water',
    C1: 'Deconstruction',
    C2: 'Transport (EoL)',
    C3: 'Waste Processing',
    C4: 'Disposal',
    D: 'Benefits & Loads',
  };

  return mapping[codeStr] || codeStr;
}

/**
 * Try to find the main PCF collection which contains the carbon footprint data.
 */
function findPCFData(formData: SubmodelFormData | undefined): {
  co2eq: number | undefined;
  reference: string | undefined;
  method: string | undefined;
  phases: LifeCyclePhase[];
} {
  const result = {
    co2eq: undefined as number | undefined,
    reference: undefined as string | undefined,
    method: undefined as string | undefined,
    phases: [] as LifeCyclePhase[],
  };

  if (!formData) return result;

  // Try various paths where PCF data might be located
  const pcfPaths = [
    'elements.ProductCarbonFootprint',
    'elements.CarbonFootprint',
    'elements.PCF',
    'elements',
  ];

  for (const basePath of pcfPaths) {
    // Try to get the collection or list
    const collection = extractCollection(formData, basePath);
    const list = extractList(formData, `${basePath}.items`);

    if (collection) {
      // Look for PCF values in collection
      const pcfResult = extractPCFFromCollection(collection);
      if (pcfResult.co2eq !== undefined) {
        return pcfResult;
      }
    }

    if (list && list.length > 0) {
      // If it's a list, use the first item or aggregate
      const firstItem = list[0];
      if (firstItem && typeof firstItem === 'object') {
        const pcfResult = extractPCFFromItem(firstItem);
        if (pcfResult.co2eq !== undefined) {
          return pcfResult;
        }
      }
    }
  }

  // Direct extraction from root elements
  result.co2eq = extractNumber(formData, 'elements.PCFCO2eq.value') ??
    extractNumber(formData, 'elements.PCFCO2eq') ??
    extractNumber(formData, 'elements.PCFGWPTotal.value') ??
    extractNumber(formData, 'elements.CO2eq');

  result.reference = String(
    extractPrimitive(formData, 'elements.PCFReferenceValueForCalculation.value') ??
    extractPrimitive(formData, 'elements.PCFReferenceValueForCalculation') ??
    extractPrimitive(formData, 'elements.DeclaredUnit') ??
    ''
  ) || undefined;

  result.method = String(
    extractPrimitive(formData, 'elements.PCFCalculationMethod.value') ??
    extractPrimitive(formData, 'elements.PCFCalculationMethod') ??
    extractPrimitive(formData, 'elements.CalculationMethod') ??
    ''
  ) || undefined;

  return result;
}

/**
 * Extract PCF data from a collection.
 */
function extractPCFFromCollection(
  collection: Record<string, ElementFormData>
): ReturnType<typeof findPCFData> {
  const result = {
    co2eq: undefined as number | undefined,
    reference: undefined as string | undefined,
    method: undefined as string | undefined,
    phases: [] as LifeCyclePhase[],
  };

  // Look through collection keys
  for (const [key, value] of Object.entries(collection)) {
    if (!value || typeof value !== 'object') continue;

    const keyLower = key.toLowerCase();

    // CO2eq value
    if (keyLower.includes('co2eq') || keyLower.includes('gwptotal')) {
      const numVal =
        typeof value === 'object' && 'value' in value
          ? Number(value.value)
          : typeof value === 'number'
            ? value
            : undefined;
      if (numVal !== undefined && !isNaN(numVal)) {
        result.co2eq = numVal;
      }
    }

    // Reference unit
    if (keyLower.includes('reference') || keyLower.includes('declaredunit')) {
      const strVal =
        typeof value === 'object' && 'value' in value
          ? String(value.value)
          : String(value);
      if (isProvided(strVal)) {
        result.reference = strVal;
      }
    }

    // Calculation method
    if (keyLower.includes('calculationmethod')) {
      const strVal =
        typeof value === 'object' && 'value' in value
          ? String(value.value)
          : String(value);
      if (isProvided(strVal)) {
        result.method = strVal;
      }
    }
  }

  return result;
}

/**
 * Extract PCF data from a list item.
 */
function extractPCFFromItem(item: ElementFormData): ReturnType<typeof findPCFData> {
  const result = {
    co2eq: undefined as number | undefined,
    reference: undefined as string | undefined,
    method: undefined as string | undefined,
    phases: [] as LifeCyclePhase[],
  };

  if (!item || typeof item !== 'object') return result;

  // Check elements property
  if ('elements' in item && typeof item.elements === 'object') {
    return extractPCFFromCollection(
      item.elements as Record<string, ElementFormData>
    );
  }

  // Check direct properties
  for (const [key, value] of Object.entries(item)) {
    if (key === 'elements' || key === 'items') continue;

    const keyLower = key.toLowerCase();
    if (keyLower.includes('co2eq') || keyLower.includes('gwptotal')) {
      const numVal =
        typeof value === 'object' && value !== null && 'value' in value
          ? Number((value as { value: unknown }).value)
          : typeof value === 'number'
            ? value
            : undefined;
      if (numVal !== undefined && !isNaN(numVal)) {
        result.co2eq = numVal;
      }
    }
  }

  return result;
}

/**
 * Generate CSS for conic-gradient pie chart.
 */
function generatePieGradient(phases: LifeCyclePhase[]): string {
  if (phases.length === 0) return 'transparent';

  const total = phases.reduce((sum, p) => sum + p.value, 0);
  if (total === 0) return 'transparent';

  let currentAngle = 0;
  const gradientParts: string[] = [];

  for (const phase of phases) {
    const percentage = (phase.value / total) * 100;
    const endAngle = currentAngle + percentage;
    gradientParts.push(`${phase.color} ${currentAngle}% ${endAngle}%`);
    currentAngle = endAngle;
  }

  return `conic-gradient(${gradientParts.join(', ')})`;
}

/**
 * PCFCard component.
 */
export default function PCFCard({ schema, formData }: PCFCardProps) {
  const pcfData = findPCFData(formData);
  const hasCO2eq = pcfData.co2eq !== undefined;
  const hasPhases = pcfData.phases.length > 0;

  // Format CO2eq with appropriate precision
  const formatCO2 = (value: number): string => {
    if (value >= 1000) {
      return value.toLocaleString(undefined, { maximumFractionDigits: 1 });
    }
    if (value >= 1) {
      return value.toFixed(2);
    }
    return value.toFixed(4);
  };

  if (!hasCO2eq) {
    return (
      <div className="passport-card pcf-card">
        <div className="pcf-header">
          <h2>Product Carbon Footprint</h2>
          <p>{schema.idShort}</p>
        </div>
        <div className="pcf-empty">
          <p>No carbon footprint data entered yet.</p>
          <p>Switch to Editor mode to fill in PCF values.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="passport-card pcf-card">
      {/* Header */}
      <div className="pcf-header">
        <h2>Product Carbon Footprint</h2>
        <p>{schema.idShort}</p>
      </div>

      {/* Main CO2eq metric */}
      <div className="pcf-main-metric">
        <span className="pcf-co2-value">
          {formatCO2(pcfData.co2eq!)}
          <span className="pcf-co2-unit">kg CO₂eq</span>
        </span>
        {pcfData.reference && (
          <p className="pcf-reference">per {pcfData.reference}</p>
        )}
      </div>

      {/* Pie chart section (only if phases available) */}
      {hasPhases && (
        <div className="pcf-chart-section">
          <div
            className="pcf-pie-chart"
            style={{ background: generatePieGradient(pcfData.phases) }}
            role="img"
            aria-label="Carbon footprint breakdown by lifecycle phase"
          />
          <div className="pcf-legend">
            {pcfData.phases.map((phase, index) => (
              <div key={index} className="pcf-legend-item">
                <span
                  className="pcf-legend-color"
                  style={{ backgroundColor: phase.color }}
                />
                <span className="pcf-legend-label">{phase.name}</span>
                <span className="pcf-legend-value">
                  {formatCO2(phase.value)} kg
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Details section */}
      <div className="pcf-details">
        <div className="pcf-details-grid">
          {pcfData.method && (
            <div className="pcf-detail-item">
              <span className="pcf-detail-label">Calculation Method</span>
              <span className="pcf-detail-value">{pcfData.method}</span>
            </div>
          )}
          {pcfData.reference && (
            <div className="pcf-detail-item">
              <span className="pcf-detail-label">Reference Unit</span>
              <span className="pcf-detail-value">{pcfData.reference}</span>
            </div>
          )}
        </div>

        {/* Accessible data table */}
        {hasPhases && (
          <table className="pcf-data-table">
            <caption className="visually-hidden">
              Carbon footprint breakdown by lifecycle phase
            </caption>
            <thead>
              <tr>
                <th scope="col">Lifecycle Phase</th>
                <th scope="col" className="value-cell">
                  CO₂eq (kg)
                </th>
              </tr>
            </thead>
            <tbody>
              {pcfData.phases.map((phase, index) => (
                <tr key={index}>
                  <td>{phase.name}</td>
                  <td className="value-cell">{formatCO2(phase.value)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// Export for testing
// eslint-disable-next-line react-refresh/only-export-components
export { getPhaseLabel, PHASE_COLORS };
