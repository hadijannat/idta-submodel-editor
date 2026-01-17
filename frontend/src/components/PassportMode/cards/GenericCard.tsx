/**
 * GenericCard - Fallback passport card for any template.
 *
 * Renders a clean, type-aware visualization of submodel elements.
 * Uses recursive rendering for nested collections with depth limit.
 */

import type { SubmodelUISchema, UIElementSchema } from '../../../types/ui-schema';
import type { SubmodelFormData, ElementFormData } from '../../../types/aas-elements';
import {
  extractPrimitive,
  extractLangString,
  extractCollection,
  extractList,
  isProvided,
  formatValue,
} from '../utils/valueExtractors';

const MAX_DEPTH = 4;

interface GenericCardProps {
  schema: SubmodelUISchema;
  formData: SubmodelFormData | undefined;
}

interface ElementValue {
  label: string;
  value: string;
  type: string;
}

/**
 * Extract displayable value from an element based on its type.
 */
function extractElementValue(
  elementSchema: UIElementSchema,
  formData: SubmodelFormData | undefined,
  basePath: string
): string | undefined {
  const path = `${basePath}.${elementSchema.idShort}`;

  switch (elementSchema.modelType) {
    case 'Property': {
      const val = extractPrimitive(formData, `${path}.value`) ?? extractPrimitive(formData, path);
      if (!isProvided(val)) return undefined;
      return formatValue(val);
    }

    case 'MultiLanguageProperty': {
      const val = extractLangString(formData, `${path}.value`) ?? extractLangString(formData, path);
      if (!isProvided(val)) return undefined;
      return val;
    }

    case 'File': {
      const val = extractPrimitive(formData, `${path}.value`);
      if (!isProvided(val)) return undefined;
      return String(val);
    }

    case 'Range': {
      const min = extractPrimitive(formData, `${path}.min`);
      const max = extractPrimitive(formData, `${path}.max`);
      if (!isProvided(min) && !isProvided(max)) return undefined;
      return `${formatValue(min) || '...'} - ${formatValue(max) || '...'}`;
    }

    default:
      return undefined;
  }
}

/**
 * Recursively render elements from the schema.
 */
function renderElements(
  elements: UIElementSchema[],
  formData: SubmodelFormData | undefined,
  basePath: string,
  depth: number
): React.ReactNode {
  if (depth > MAX_DEPTH || !elements.length) {
    return null;
  }

  const renderedFields: ElementValue[] = [];
  const nestedSections: React.ReactNode[] = [];

  for (const element of elements) {
    const path = `${basePath}.${element.idShort}`;

    // Handle collections and lists recursively
    if (element.modelType === 'SubmodelElementCollection' && element.elements) {
      const collectionData = extractCollection(formData, path);
      const hasData = collectionData && Object.keys(collectionData).length > 0;

      // Check if any child has data
      const childContent = renderElements(
        element.elements,
        formData,
        `${path}.elements`,
        depth + 1
      );

      if (childContent || hasData) {
        nestedSections.push(
          <div key={element.idShort} className="generic-nested">
            <div className="generic-nested-title">
              {element.semanticLabel || element.idShort}
            </div>
            {childContent}
          </div>
        );
      }
      continue;
    }

    if (element.modelType === 'SubmodelElementList' && element.itemTemplate) {
      const listItems = extractList(formData, `${path}.items`);
      if (listItems && listItems.length > 0) {
        nestedSections.push(
          <div key={element.idShort} className="generic-nested">
            <div className="generic-nested-title">
              {element.semanticLabel || element.idShort} ({listItems.length} items)
            </div>
            {listItems.map((item, index) => (
              <div key={index} className="generic-field">
                <span className="generic-field-label">Item {index + 1}</span>
                <span className="generic-field-value">
                  {renderListItem(item, element.itemTemplate!)}
                </span>
              </div>
            ))}
          </div>
        );
      }
      continue;
    }

    // Extract simple values
    const value = extractElementValue(element, formData, basePath);
    if (value !== undefined) {
      renderedFields.push({
        label: element.semanticLabel || element.idShort,
        value,
        type: element.modelType,
      });
    }
  }

  if (renderedFields.length === 0 && nestedSections.length === 0) {
    return null;
  }

  return (
    <>
      {renderedFields.length > 0 && (
        <div className="generic-fields">
          {renderedFields.map((field, index) => (
            <div key={index} className="generic-field">
              <span className="generic-field-label">{field.label}</span>
              <span className="generic-field-value">{field.value}</span>
            </div>
          ))}
        </div>
      )}
      {nestedSections}
    </>
  );
}

/**
 * Render a single list item (simplified).
 */
function renderListItem(item: ElementFormData, template: UIElementSchema): string {
  // Try to extract a meaningful value from the item
  if (typeof item === 'object' && item !== null) {
    // Check for direct value
    if ('value' in item && isProvided(item.value)) {
      return formatValue(item.value);
    }

    // Check for elements (collection-type items)
    if ('elements' in item && typeof item.elements === 'object') {
      const elementsRecord = item.elements as Record<string, ElementFormData>;
      const values = Object.entries(elementsRecord)
        .map(([key, val]) => {
          if (typeof val === 'object' && val !== null && 'value' in val && isProvided(val.value)) {
            return `${key}: ${formatValue(val.value)}`;
          }
          return null;
        })
        .filter(Boolean);
      if (values.length > 0) {
        return values.join(', ');
      }
    }
  }

  return template.idShort || 'Item';
}

/**
 * GenericCard component.
 */
export default function GenericCard({ schema, formData }: GenericCardProps) {
  const content = renderElements(schema.elements, formData, 'elements', 0);

  const hasContent = content !== null;

  return (
    <div className="passport-card generic-card">
      <div className="generic-card-header">
        <h2>{schema.idShort}</h2>
        {schema.semanticId && <div className="semantic-id">{schema.semanticId}</div>}
      </div>

      <div className="generic-card-body">
        {hasContent ? (
          content
        ) : (
          <div className="generic-empty">
            <p>No data entered yet.</p>
            <p>Switch to Editor mode to fill in the form fields.</p>
          </div>
        )}
      </div>

      <div className="passport-card-footer">
        {schema.templateName && <span>Template: {schema.templateName}</span>}
      </div>
    </div>
  );
}
