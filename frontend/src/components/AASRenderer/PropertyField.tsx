/**
 * PropertyField component for rendering Property elements.
 */

import React from 'react';
import { useFormContext, Controller } from 'react-hook-form';
import type { UIElementSchema } from '../../types/ui-schema';
import DescriptionText from './DescriptionText';

interface PropertyFieldProps {
  /** Form path for the value */
  path: string;
  /** Element schema */
  schema: UIElementSchema;
  /** Display label */
  label: string;
  /** Whether the field is required */
  required: boolean;
}

/**
 * Renders a form input for a Property element.
 *
 * Maps XSD value types to appropriate HTML input types.
 */
export const PropertyField: React.FC<PropertyFieldProps> = ({
  path,
  schema,
  label,
  required,
}) => {
  const { control } = useFormContext();
  const inputType = schema.inputType || 'text';
  const step = schema.step;
  const constraints = schema.constraints;
  const unit = schema.unit;

  const getInputProps = () => {
    const props: React.InputHTMLAttributes<HTMLInputElement> = {
      type: inputType,
      placeholder: `Enter ${label}`,
    };

    if (inputType === 'number') {
      if (step) props.step = step;
      if (constraints?.min !== null && constraints?.min !== undefined) {
        props.min = constraints.min;
      }
      if (constraints?.max !== null && constraints?.max !== undefined) {
        props.max = constraints.max;
      }
    }

    return props;
  };

  // Handle checkbox (boolean) type
  if (inputType === 'checkbox') {
    return (
      <div className="aas-field aas-field-checkbox">
        <Controller
          name={path}
          control={control}
          defaultValue={schema.value ?? false}
          render={({ field, fieldState }) => (
            <label className="aas-checkbox-label">
              <input
                {...field}
                type="checkbox"
                checked={field.value === true}
                onChange={(e) => field.onChange(e.target.checked)}
                className={fieldState.error ? 'aas-input-error' : ''}
              />
              <span>{label}</span>
              {required && <span className="aas-required">*</span>}
              {fieldState.error && (
                <span className="aas-error-message">{fieldState.error.message}</span>
              )}
            </label>
          )}
        />
        <DescriptionText description={schema.description} />
      </div>
    );
  }

  // Handle textarea for long strings
  const isMultiline = schema.valueType === 'xs:string' && !schema.constraints;

  return (
    <div className="aas-field aas-field-property">
      <label className="aas-label" htmlFor={path}>
        {label}
        {required && <span className="aas-required">*</span>}
        {unit && <span className="aas-unit">({unit})</span>}
      </label>

      <Controller
        name={path}
        control={control}
        defaultValue={schema.value ?? ''}
        rules={{
          required: required ? `${label} is required` : false,
        }}
        render={({ field, fieldState }) => (
          <>
            {isMultiline ? (
              <textarea
                {...field}
                id={path}
                rows={3}
                placeholder={`Enter ${label}`}
                className={`aas-input aas-textarea ${fieldState.error ? 'aas-input-error' : ''}`}
              />
            ) : (
              <input
                {...field}
                {...getInputProps()}
                id={path}
                className={`aas-input ${fieldState.error ? 'aas-input-error' : ''}`}
                value={field.value ?? ''}
                onChange={(e) => {
                  const value = e.target.value;
                  if (inputType === 'number' && value !== '') {
                    field.onChange(parseFloat(value));
                  } else {
                    field.onChange(value);
                  }
                }}
              />
            )}
            {fieldState.error && (
              <span className="aas-error-message">{fieldState.error.message}</span>
            )}
          </>
        )}
      />

      <DescriptionText description={schema.description} />
    </div>
  );
};

export default PropertyField;
