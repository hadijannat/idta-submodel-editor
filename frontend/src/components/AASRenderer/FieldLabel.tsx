/**
 * FieldLabel renders the human-readable label of an element together with
 * its idShort, requirement marker, unit and cardinality.
 */

import React from 'react';
import type { UIElementSchema } from '../../types/ui-schema';

interface FieldLabelProps {
  schema: UIElementSchema;
  label: string;
  required: boolean;
  htmlFor?: string;
  unit?: string | null;
}

function cardinalityText(cardinality: string): string | null {
  switch (cardinality) {
    case '[0..1]':
      return 'optional';
    case '[0..*]':
      return 'optional, multiple';
    case '[1..*]':
      return 'one or more';
    default:
      return null;
  }
}

export const FieldLabel: React.FC<FieldLabelProps> = ({
  schema,
  label,
  required,
  htmlFor,
  unit,
}) => {
  const showIdShort = schema.idShort && schema.idShort !== label;
  const hint = cardinalityText(schema.cardinality);
  return (
    <label className="aas-label" htmlFor={htmlFor}>
      <span className="aas-label-text">{label}</span>
      {required && (
        <span className="aas-required" title="Required by the template">
          *
        </span>
      )}
      {unit && <span className="aas-unit">({unit})</span>}
      {showIdShort && (
        <code className="aas-id-short" title="idShort in the submodel">
          {schema.idShort}
        </code>
      )}
      {!required && hint && <span className="aas-optional">{hint}</span>}
    </label>
  );
};

export default FieldLabel;
