/**
 * DescriptionText renders the guidance for an element.
 *
 * With a schema it shows the full specification guidance (definition, notes,
 * standards, constraints, example). With only a description it falls back
 * to the plain multi-language text.
 */

import React from 'react';
import type { UIElementSchema } from '../../types/ui-schema';
import FieldGuidance from './FieldGuidance';

interface DescriptionTextProps {
  description?: Record<string, string> | null;
  /** Element schema; enables the full specification guidance */
  schema?: UIElementSchema;
  /** Form path of the element */
  path?: string;
}

export const DescriptionText: React.FC<DescriptionTextProps> = ({
  description,
  schema,
  path,
}) => {
  if (schema) {
    return <FieldGuidance schema={schema} path={path} />;
  }

  if (!description || Object.keys(description).length === 0) {
    return null;
  }

  return (
    <div className="aas-description">
      {Object.entries(description).map(([lang, text]) => (
        <div key={lang} className="aas-description-line">
          <span className="aas-description-lang">{lang}:</span> {text}
        </div>
      ))}
    </div>
  );
};

export default DescriptionText;
