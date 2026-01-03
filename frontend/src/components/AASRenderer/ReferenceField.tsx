/**
 * ReferenceField component for rendering ReferenceElement elements.
 *
 * Allows users to enter reference identifiers (IRIs, IRDIs, etc.).
 */

import React from 'react';
import { useFormContext, Controller } from 'react-hook-form';
import type { UIElementSchema } from '../../types/ui-schema';

interface ReferenceFieldProps {
  /** Form path for the reference value */
  path: string;
  /** Element schema */
  schema: UIElementSchema;
  /** Display label */
  label: string;
  /** Whether the field is required */
  required: boolean;
}

/**
 * Validates reference format (IRI or IRDI).
 */
function isValidReference(value: string): boolean {
  if (!value) return true; // Empty is valid (handled by required)

  // IRI pattern (basic URL validation)
  const iriPattern = /^https?:\/\/.+/i;

  // IRDI pattern (e.g., 0173-1#01-AFZ615#001)
  const irdiPattern = /^\d{4}-\d#\d{2}-[A-Z]{3}\d{3}#\d{3}$/;

  // ECLASS IRDI pattern (e.g., 0173-1#02-AAO677#002)
  const eclassPattern = /^\d{4}-\d#\d{2}-[A-Z]{3}\d{3}#\d{3}$/;

  return iriPattern.test(value) || irdiPattern.test(value) || eclassPattern.test(value);
}

/**
 * Renders an input field for reference identifiers.
 */
export const ReferenceField: React.FC<ReferenceFieldProps> = ({
  path,
  schema,
  label,
  required,
}) => {
  const { control } = useFormContext();

  return (
    <div className="aas-field aas-field-reference">
      <label className="aas-label" htmlFor={path}>
        {label}
        {required && <span className="aas-required">*</span>}
      </label>

      {schema.description?.en && (
        <p className="aas-description">{schema.description.en}</p>
      )}

      <Controller
        name={path}
        control={control}
        defaultValue={schema.value ?? ''}
        rules={{
          required: required ? `${label} is required` : false,
          validate: (value) => {
            if (value && !isValidReference(value)) {
              return 'Please enter a valid IRI (URL) or IRDI';
            }
            return true;
          },
        }}
        render={({ field, fieldState }) => (
          <>
            <input
              {...field}
              id={path}
              type="text"
              placeholder="e.g., https://example.com/asset or 0173-1#01-ABC123#001"
              className={`aas-input ${fieldState.error ? 'aas-input-error' : ''}`}
            />
            {fieldState.error && (
              <span className="aas-error-message">
                {fieldState.error.message}
              </span>
            )}
          </>
        )}
      />

      <p className="aas-help-text">
        Enter an IRI (URL) or IRDI (e.g., ECLASS identifier) to reference another element.
      </p>
    </div>
  );
};

export default ReferenceField;
