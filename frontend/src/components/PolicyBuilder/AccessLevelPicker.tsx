/**
 * AccessLevelPicker - Radio button picker for full/selective/time-limited access.
 *
 * Allows users to choose between different access scopes and configure
 * time-based restrictions for policies.
 */

import React from 'react';

export type AccessScope = 'full' | 'selective' | 'time-limited';

interface AccessLevelPickerProps {
  /** Current access scope */
  scope: AccessScope;
  /** Callback when scope changes */
  onScopeChange: (scope: AccessScope) => void;
  /** Valid from date (ISO string) */
  validFrom: string | null;
  /** Valid until date (ISO string) */
  validUntil: string | null;
  /** Callback when valid from changes */
  onValidFromChange: (date: string | null) => void;
  /** Callback when valid until changes */
  onValidUntilChange: (date: string | null) => void;
  /** Whether element selection is enabled (for selective scope) */
  hasElementSelection?: boolean;
  /** Number of selected elements */
  selectedElementCount?: number;
}

interface AccessOption {
  scope: AccessScope;
  name: string;
  description: string;
}

const accessOptions: AccessOption[] = [
  {
    scope: 'full',
    name: 'Full Access',
    description: 'Grant access to all submodel elements',
  },
  {
    scope: 'selective',
    name: 'Selective Access',
    description: 'Grant access only to selected elements',
  },
  {
    scope: 'time-limited',
    name: 'Time-Limited Access',
    description: 'Grant access with time restrictions',
  },
];

/**
 * AccessLevelPicker component
 */
export const AccessLevelPicker: React.FC<AccessLevelPickerProps> = ({
  scope,
  onScopeChange,
  validFrom,
  validUntil,
  onValidFromChange,
  onValidUntilChange,
  hasElementSelection = false,
  selectedElementCount = 0,
}) => {
  const handleDateChange = (
    field: 'from' | 'until',
    value: string
  ) => {
    if (field === 'from') {
      onValidFromChange(value || null);
    } else {
      onValidUntilChange(value || null);
    }
  };

  return (
    <div className="access-level-picker">
      {accessOptions.map((option) => (
        <div key={option.scope}>
          <label
            className={`access-level-picker__option ${
              scope === option.scope ? 'access-level-picker__option--selected' : ''
            }`}
          >
            <input
              type="radio"
              name="access-scope"
              className="access-level-picker__radio"
              checked={scope === option.scope}
              onChange={() => onScopeChange(option.scope)}
            />
            <div className="access-level-picker__content">
              <div className="access-level-picker__name">
                {option.name}
                {option.scope === 'selective' && hasElementSelection && (
                  <span style={{ fontWeight: 'normal', marginLeft: 8 }}>
                    ({selectedElementCount} selected)
                  </span>
                )}
              </div>
              <div className="access-level-picker__desc">{option.description}</div>
            </div>
          </label>

          {/* Time options for time-limited scope */}
          {option.scope === 'time-limited' && scope === 'time-limited' && (
            <div className="access-level-picker__time-options">
              <div className="access-level-picker__time-field">
                <label htmlFor="valid-from">Valid From</label>
                <input
                  id="valid-from"
                  type="datetime-local"
                  value={validFrom ? validFrom.slice(0, 16) : ''}
                  onChange={(e) => handleDateChange('from', e.target.value)}
                />
              </div>
              <div className="access-level-picker__time-field">
                <label htmlFor="valid-until">Valid Until</label>
                <input
                  id="valid-until"
                  type="datetime-local"
                  value={validUntil ? validUntil.slice(0, 16) : ''}
                  onChange={(e) => handleDateChange('until', e.target.value)}
                />
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

export default AccessLevelPicker;
