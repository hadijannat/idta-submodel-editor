/**
 * EDCModeSelector - Picker for EDC connector mode.
 *
 * Allows selection between Tractus-X EDC and AAS Extension modes
 * with descriptions of each approach.
 */

import type { EDCMode, EDCModeInfo } from '../../services/dataspaceApi';

interface EDCModeSelectorProps {
  modes: EDCModeInfo[];
  selected: EDCMode;
  onChange: (mode: EDCMode) => void;
  disabled?: boolean;
  className?: string;
}

export default function EDCModeSelector({
  modes,
  selected,
  onChange,
  disabled = false,
  className = '',
}: EDCModeSelectorProps) {
  return (
    <div className={`dataspace-edc-selector ${className}`}>
      <label className="dataspace-edc-selector__label">EDC Connector Mode</label>
      <p className="dataspace-edc-selector__help">
        Choose how the Eclipse Data Connector integrates with your AAS infrastructure.
      </p>
      <div className="dataspace-edc-selector__options">
        {modes.map((mode) => (
          <label
            key={mode.id}
            className={`dataspace-edc-selector__option ${
              selected === mode.id ? 'dataspace-edc-selector__option--selected' : ''
            } ${disabled ? 'dataspace-edc-selector__option--disabled' : ''}`}
          >
            <input
              type="radio"
              name="edc-mode"
              value={mode.id}
              checked={selected === mode.id}
              onChange={() => onChange(mode.id)}
              disabled={disabled}
              className="dataspace-edc-selector__radio"
            />
            <span className="dataspace-edc-selector__content">
              <span className="dataspace-edc-selector__icon">
                {mode.id === 'tractus-x' && '⚙️'}
                {mode.id === 'aas-extension' && '🔗'}
              </span>
              <span className="dataspace-edc-selector__text">
                <span className="dataspace-edc-selector__name">{mode.name}</span>
                <span className="dataspace-edc-selector__desc">{mode.description}</span>
              </span>
              {mode.is_default && (
                <span className="dataspace-edc-selector__default">Recommended</span>
              )}
            </span>
          </label>
        ))}
      </div>
    </div>
  );
}
