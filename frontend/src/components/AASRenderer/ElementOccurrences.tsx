/**
 * Further occurrences of a repeatable element.
 *
 * Templates often allow an element to occur several times without putting it
 * into a list (cardinality "ZeroToMany" or "OneToMany"). The first occurrence
 * is the element itself; this component manages the others, which live in the
 * element's `occurrences` array in the form data. The backend turns each one
 * into a sibling element with an idShort of its own on export.
 */

import React, { useCallback } from 'react';
import { useFieldArray, useFormContext } from 'react-hook-form';
import type { UIElementSchema } from '../../types/ui-schema';
import { getMaxItems } from '../../types/aas-elements';
import { elementLabel } from '../../utils/fieldRequirements';
import { createDefaultItem } from './elementDefaults';

interface ElementOccurrencesProps {
  /** Schema of the repeatable element */
  schema: UIElementSchema;
  /** Form path of the element (its first occurrence) */
  path: string;
  /** Renders one further occurrence at the given form path */
  renderOccurrence: (occurrencePath: string) => React.ReactNode;
}

export const ElementOccurrences: React.FC<ElementOccurrencesProps> = ({
  schema,
  path,
  renderOccurrence,
}) => {
  const { control } = useFormContext();
  const { fields, append, remove } = useFieldArray({
    control,
    name: `${path}.occurrences` as const,
  });

  const label = elementLabel(schema);
  const maxOccurrences = getMaxItems(schema.cardinality);
  // The element itself is the first occurrence.
  const canAdd = maxOccurrences === undefined || fields.length + 1 < maxOccurrences;

  const handleAdd = useCallback(() => {
    append(createDefaultItem(schema));
  }, [append, schema]);

  return (
    <div className="aas-occurrences" data-id-short={schema.idShort}>
      {fields.map((field, index) => (
        <div key={field.id} className="aas-occurrence" data-index={index}>
          <div className="aas-occurrence-header">
            <span className="aas-occurrence-title">
              {label} {index + 2}
            </span>
            <button
              type="button"
              className="aas-btn aas-btn-icon aas-btn-danger"
              onClick={() => remove(index)}
              aria-label={`Remove ${label} ${index + 2}`}
              title="Remove"
            >
              ×
            </button>
          </div>
          <div className="aas-occurrence-content">
            {renderOccurrence(`${path}.occurrences.${index}`)}
          </div>
        </div>
      ))}

      <button
        type="button"
        className="aas-btn aas-btn-add-occurrence"
        onClick={handleAdd}
        disabled={!canAdd}
        title={
          canAdd
            ? undefined
            : `The template allows at most ${maxOccurrences} of ${label}`
        }
      >
        + Add another {label}
      </button>
    </div>
  );
};

export default ElementOccurrences;
