/**
 * CollectionField component for rendering SubmodelElementCollection elements.
 */

import React, { useState } from 'react';
import type { UIElementSchema } from '../../types/ui-schema';
import { isRequired } from '../../types/aas-elements';
import { elementLabel } from '../../utils/fieldRequirements';
import FieldGuidance from './FieldGuidance';

interface CollectionFieldProps {
  /** Form path for the collection */
  path: string;
  /** Element schema */
  schema: UIElementSchema;
  /** Current nesting depth */
  depth: number;
  /** Override title */
  title?: string;
  /** Child elements to render */
  children: React.ReactNode;
}

/**
 * Renders a collapsible section for SubmodelElementCollection.
 */
export const CollectionField: React.FC<CollectionFieldProps> = ({
  path,
  schema,
  depth,
  title,
  children,
}) => {
  const [isExpanded, setIsExpanded] = useState(depth < 2); // Auto-expand first 2 levels

  const displayTitle = title || elementLabel(schema);
  const childCount = schema.elements?.length || schema.statements?.length || 0;
  const required = isRequired(schema.cardinality);

  return (
    <div
      className={`aas-collection aas-depth-${depth}`}
      data-id-short={schema.idShort}
    >
      <div
        className="aas-collection-header"
        onClick={() => setIsExpanded(!isExpanded)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setIsExpanded(!isExpanded);
          }
        }}
        role="button"
        tabIndex={0}
        aria-expanded={isExpanded}
      >
        <span className={`aas-expand-icon ${isExpanded ? 'expanded' : ''}`}>
          {isExpanded ? '▼' : '▶'}
        </span>
        <span className="aas-collection-title">{displayTitle}</span>
        {required && (
          <span className="aas-required" title="Required by the template">
            *
          </span>
        )}
        {schema.idShort && schema.idShort !== displayTitle && (
          <code className="aas-id-short">{schema.idShort}</code>
        )}
        <span className="aas-collection-count">
          ({childCount} {childCount === 1 ? 'field' : 'fields'})
        </span>
        {schema.cardinality !== '[1]' && (
          <span className="aas-cardinality">{schema.cardinality}</span>
        )}
      </div>

      {isExpanded && <FieldGuidance schema={schema} path={path} hideExample />}

      <div
        className={`aas-collection-content ${isExpanded ? 'expanded' : 'collapsed'}`}
        aria-hidden={!isExpanded}
      >
        {isExpanded && children}
      </div>
    </div>
  );
};

export default CollectionField;
