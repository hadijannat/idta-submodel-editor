/**
 * EnvironmentSelector - Picker for dataspace environments.
 *
 * Allows selection between sandbox, test, and production environments
 * with visual indicators of requirements.
 */

import type { Environment, EnvironmentInfo } from '../../services/dataspaceApi';

interface EnvironmentSelectorProps {
  environments: EnvironmentInfo[];
  selected: Environment;
  onChange: (env: Environment) => void;
  disabled?: boolean;
  className?: string;
}

export default function EnvironmentSelector({
  environments,
  selected,
  onChange,
  disabled = false,
  className = '',
}: EnvironmentSelectorProps) {
  return (
    <div className={`dataspace-env-selector ${className}`}>
      <label className="dataspace-env-selector__label">Environment</label>
      <div className="dataspace-env-selector__options">
        {environments.map((env) => (
          <button
            key={env.id}
            type="button"
            className={`dataspace-env-selector__option ${
              selected === env.id ? 'dataspace-env-selector__option--selected' : ''
            } ${disabled ? 'dataspace-env-selector__option--disabled' : ''}`}
            onClick={() => !disabled && onChange(env.id)}
            disabled={disabled}
          >
            <span className="dataspace-env-selector__icon">
              {env.id === 'sandbox' && '🧪'}
              {env.id === 'catena-x-test' && '🔬'}
              {env.id === 'catena-x-prod' && '🏭'}
            </span>
            <span className="dataspace-env-selector__content">
              <span className="dataspace-env-selector__name">{env.name}</span>
              <span className="dataspace-env-selector__desc">{env.description}</span>
              <span className="dataspace-env-selector__requirements">
                {env.requires_bpn && (
                  <span className="dataspace-env-selector__req-badge">BPN Required</span>
                )}
                {env.requires_credentials && (
                  <span className="dataspace-env-selector__req-badge">
                    Credentials Required
                  </span>
                )}
                {!env.requires_bpn && !env.requires_credentials && (
                  <span className="dataspace-env-selector__req-badge dataspace-env-selector__req-badge--optional">
                    No Credentials Needed
                  </span>
                )}
              </span>
            </span>
            {env.is_default && (
              <span className="dataspace-env-selector__default">Default</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
