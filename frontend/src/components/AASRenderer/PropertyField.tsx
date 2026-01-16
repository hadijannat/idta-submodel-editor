/**
 * PropertyField component for rendering Property elements.
 */

import React, { useState } from 'react';
import { useFormContext, Controller, useWatch } from 'react-hook-form';
import type { UIElementSchema } from '../../types/ui-schema';
import DescriptionText from './DescriptionText';
import SemanticChip from '../semantic/SemanticChip';
import SemanticLookupModal from '../semantic/SemanticLookupModal';

interface PropertyFieldProps {
  /** Form path for the value */
  path: string;
  /** Element schema */
  schema: UIElementSchema;
  /** Display label */
  label: string;
  /** Whether the field is required */
  required: boolean;
  /** Show semantic lookup controls */
  showSemantic?: boolean;
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
  showSemantic = true,
}) => {
  const { control, setValue } = useFormContext();
  const [isSemanticOpen, setSemanticOpen] = useState(false);
  const basePath = path.replace(/\.value$/, '');
  const semanticId = useWatch({
    control,
    name: `${basePath}.semanticId`,
  }) as string | null | undefined;
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
        {showSemantic && (
          <div className="semantic-row">
            <span className="aas-sublabel">Semantic</span>
            <SemanticChip
              semanticId={semanticId}
              onOpen={() => setSemanticOpen(true)}
              onClear={() =>
                setValue(`${basePath}.semanticId`, null, { shouldDirty: true })
              }
            />
          </div>
        )}
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

        {showSemantic && (
          <SemanticLookupModal
            isOpen={isSemanticOpen}
            onClose={() => setSemanticOpen(false)}
            onApply={(value) =>
              setValue(`${basePath}.semanticId`, value, { shouldDirty: true })
            }
            currentSemanticId={semanticId ?? undefined}
            elementType={schema.modelType}
            valueType={schema.valueType}
            defaultKind="property"
          />
        )}
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
      {showSemantic && (
        <div className="semantic-row">
          <span className="aas-sublabel">Semantic</span>
          <SemanticChip
            semanticId={semanticId}
            onOpen={() => setSemanticOpen(true)}
            onClear={() =>
              setValue(`${basePath}.semanticId`, null, { shouldDirty: true })
            }
          />
        </div>
      )}

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

      {showSemantic && (
        <SemanticLookupModal
          isOpen={isSemanticOpen}
          onClose={() => setSemanticOpen(false)}
          onApply={(value) =>
            setValue(`${basePath}.semanticId`, value, { shouldDirty: true })
          }
          currentSemanticId={semanticId ?? undefined}
          elementType={schema.modelType}
          valueType={schema.valueType}
          defaultKind="property"
        />
      )}
    </div>
  );
};

export default PropertyField;
