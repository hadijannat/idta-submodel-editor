/**
 * RangeField component for rendering Range elements.
 *
 * Provides input fields for minimum and maximum values.
 */

import React from 'react';
import { useFormContext, Controller } from 'react-hook-form';
import type { UIElementSchema } from '../../types/ui-schema';
import DescriptionText from './DescriptionText';

interface RangeFieldProps {
  /** Form path for the range element */
  path: string;
  /** Element schema */
  schema: UIElementSchema;
  /** Display label */
  label: string;
  /** Whether the field is required */
  required: boolean;
}

/**
 * Renders min/max input fields for Range element.
 */
export const RangeField: React.FC<RangeFieldProps> = ({
  path,
  schema,
  label,
  required,
}) => {
  const { control, watch } = useFormContext();

  const valueType = schema.valueType || 'xs:double';
  const isInteger = valueType.includes('int') || valueType.includes('Integer');
  const step = isInteger ? '1' : 'any';
  const unit = schema.unit;

  // Watch values for validation
  const minValue = watch(`${path}.min`);
  const maxValue = watch(`${path}.max`);

  return (
    <div className="aas-field aas-field-range">
      <label className="aas-label">
        {label}
        {required && <span className="aas-required">*</span>}
        {unit && <span className="aas-unit">({unit})</span>}
      </label>

      <DescriptionText description={schema.description} />

      <div className="aas-range-fields">
        <div className="aas-range-min">
          <label className="aas-sublabel" htmlFor={`${path}.min`}>
            Minimum
          </label>
          <Controller
            name={`${path}.min`}
            control={control}
            defaultValue={schema.min ?? ''}
            rules={{
              required: required ? 'Minimum value is required' : false,
              validate: (value) => {
                if (value !== '' && maxValue !== '' && value !== null && maxValue !== null) {
                  const numValue = parseFloat(value);
                  const numMax = parseFloat(maxValue);
                  if (!isNaN(numValue) && !isNaN(numMax) && numValue > numMax) {
                    return 'Minimum must be less than or equal to maximum';
                  }
                }
                return true;
              },
            }}
            render={({ field, fieldState }) => (
              <>
                <input
                  {...field}
                  id={`${path}.min`}
                  type="number"
                  step={step}
                  placeholder="Min"
                  className={`aas-input ${fieldState.error ? 'aas-input-error' : ''}`}
                  onChange={(e) => {
                    const value = e.target.value;
                    field.onChange(value === '' ? '' : parseFloat(value));
                  }}
                />
                {fieldState.error && (
                  <span className="aas-error-message">
                    {fieldState.error.message}
                  </span>
                )}
              </>
            )}
          />
        </div>

        <span className="aas-range-separator">to</span>

        <div className="aas-range-max">
          <label className="aas-sublabel" htmlFor={`${path}.max`}>
            Maximum
          </label>
          <Controller
            name={`${path}.max`}
            control={control}
            defaultValue={schema.max ?? ''}
            rules={{
              required: required ? 'Maximum value is required' : false,
              validate: (value) => {
                if (value !== '' && minValue !== '' && value !== null && minValue !== null) {
                  const numValue = parseFloat(value);
                  const numMin = parseFloat(minValue);
                  if (!isNaN(numValue) && !isNaN(numMin) && numValue < numMin) {
                    return 'Maximum must be greater than or equal to minimum';
                  }
                }
                return true;
              },
            }}
            render={({ field, fieldState }) => (
              <>
                <input
                  {...field}
                  id={`${path}.max`}
                  type="number"
                  step={step}
                  placeholder="Max"
                  className={`aas-input ${fieldState.error ? 'aas-input-error' : ''}`}
                  onChange={(e) => {
                    const value = e.target.value;
                    field.onChange(value === '' ? '' : parseFloat(value));
                  }}
                />
                {fieldState.error && (
                  <span className="aas-error-message">
                    {fieldState.error.message}
                  </span>
                )}
              </>
            )}
          />
        </div>
      </div>
    </div>
  );
};

export default RangeField;
