/**
 * FieldGuidance shows what the template specification requires of a field:
 * the definition of the concept, the notes of the specification, the format
 * standard that applies, value constraints and an example.
 */

import React from 'react';
import type { UIElementSchema } from '../../types/ui-schema';
import {
  exampleValue,
  preferredText,
  splitNotes,
  toIdShortPath,
} from '../../utils/fieldRequirements';
import { useFormOptions } from './FormOptionsContext';

interface FieldGuidanceProps {
  schema: UIElementSchema;
  /** Form path of the element (used to look up specification notes) */
  path?: string;
  /** Hide the example line (e.g. when the input already shows it) */
  hideExample?: boolean;
}

function normalize(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, '');
}

function describeRange(schema: UIElementSchema): string | null {
  const range = schema.allowedRange;
  if (!range) return null;
  const hasMin = range.min !== null && range.min !== undefined;
  const hasMax = range.max !== null && range.max !== undefined;
  if (hasMin && hasMax) return `Allowed range: ${range.min} to ${range.max}`;
  if (hasMin) return `Minimum: ${range.min}`;
  if (hasMax) return `Maximum: ${range.max}`;
  return null;
}

export const FieldGuidance: React.FC<FieldGuidanceProps> = ({
  schema,
  path,
  hideExample = false,
}) => {
  const { specNotes, specificationUrl } = useFormOptions();
  const spec = path ? specNotes[toIdShortPath(path)] : undefined;

  const description = splitNotes(preferredText(schema.description));
  const definition = preferredText(schema.definition);
  const body = definition || description.body;

  const notes: string[] = [];
  const seen = new Set<string>();
  const addNote = (note: string | null | undefined) => {
    if (!note) return;
    const key = normalize(note);
    if (!key || seen.has(key)) return;
    if (body && normalize(body).includes(key)) return;
    seen.add(key);
    notes.push(note);
  };
  if (definition && description.body && normalize(description.body) !== normalize(definition)) {
    addNote(description.body);
  }
  description.notes.forEach(addNote);
  (schema.notes ?? []).forEach(addNote);
  addNote(schema.formInfo);
  // The template package is the newer source; notes from the PDF fill in
  // only where the package carries none.
  if (notes.length === 0) {
    (spec?.notes ?? []).forEach(addNote);
  }

  const constraints: string[] = [];
  const range = describeRange(schema);
  if (range) constraints.push(range);
  if (schema.valueFormat) {
    constraints.push(
      `Value format ${schema.valueFormat}${
        schema.valueFormatDescription ? ` (${schema.valueFormatDescription})` : ''
      }`
    );
  }
  if (schema.pattern) constraints.push(`Pattern: ${schema.pattern}`);
  if (schema.requiredLanguages && schema.requiredLanguages.length > 0) {
    constraints.push(`Required languages: ${schema.requiredLanguages.join(', ')}`);
  }
  if (schema.eitherOr) {
    constraints.push(`One of the "${schema.eitherOr}" alternatives must be provided`);
  }
  if (schema.defaultValue) constraints.push(`Default: ${schema.defaultValue}`);
  if (
    spec?.cardinality &&
    spec.templateCardinality &&
    spec.cardinality !== spec.templateCardinality
  ) {
    constraints.push(
      `The specification PDF states cardinality ${spec.cardinality}; the template package declares ${spec.templateCardinality}`
    );
  }

  // Examples in the PDF sometimes run into the adjoining prose; only short
  // ones are usable as an example value.
  const specExample = spec?.example && spec.example.length <= 60 ? spec.example : null;
  const example = hideExample ? null : (exampleValue(schema) ?? specExample ?? null);
  const standards = (schema.standards ?? []).filter(
    (standard) => !schema.formatHint || !normalize(schema.formatHint.label).includes(normalize(standard))
  );
  const specLink =
    specificationUrl && spec?.page ? `${specificationUrl}#page=${spec.page}` : null;

  const hasContent =
    body ||
    notes.length > 0 ||
    constraints.length > 0 ||
    example ||
    schema.formatHint ||
    standards.length > 0 ||
    specLink;
  if (!hasContent) return null;

  return (
    <div className="aas-guidance">
      {body && <p className="aas-guidance-definition">{body}</p>}

      {(schema.formatHint || standards.length > 0) && (
        <div className="aas-guidance-standards">
          {schema.formatHint && (
            <span
              className="aas-standard-chip aas-standard-chip-format"
              title={schema.formatHint.description}
            >
              {schema.formatHint.label}
            </span>
          )}
          {standards.map((standard) => (
            <span key={standard} className="aas-standard-chip" title="Standard referenced by the specification">
              {standard}
            </span>
          ))}
          {schema.formatHint && (
            <span className="aas-guidance-format-text">{schema.formatHint.description}</span>
          )}
        </div>
      )}

      {notes.length > 0 && (
        <ul className="aas-guidance-notes">
          {notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}

      {constraints.length > 0 && (
        <ul className="aas-guidance-constraints">
          {constraints.map((constraint) => (
            <li key={constraint}>{constraint}</li>
          ))}
        </ul>
      )}

      {(example || specLink) && (
        <p className="aas-guidance-footer">
          {example && (
            <span className="aas-guidance-example">
              Example: <code>{example}</code>
            </span>
          )}
          {specLink && (
            <a
              className="aas-guidance-spec-link"
              href={specLink}
              target="_blank"
              rel="noopener noreferrer"
            >
              Specification, p. {spec?.page}
            </a>
          )}
        </p>
      )}
    </div>
  );
};

export default FieldGuidance;
