/**
 * PropertyField component for rendering Property elements.
 */

import React, { useId, useState } from 'react';
import { useFormContext, Controller, useWatch } from 'react-hook-form';
import type { UIElementSchema } from '../../types/ui-schema';
import FieldGuidance from './FieldGuidance';
import FieldLabel from './FieldLabel';
import { useFormOptions } from './FormOptionsContext';
import SemanticChip from '../semantic/SemanticChip';
import SemanticLookupModal from '../semantic/SemanticLookupModal';
import {
  fieldOptions,
  fieldPlaceholder,
  formatHintWarning,
  isStrictEnumeration,
  isTemplateExample,
  requirementError,
} from '../../utils/fieldRequirements';

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

/** Long free text is edited in a textarea; short identifiers in an input. */
function isLongText(schema: UIElementSchema): boolean {
  if (schema.valueType !== 'xs:string') return false;
  if (schema.formatHint || schema.pattern || schema.maxLength) return false;
  if (schema.allowedValues && schema.allowedValues.length > 0) return false;
  const sample = typeof schema.value === 'string' ? schema.value : '';
  return sample.length > 80 || sample.includes('\n');
}

/**
 * Renders a form input for a Property element.
 *
 * Maps XSD value types to HTML input types and applies the requirements the
 * template declares: enumerations become selects, code lists and suggested
 * values become autocompletion, ranges and patterns are checked inline.
 */
export const PropertyField: React.FC<PropertyFieldProps> = ({
  path,
  schema,
  label,
  required,
  showSemantic = true,
}) => {
  const { control, setValue } = useFormContext();
  const formOptions = useFormOptions();
  const semanticVisible = showSemantic && formOptions.showSemantic;
  const [isSemanticOpen, setSemanticOpen] = useState(false);
  const listId = useId();
  const basePath = path.replace(/\.value$/, '');
  const semanticId = useWatch({
    control,
    name: `${basePath}.semanticId`,
  }) as string | null | undefined;
  const currentValue = useWatch({ control, name: path });
  const holdsExample = isTemplateExample(schema, currentValue);
  const inputType = schema.inputType || 'text';
  const step = schema.step;
  const unit = schema.unit;
  const readOnly = Boolean(schema.readOnly);
  const options = fieldOptions(schema);
  const strictEnumeration = isStrictEnumeration(schema) && inputType !== 'checkbox';

  const getInputProps = () => {
    const props: React.InputHTMLAttributes<HTMLInputElement> = {
      type: inputType,
      placeholder: fieldPlaceholder(schema, label),
    };

    if (inputType === 'number') {
      if (step) props.step = step;
      const min = schema.allowedRange?.min ?? schema.constraints?.min;
      const max = schema.allowedRange?.max ?? schema.constraints?.max;
      if (min !== null && min !== undefined) props.min = min;
      if (max !== null && max !== undefined) props.max = max;
    }
    if (inputType === 'text' || inputType === 'url') {
      if (schema.maxLength) props.maxLength = Math.max(schema.maxLength * 4, 64);
      if (options.length > 0) props.list = listId;
    }
    if (inputType === 'url') {
      // Template values are checked by the template rules, not the browser.
      props.type = 'text';
      props.inputMode = 'url';
    }

    return props;
  };

  const semanticControls = semanticVisible && (
    <div className="semantic-row">
      <span className="aas-sublabel">Semantic</span>
      <SemanticChip
        semanticId={semanticId}
        onOpen={() => setSemanticOpen(true)}
        onClear={() => setValue(`${basePath}.semanticId`, null, { shouldDirty: true })}
      />
    </div>
  );

  const semanticModal = semanticVisible && (
    <SemanticLookupModal
      isOpen={isSemanticOpen}
      onClose={() => setSemanticOpen(false)}
      onApply={(value) => setValue(`${basePath}.semanticId`, value, { shouldDirty: true })}
      currentSemanticId={semanticId ?? undefined}
      elementType={schema.modelType}
      valueType={schema.valueType}
      defaultKind="property"
    />
  );

  // Handle checkbox (boolean) type
  if (inputType === 'checkbox') {
    return (
      <div className="aas-field aas-field-checkbox">
        {semanticControls}
        <Controller
          name={path}
          control={control}
          defaultValue={schema.value ?? false}
          render={({ field, fieldState }) => (
            <label className="aas-checkbox-label">
              <input
                {...field}
                type="checkbox"
                checked={field.value === true || field.value === 'true'}
                disabled={readOnly}
                onChange={(e) => field.onChange(e.target.checked)}
                className={fieldState.error ? 'aas-input-error' : ''}
              />
              <span>{label}</span>
              {required && <span className="aas-required">*</span>}
              {schema.idShort !== label && (
                <code className="aas-id-short">{schema.idShort}</code>
              )}
              {fieldState.error && (
                <span className="aas-error-message">{fieldState.error.message}</span>
              )}
            </label>
          )}
        />
        <FieldGuidance schema={schema} path={basePath} hideExample />
        {semanticModal}
      </div>
    );
  }

  const multiline = !strictEnumeration && isLongText(schema);

  return (
    <div className="aas-field aas-field-property">
      <FieldLabel
        schema={schema}
        label={label}
        required={required}
        htmlFor={path}
        unit={unit}
      />
      {semanticControls}

      <Controller
        name={path}
        control={control}
        defaultValue={schema.value ?? ''}
        rules={{
          required: required ? `${label} is required` : false,
          validate: (value) => requirementError(schema, value) ?? true,
        }}
        render={({ field, fieldState }) => {
          const warning = fieldState.error
            ? null
            : formatHintWarning(schema.formatHint, field.value);
          const stillExample = isTemplateExample(schema, field.value);
          const invalidClass = fieldState.error ? 'aas-input-error' : '';
          return (
            <>
              {strictEnumeration ? (
                <select
                  {...field}
                  id={path}
                  disabled={readOnly}
                  className={`aas-input aas-select ${invalidClass}`}
                  value={field.value === null || field.value === undefined ? '' : String(field.value)}
                  aria-invalid={fieldState.error ? 'true' : undefined}
                >
                  <option value="">{required ? 'Select…' : '— not specified —'}</option>
                  {options.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label && option.label !== option.value
                        ? `${option.label} (${option.value})`
                        : option.value}
                    </option>
                  ))}
                </select>
              ) : multiline ? (
                <textarea
                  {...field}
                  id={path}
                  rows={3}
                  readOnly={readOnly}
                  placeholder={fieldPlaceholder(schema, label)}
                  className={`aas-input aas-textarea ${invalidClass}`}
                  aria-invalid={fieldState.error ? 'true' : undefined}
                  value={field.value ?? ''}
                />
              ) : (
                <input
                  {...field}
                  {...getInputProps()}
                  id={path}
                  readOnly={readOnly}
                  className={`aas-input ${invalidClass} ${warning ? 'aas-input-warning' : ''}`}
                  aria-invalid={fieldState.error ? 'true' : undefined}
                  value={field.value ?? ''}
                  onChange={(e) => {
                    const value = e.target.value;
                    if (inputType === 'number' && value !== '') {
                      field.onChange(parseFloat(value));
                    } else {
                      field.onChange(value);
                    }
                  }}
                  onBlur={(e) => {
                    const transform = schema.formatHint?.transform;
                    const current = e.target.value;
                    if (transform === 'uppercase' && current !== current.toUpperCase()) {
                      field.onChange(current.toUpperCase().trim());
                    } else if (transform === 'lowercase' && current !== current.toLowerCase()) {
                      field.onChange(current.toLowerCase().trim());
                    }
                    field.onBlur();
                  }}
                />
              )}
              {!strictEnumeration && options.length > 0 && (
                <datalist id={listId}>
                  {options.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label ?? option.value}
                    </option>
                  ))}
                </datalist>
              )}
              {(() => {
                // Enumerations of IRDIs are unreadable on their own: show what
                // the selected identifier stands for.
                const selected = options.find(
                  (option) => option.value === String(field.value ?? '')
                );
                return !strictEnumeration && selected?.label && selected.label !== selected.value ? (
                  <span className="aas-value-label">= {selected.label}</span>
                ) : null;
              })()}
              {fieldState.error && (
                <span className="aas-error-message" role="alert">
                  {fieldState.error.message}
                </span>
              )}
              {warning && <span className="aas-warning-message">{warning}</span>}
              {stillExample && !fieldState.error && (
                <span className="aas-example-flag">
                  Example value from the template — replace it with your own data.
                  <button
                    type="button"
                    className="aas-link-button"
                    onClick={() => field.onChange('')}
                  >
                    Clear
                  </button>
                </span>
              )}
            </>
          );
        }}
      />

      <FieldGuidance schema={schema} path={basePath} hideExample={holdsExample} />
      {semanticModal}
    </div>
  );
};

export default PropertyField;
