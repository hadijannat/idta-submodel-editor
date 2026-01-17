/**
 * PCFCard - IDTA 02023 Product Carbon Footprint visualization.
 *
 * Renders a CO2e metric display with optional pie chart breakdown
 * showing lifecycle phase contributions.
 */

import type { SubmodelUISchema } from '../../../types/ui-schema';
import type { SubmodelFormData } from '../../../types/aas-elements';
import {
  extractLangStringValue,
  extractPrimitiveValue,
  formatValue,
  isProvided,
  parseStrictNumber,
} from '../utils/valueExtractors';
import {
  collectResolvedContexts,
  ElementMatcher,
  findMatchingElements,
  resolveSchemaElements,
} from '../utils/schemaIndex';
import { buildPieSlices } from '../utils/pieChart';
import { usePassportI18n } from '../i18n';
import type { TranslationKey } from '../i18n';

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

const TOTAL_MATCH: ElementMatcher = {
  semanticIdPatterns: [
    /0173-1#02-ABG855#001/i,
    /pcfco2eq/i,
    /gwptotal/i,
    /co2eq/i,
  ],
  idShortPatterns: [/PCFCO2eq/i, /PCFGWPTotal/i, /^CO2eq$/i],
  modelTypes: ['Property', 'Range'],
};

const REFERENCE_MATCH: ElementMatcher = {
  semanticIdPatterns: [
    /0173-1#02-ABG856#001/i,
    /referencevalue/i,
    /declaredunit/i,
  ],
  idShortPatterns: [/PCFReferenceValueForCalculation/i, /DeclaredUnit/i],
  modelTypes: ['Property', 'MultiLanguageProperty'],
};

const METHOD_MATCH: ElementMatcher = {
  semanticIdPatterns: [/0173-1#02-ABG854#001/i, /calculationmethod/i],
  idShortPatterns: [/PCFCalculationMethod/i, /CalculationMethod/i],
  modelTypes: ['Property', 'MultiLanguageProperty'],
};

const PHASE_MATCH: ElementMatcher = {
  semanticIdPatterns: [/0173-1#02-ABG858#001/i, /lifecyclephase/i, /life cycle phase/i],
  idShortPatterns: [/PCFLifeCyclePhase/i, /LifeCyclePhase/i, /Phase/i],
  modelTypes: ['Property', 'MultiLanguageProperty'],
};

const VALUE_MATCH: ElementMatcher = {
  semanticIdPatterns: [/0173-1#02-ABG855#001/i, /co2eq/i, /gwp/i],
  idShortPatterns: [/PCFCO2eq/i, /CO2eq/i, /GWP/i],
  modelTypes: ['Property', 'Range'],
};

/**
 * Phase code to translation key mapping.
 */
const PHASE_KEYS: Record<string, TranslationKey> = {
  A1: 'pcf.phases.A1',
  A2: 'pcf.phases.A2',
  A3: 'pcf.phases.A3',
  'A1-A3': 'pcf.phases.A1-A3',
  A4: 'pcf.phases.A4',
  A5: 'pcf.phases.A5',
  B1: 'pcf.phases.B1',
  B2: 'pcf.phases.B2',
  B3: 'pcf.phases.B3',
  B4: 'pcf.phases.B4',
  B5: 'pcf.phases.B5',
  B6: 'pcf.phases.B6',
  B7: 'pcf.phases.B7',
  C1: 'pcf.phases.C1',
  C2: 'pcf.phases.C2',
  C3: 'pcf.phases.C3',
  C4: 'pcf.phases.C4',
  D: 'pcf.phases.D',
};

/**
 * Map life cycle phase codes to readable names.
 */
function getPhaseLabel(
  code: string | number | boolean | undefined,
  t: (key: TranslationKey) => string
): string {
  if (!code) return t('pcf.unknownPhase');
  const codeStr = String(code);

  const translationKey = PHASE_KEYS[codeStr];
  if (translationKey) {
    return t(translationKey);
  }

  return codeStr;
}

function formatNumber(value: number): string {
  if (value >= 1000) {
    return value.toLocaleString(undefined, { maximumFractionDigits: 1 });
  }
  if (value >= 1) {
    return value.toFixed(2);
  }
  return value.toFixed(4);
}

function findFirstNumber(
  resolved: ReturnType<typeof resolveSchemaElements>,
  matcher: Parameters<typeof findMatchingElements>[1]
): { value?: number; unit?: string } {
  const matches = findMatchingElements(resolved, matcher);
  for (const match of matches) {
    const primitive = extractPrimitiveValue(match.data);
    const num = parseStrictNumber(primitive);
    if (num !== undefined) {
      return {
        value: num,
        unit: match.schema.unit ?? undefined,
      };
    }
  }
  return {};
}

function findFirstString(
  resolved: ReturnType<typeof resolveSchemaElements>,
  matcher: Parameters<typeof findMatchingElements>[1]
): string | undefined {
  const matches = findMatchingElements(resolved, matcher);
  for (const match of matches) {
    const value =
      extractLangStringValue(match.data?.value ?? match.data, ['en', 'de']) ??
      extractPrimitiveValue(match.data);
    if (isProvided(value)) {
      return formatValue(value);
    }
  }
  return undefined;
}

function extractPhaseBreakdown(
  contexts: ReturnType<typeof collectResolvedContexts>,
  t: (key: TranslationKey) => string
): { phases: LifeCyclePhase[]; unit?: string } {
  const phaseMap = new Map<string, number>();
  const orderedLabels: string[] = [];
  let unit: string | undefined;

  contexts.forEach((context) => {
    const phaseCandidates = findMatchingElements(context.elements, PHASE_MATCH);
    const valueCandidates = findMatchingElements(context.elements, VALUE_MATCH);

    let phaseValue: string | undefined;
    for (const candidate of phaseCandidates) {
      const raw =
        extractLangStringValue(candidate.data?.value ?? candidate.data, ['en', 'de']) ??
        extractPrimitiveValue(candidate.data);
      if (isProvided(raw)) {
        phaseValue = String(raw);
        break;
      }
    }

    let numericValue: number | undefined;
    for (const candidate of valueCandidates) {
      const raw = extractPrimitiveValue(candidate.data);
      const num = parseStrictNumber(raw);
      if (num !== undefined) {
        numericValue = num;
        unit = unit ?? candidate.schema.unit ?? undefined;
        break;
      }
    }

    if (!phaseValue || numericValue === undefined) return;
    const label = getPhaseLabel(phaseValue, t);

    if (!phaseMap.has(label)) {
      orderedLabels.push(label);
    }
    phaseMap.set(label, (phaseMap.get(label) ?? 0) + numericValue);
  });

  return {
    phases: orderedLabels
    .map((label, index) => ({
      name: label,
      value: phaseMap.get(label) ?? 0,
      color: PHASE_COLORS[index % PHASE_COLORS.length],
    }))
    .filter((phase) => phase.value > 0),
    unit,
  };
}

/**
 * PCFCard component.
 */
export default function PCFCard({ schema, formData }: PCFCardProps) {
  const { t } = usePassportI18n();
  const resolvedElements = resolveSchemaElements(schema, formData);
  const contexts = collectResolvedContexts(schema, formData);

  const totalResult = findFirstNumber(resolvedElements, TOTAL_MATCH);
  const reference = findFirstString(resolvedElements, REFERENCE_MATCH);
  const method = findFirstString(resolvedElements, METHOD_MATCH);
  const phaseBreakdown = extractPhaseBreakdown(contexts, t);
  const phases = phaseBreakdown.phases;

  const derivedTotal = phases.reduce((sum, phase) => sum + phase.value, 0);
  const total = totalResult.value ?? (phases.length > 0 ? derivedTotal : undefined);
  const unit = totalResult.unit ?? phaseBreakdown.unit;
  const hasTotal = total !== undefined;
  const hasPhases = phases.length > 0;
  const totalSource = totalResult.value !== undefined ? 'explicit' : 'derived';

  const pieSlices = hasPhases
    ? buildPieSlices(
        phases.map((phase) => ({
          label: phase.name,
          value: phase.value,
          color: phase.color,
        }))
      )
    : [];
  const pieSummary = pieSlices
    .map((slice) => `${slice.label} ${slice.percentage.toFixed(1)}%`)
    .join(', ');

  if (!hasTotal) {
    return (
      <div className="passport-card pcf-card">
        <div className="pcf-header">
          <h2>{t('pcf.title')}</h2>
          <p>{schema.idShort}</p>
        </div>
        <div className="pcf-empty">
          <p>{t('pcf.emptyMessage')}</p>
          <p>{t('pcf.emptyHint')}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="passport-card pcf-card">
      {/* Header */}
      <div className="pcf-header">
        <h2>{t('pcf.title')}</h2>
        <p>{schema.idShort}</p>
      </div>

      {/* Main CO2eq metric */}
      <div className="pcf-main-metric">
        <span className="pcf-metric-label">{t('pcf.totalCo2e')}</span>
        <span className="pcf-co2-value">
          {formatNumber(total!)}
          {unit && <span className="pcf-co2-unit">{unit}</span>}
        </span>
        {reference && <p className="pcf-reference">{t('pcf.perUnit', { unit: reference })}</p>}
        {hasTotal && totalSource === 'derived' && (
          <p className="pcf-derivation-note">{t('pcf.derivedNote')}</p>
        )}
      </div>

      {/* Pie chart section (only if phases available) */}
      {hasPhases && (
        <div className="pcf-chart-section">
          <div
            className="pcf-pie-chart"
            role="img"
            aria-label={
              pieSummary
                ? t('pcf.chartAriaLabelWithBreakdown', { breakdown: pieSummary })
                : t('pcf.chartAriaLabel')
            }
          >
            <svg viewBox="0 0 160 160" aria-hidden="true">
              {pieSlices.map((slice) => (
                <path key={slice.label} d={slice.path} fill={slice.color} />
              ))}
              <circle cx="80" cy="80" r="42" fill="white" />
            </svg>
          </div>
          <div className="pcf-legend">
            {phases.map((phase) => (
              <div key={phase.name} className="pcf-legend-item">
                <span
                  className="pcf-legend-color"
                  style={{ backgroundColor: phase.color }}
                />
                <span className="pcf-legend-label">{phase.name}</span>
                <span className="pcf-legend-value">
                  {formatNumber(phase.value)}
                  {unit ? ` ${unit}` : ''}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {!hasPhases && (
        <div className="pcf-breakdown-missing">
          {t('pcf.breakdownMissing')}
        </div>
      )}

      {/* Details section */}
      <div className="pcf-details">
        <div className="pcf-details-grid">
          {method && (
            <div className="pcf-detail-item">
              <span className="pcf-detail-label">{t('pcf.calculationMethod')}</span>
              <span className="pcf-detail-value">{method}</span>
            </div>
          )}
          {reference && (
            <div className="pcf-detail-item">
              <span className="pcf-detail-label">{t('pcf.referenceUnit')}</span>
              <span className="pcf-detail-value">{reference}</span>
            </div>
          )}
        </div>

        {/* Accessible data table */}
        {hasPhases && (
          <table className="pcf-data-table">
            <caption className="visually-hidden">
              {t('pcf.chartAriaLabel')}
            </caption>
            <thead>
              <tr>
                <th scope="col">{t('pcf.lifecyclePhase')}</th>
                <th scope="col" className="value-cell">
                  {t('common.co2e')}{unit ? ` (${unit})` : ''}
                </th>
              </tr>
            </thead>
            <tbody>
              {phases.map((phase) => (
                <tr key={phase.name}>
                  <td>{phase.name}</td>
                  <td className="value-cell">{formatNumber(phase.value)}</td>
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
