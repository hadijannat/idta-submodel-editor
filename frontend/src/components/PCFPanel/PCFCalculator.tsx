/**
 * PCF Calculator component for managing emission activities.
 *
 * Displays an activity table where users can:
 * - Add/remove emission activities
 * - Enter quantities and emission factors
 * - Search and select emission factors from a database
 * - Calculate total CO2e emissions
 * - Apply the result to the form's PcfCO2eq field
 */

import { useEffect, useState } from 'react';
import type {
  EmissionFactor,
  PCFActivity,
  PCFActivityCategory,
} from '../../types/pcf';
import './PCFCalculator.css';

interface PCFCalculatorProps {
  activities: PCFActivity[];
  totalCo2eKg: number;
  warnings: string[];
  calculating: boolean;
  searchingFactors: boolean;
  factorResults: EmissionFactor[];
  factorsMeta: {
    version?: string | null;
    sources?: string[];
    count?: number;
  } | null;
  onAddActivity: (activity?: Partial<PCFActivity>) => void;
  onUpdateActivity: (id: string, updates: Partial<PCFActivity>) => void;
  onRemoveActivity: (id: string) => void;
  onCalculate: () => Promise<void>;
  onApplyToForm: () => void;
  onSearchFactors: (query: string) => Promise<void>;
  onClearFactorResults: () => void;
  onApplyFactor: (activityId: string, factor: EmissionFactor) => void;
}

const CATEGORY_OPTIONS: { value: PCFActivityCategory; label: string }[] = [
  { value: 'scope1', label: 'Scope 1 (Direct)' },
  { value: 'scope2', label: 'Scope 2 (Energy)' },
  { value: 'scope3', label: 'Scope 3 (Indirect)' },
];

const UNIT_OPTIONS = ['kg', 't', 'kWh', 'MJ', 'km', 'tkm', 'L', 'm³'];

export default function PCFCalculator({
  activities,
  totalCo2eKg,
  warnings,
  calculating,
  searchingFactors,
  factorResults,
  factorsMeta,
  onAddActivity,
  onUpdateActivity,
  onRemoveActivity,
  onCalculate,
  onApplyToForm,
  onSearchFactors,
  onClearFactorResults,
  onApplyFactor,
}: PCFCalculatorProps) {
  // Track which activity is currently searching for factors
  const [searchingForActivityId, setSearchingForActivityId] = useState<
    string | null
  >(null);
  const [searchQuery, setSearchQuery] = useState('');

  const handleFieldChange = (
    id: string,
    field: keyof PCFActivity,
    value: string | number
  ) => {
    // Convert numeric fields
    if (field === 'quantity' || field === 'factor_value') {
      const numValue = parseFloat(value as string) || 0;
      onUpdateActivity(id, { [field]: numValue });
    } else {
      onUpdateActivity(id, { [field]: value });
    }
  };

  const handleOpenFactorSearch = (activityId: string) => {
    setSearchingForActivityId(activityId);
    setSearchQuery('');
  };

  const handleCloseFactorSearch = () => {
    setSearchingForActivityId(null);
    setSearchQuery('');
    onClearFactorResults();
  };

  const handleFactorSelect = (factor: EmissionFactor) => {
    if (searchingForActivityId) {
      onApplyFactor(searchingForActivityId, factor);
    }
    handleCloseFactorSearch();
  };

  const handleSearchChange = (query: string) => {
    setSearchQuery(query);
  };

  const hasActivities = activities.length > 0;
  const canApply =
    hasActivities && activities.every((activity) => activity.co2e_kg != null);

  useEffect(() => {
    if (!searchingForActivityId) return;
    const handle = setTimeout(() => {
      onSearchFactors(searchQuery);
    }, 300);
    return () => clearTimeout(handle);
  }, [searchQuery, searchingForActivityId, onSearchFactors]);

  return (
    <div className="pcf-calculator">
      <div className="pcf-calculator__header">
        <h3>CO₂e Calculator</h3>
        <p className="pcf-calculator__description">
          Add emission activities to calculate the total Product Carbon
          Footprint (PCF).
        </p>
        {factorsMeta && (factorsMeta.version || factorsMeta.count) && (
          <p className="pcf-calculator__meta">
            Factors dataset
            {factorsMeta.version ? ` v${factorsMeta.version}` : ''}
            {typeof factorsMeta.count === 'number'
              ? ` • ${factorsMeta.count} factors`
              : ''}
          </p>
        )}
      </div>

      {!hasActivities ? (
        <div className="pcf-calculator__empty">
          <p>No activities added yet.</p>
          <button
            type="button"
            className="pcf-calculator__btn pcf-calculator__btn--primary"
            onClick={() => onAddActivity()}
          >
            + Add Activity
          </button>
        </div>
      ) : (
        <>
          <div className="pcf-calculator__table-wrapper">
            <table className="pcf-calculator__table">
              <thead>
                <tr>
                  <th>Activity Name</th>
                  <th>Category</th>
                  <th>Quantity</th>
                  <th>Unit</th>
                  <th>Factor</th>
                  <th>Factor Unit</th>
                  <th>CO₂e (kg)</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {activities.map((activity) => (
                  <tr key={activity.id}>
                    <td>
                      <input
                        type="text"
                        value={activity.name}
                        onChange={(e) =>
                          handleFieldChange(activity.id, 'name', e.target.value)
                        }
                        placeholder="e.g., Electricity"
                        className="pcf-calculator__input"
                      />
                    </td>
                    <td>
                      <select
                        value={activity.category}
                        onChange={(e) =>
                          handleFieldChange(
                            activity.id,
                            'category',
                            e.target.value as PCFActivityCategory
                          )
                        }
                        className="pcf-calculator__select"
                      >
                        {CATEGORY_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <input
                        type="number"
                        value={activity.quantity}
                        onChange={(e) =>
                          handleFieldChange(
                            activity.id,
                            'quantity',
                            e.target.value
                          )
                        }
                        step="any"
                        className="pcf-calculator__input pcf-calculator__input--number"
                      />
                    </td>
                    <td>
                      <select
                        value={activity.unit}
                        onChange={(e) =>
                          handleFieldChange(activity.id, 'unit', e.target.value)
                        }
                        className="pcf-calculator__select pcf-calculator__select--narrow"
                      >
                        {UNIT_OPTIONS.map((u) => (
                          <option key={u} value={u}>
                            {u}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <div className="pcf-calculator__factor-cell">
                        <input
                          type="number"
                          value={activity.factor_value}
                          onChange={(e) =>
                            handleFieldChange(
                              activity.id,
                              'factor_value',
                              e.target.value
                            )
                          }
                          min="0"
                          step="any"
                          className="pcf-calculator__input pcf-calculator__input--number"
                        />
                        <button
                          type="button"
                          className="pcf-calculator__btn pcf-calculator__btn--search"
                          onClick={() => handleOpenFactorSearch(activity.id)}
                          title="Search emission factors"
                        >
                          🔍
                        </button>
                      </div>
                    </td>
                    <td>
                      <input
                        type="text"
                        value={activity.factor_unit}
                        onChange={(e) =>
                          handleFieldChange(
                            activity.id,
                            'factor_unit',
                            e.target.value
                          )
                        }
                        placeholder="kg CO2e/kg"
                        className="pcf-calculator__input"
                      />
                    </td>
                    <td className="pcf-calculator__result">
                      {activity.co2e_kg != null
                        ? activity.co2e_kg.toFixed(2)
                        : '—'}
                    </td>
                    <td>
                      <button
                        type="button"
                        className="pcf-calculator__btn pcf-calculator__btn--icon"
                        onClick={() => onRemoveActivity(activity.id)}
                        title="Remove activity"
                        aria-label="Remove"
                      >
                        ×
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="pcf-calculator__actions">
            <button
              type="button"
              className="pcf-calculator__btn pcf-calculator__btn--secondary"
              onClick={() => onAddActivity()}
            >
              + Add Activity
            </button>
          </div>
        </>
      )}

      {/* Emission Factor Search Modal */}
      {searchingForActivityId && (
        <div className="pcf-calculator__modal-overlay">
          <div className="pcf-calculator__modal">
            <div className="pcf-calculator__modal-header">
              <h4>Search Emission Factors</h4>
              <button
                type="button"
                className="pcf-calculator__btn pcf-calculator__btn--icon"
                onClick={handleCloseFactorSearch}
                aria-label="Close"
              >
                ×
              </button>
            </div>

            <div className="pcf-calculator__modal-search">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => handleSearchChange(e.target.value)}
                placeholder="Search by name, source, or region..."
                className="pcf-calculator__input pcf-calculator__input--search"
                autoFocus
              />
              {searchingFactors && (
                <span className="pcf-calculator__searching">Searching...</span>
              )}
            </div>

            <div className="pcf-calculator__modal-results">
              {factorResults.length === 0 && !searchingFactors ? (
                <p className="pcf-calculator__no-results">
                  No emission factors found.
                </p>
              ) : (
                <table className="pcf-calculator__factor-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Factor</th>
                      <th>Unit</th>
                      <th>Source</th>
                      <th>Region</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {factorResults.map((factor) => (
                      <tr key={factor.id}>
                        <td title={factor.name}>{factor.name}</td>
                        <td>{factor.factor_value}</td>
                        <td>{factor.factor_unit}</td>
                        <td>{factor.source}</td>
                        <td>{factor.region || '—'}</td>
                        <td>
                          <button
                            type="button"
                            className="pcf-calculator__btn pcf-calculator__btn--select"
                            onClick={() => handleFactorSelect(factor)}
                          >
                            Select
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}

      {warnings.length > 0 && (
        <div className="pcf-calculator__warnings">
          {warnings.map((w, i) => (
            <p key={i} className="pcf-calculator__warning">
              ⚠️ {w}
            </p>
          ))}
        </div>
      )}

      <div className="pcf-calculator__footer">
        <div className="pcf-calculator__total">
          <span className="pcf-calculator__total-label">Total:</span>
          <span className="pcf-calculator__total-value">
            {totalCo2eKg.toFixed(2)} kg CO₂e
          </span>
        </div>

        <div className="pcf-calculator__footer-actions">
          <button
            type="button"
            className="pcf-calculator__btn pcf-calculator__btn--primary"
            onClick={onCalculate}
            disabled={!hasActivities || calculating}
          >
            {calculating ? 'Calculating...' : 'Calculate'}
          </button>
          <button
            type="button"
            className="pcf-calculator__btn pcf-calculator__btn--success"
            onClick={onApplyToForm}
            disabled={!canApply}
            title={
              canApply
                ? 'Apply total to PcfCO2eq field'
                : 'Calculate all activities before applying'
            }
          >
            Apply to Form
          </button>
        </div>
      </div>
    </div>
  );
}
