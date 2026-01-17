/**
 * PCF Validator component for displaying IDTA 02023 validation results.
 *
 * Shows:
 * - Validation status (pass/fail)
 * - Error list with field paths (blocking issues)
 * - Warning list (recommendations)
 * - Completeness score indicator
 */

import type { PCFValidateResponse } from '../../types/pcf';
import './PCFValidator.css';

interface PCFValidatorProps {
  validationResult: PCFValidateResponse | null;
  validating: boolean;
  onValidate: () => Promise<void>;
}

export default function PCFValidator({
  validationResult,
  validating,
  onValidate,
}: PCFValidatorProps) {
  const hasResult = validationResult !== null;
  const isValid = validationResult?.valid ?? false;
  const errors = validationResult?.errors ?? [];
  const warnings = validationResult?.warnings ?? [];
  const completeness = validationResult?.completeness_score ?? 0;

  return (
    <div className="pcf-validator">
      <div className="pcf-validator__header">
        <h3>PCF Validation</h3>
        <p className="pcf-validator__description">
          Validate against IDTA 02023 Carbon Footprint requirements.
        </p>
      </div>

      <div className="pcf-validator__actions">
        <button
          type="button"
          className="pcf-validator__btn pcf-validator__btn--primary"
          onClick={onValidate}
          disabled={validating}
        >
          {validating ? 'Validating...' : 'Validate PCF'}
        </button>
      </div>

      {hasResult && (
        <div className="pcf-validator__results">
          {/* Status badge */}
          <div
            className={`pcf-validator__status ${
              isValid ? 'pcf-validator__status--valid' : 'pcf-validator__status--invalid'
            }`}
          >
            {isValid ? '✓ Valid' : '✗ Invalid'}
          </div>

          {/* Completeness score */}
          <div className="pcf-validator__completeness">
            <span className="pcf-validator__completeness-label">Completeness:</span>
            <div className="pcf-validator__progress">
              <div
                className="pcf-validator__progress-fill"
                style={{ width: `${completeness * 100}%` }}
              />
            </div>
            <span className="pcf-validator__completeness-value">
              {Math.round(completeness * 100)}%
            </span>
          </div>

          {/* Errors */}
          {errors.length > 0 && (
            <div className="pcf-validator__section pcf-validator__section--errors">
              <h4>Errors ({errors.length})</h4>
              <ul className="pcf-validator__list">
                {errors.map((error) => (
                  <li key={error.rule_id} className="pcf-validator__item">
                    <span className="pcf-validator__icon pcf-validator__icon--error">
                      ✗
                    </span>
                    <div className="pcf-validator__content">
                      <span className="pcf-validator__field">{error.field}</span>
                      <span className="pcf-validator__message">{error.message}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Warnings */}
          {warnings.length > 0 && (
            <div className="pcf-validator__section pcf-validator__section--warnings">
              <h4>Warnings ({warnings.length})</h4>
              <ul className="pcf-validator__list">
                {warnings.map((warning) => (
                  <li key={warning.rule_id} className="pcf-validator__item">
                    <span className="pcf-validator__icon pcf-validator__icon--warning">
                      ⚠
                    </span>
                    <div className="pcf-validator__content">
                      <span className="pcf-validator__field">{warning.field}</span>
                      <span className="pcf-validator__message">{warning.message}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Success message */}
          {isValid && errors.length === 0 && warnings.length === 0 && (
            <div className="pcf-validator__success">
              <p>✓ All PCF requirements are satisfied.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
