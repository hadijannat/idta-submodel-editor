/**
 * ReferenceField component for rendering ReferenceElement elements.
 *
 * Allows users to enter reference identifiers (IRIs, IRDIs, etc.).
 */

import React, { useState } from 'react';
import { useFormContext, Controller, useWatch } from 'react-hook-form';
import type { UIElementSchema } from '../../types/ui-schema';
import DescriptionText from './DescriptionText';
import SemanticChip from '../semantic/SemanticChip';
import SemanticLookupModal from '../semantic/SemanticLookupModal';

interface ReferenceFieldProps {
  /** Form path for the reference value */
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
 * Validates reference format (IRI or IRDI).
 */
function isValidReference(value: string): boolean {
  if (!value) return true; // Empty is valid (handled by required)

  // URI/IRI pattern aligned with backend validation, including urn:...
  const uriPattern = /^[a-zA-Z][a-zA-Z0-9+.-]*:\S+$/;

  // IRDI pattern (e.g., 0173-1#01-AFZ615#001)
  const irdiPattern = /^\d{4}-\d#\d{2}-[A-Z]{3}\d{3}#\d{3}$/;

  // ECLASS IRDI pattern (e.g., 0173-1#02-AAO677#002)
  const eclassPattern = /^\d{4}-\d#\d{2}-[A-Z]{3}\d{3}#\d{3}$/;

  return uriPattern.test(value) || irdiPattern.test(value) || eclassPattern.test(value);
}

/**
 * Renders an input field for reference identifiers.
 */
export const ReferenceField: React.FC<ReferenceFieldProps> = ({
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

  return (
    <div className="aas-field aas-field-reference">
      <label className="aas-label" htmlFor={path}>
        {label}
        {required && <span className="aas-required">*</span>}
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

      <DescriptionText description={schema.description} />

      <Controller
        name={path}
        control={control}
        defaultValue={schema.value ?? ''}
        rules={{
          required: required ? `${label} is required` : false,
          validate: (value) => {
            if (value && !isValidReference(value)) {
              return 'Please enter a valid URI/IRI or IRDI';
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
        Enter a URI/IRI or IRDI (e.g., ECLASS identifier) to reference another element.
      </p>

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

export default ReferenceField;
