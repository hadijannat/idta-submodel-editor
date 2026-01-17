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
  extractList,
  extractLangStringValue,
  extractPrimitiveValue,
  extractSafeUrl,
  isProvided,
  formatValue,
} from '../utils/valueExtractors';
import { usePassportI18n } from '../i18n';
import type { TranslationKey } from '../i18n';

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

function renderValueNode(value: string): React.ReactNode {
  const href = extractSafeUrl(value);
  if (href) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer">
        {value}
      </a>
    );
  }
  return value;
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
      const val =
        extractPrimitive(formData, `${path}.value`) ?? extractPrimitive(formData, path);
      if (!isProvided(val)) return undefined;
      return String(val);
    }

    case 'Range': {
      const min = extractPrimitive(formData, `${path}.min`);
      const max = extractPrimitive(formData, `${path}.max`);
      const minProvided = isProvided(min);
      const maxProvided = isProvided(max);
      if (!minProvided && !maxProvided) return undefined;
      if (minProvided && maxProvided) {
        return `${formatValue(min)} – ${formatValue(max)}`;
      }
      if (minProvided) {
        return `≥ ${formatValue(min)}`;
      }
      return `≤ ${formatValue(max)}`;
    }

    default:
      return undefined;
  }
}

/**
 * Translation function type for i18n.
 */
type TranslateFunc = (key: TranslationKey, params?: Record<string, string | number>) => string;

/**
 * Recursively render elements from the schema.
 */
function renderElements(
  elements: UIElementSchema[],
  formData: SubmodelFormData | undefined,
  basePath: string,
  depth: number,
  t: TranslateFunc
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
      // Check if any child has data
      const childContent = renderElements(
        element.elements,
        formData,
        `${path}.elements`,
        depth + 1,
        t
      );

      if (childContent) {
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
        const displayItems = listItems
          .map((item, index) => ({
            index,
            value: renderListItem(item),
          }))
          .filter((entry) => entry.value !== null);

        if (displayItems.length === 0) {
          continue;
        }
        nestedSections.push(
          <div key={element.idShort} className="generic-nested">
            <div className="generic-nested-title">
              {element.semanticLabel || element.idShort} ({t('generic.itemsCount', { count: displayItems.length })})
            </div>
            {displayItems.map((item) => (
              <div key={item.index} className="generic-field">
                <span className="generic-field-label">{t('generic.itemLabel', { index: item.index + 1 })}</span>
                <span className="generic-field-value">
                  {renderValueNode(item.value!)}
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
              <span className="generic-field-value">{renderValueNode(field.value)}</span>
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
function renderListItem(item: ElementFormData): string | null {
  // Try to extract a meaningful value from the item
  if (typeof item === 'object' && item !== null) {
    // Check for direct value
    if ('value' in item && isProvided(item.value)) {
      const langValue = extractLangStringValue(item.value, ['en', 'de']);
      if (langValue) return langValue;
      return formatValue(item.value);
    }

    // Check for elements (collection-type items)
    if ('elements' in item && typeof item.elements === 'object') {
      const elementsRecord = item.elements as Record<string, ElementFormData>;
      const values: string[] = [];
      for (const [key, val] of Object.entries(elementsRecord)) {
        if (!val || typeof val !== 'object') continue;
        const primitive = extractPrimitiveValue(val);
        const langValue = extractLangStringValue(val.value ?? val, ['en', 'de']);
        const display = langValue ?? (isProvided(primitive) ? formatValue(primitive) : undefined);
        if (display) values.push(`${key}: ${display}`);
        if (values.length >= 3) break;
      }
      if (values.length > 0) return values.join(', ');
    }
  }

  return null;
}

/**
 * GenericCard component.
 */
export default function GenericCard({ schema, formData }: GenericCardProps) {
  const { t } = usePassportI18n();
  const content = renderElements(schema.elements, formData, 'elements', 0, t);

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
            <p>{t('generic.emptyMessage')}</p>
            <p>{t('generic.emptyHint')}</p>
          </div>
        )}
      </div>

      <div className="passport-card-footer">
        {schema.templateName && <span>{t('generic.templateLabel')} {schema.templateName}</span>}
      </div>
    </div>
  );
}
