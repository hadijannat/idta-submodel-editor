/**
 * ListField component for rendering SubmodelElementList elements.
 *
 * Uses React Hook Form's useFieldArray for dynamic add/remove.
 */

import React from 'react';
import { useFormContext, useFieldArray } from 'react-hook-form';
import type { UIElementSchema } from '../../types/ui-schema';
import type { ElementFormData } from '../../types/aas-elements';
import { getMaxItems, getMinItems } from '../../types/aas-elements';

interface ListFieldProps {
  /** Form path for the list */
  path: string;
  /** Element schema */
  schema: UIElementSchema;
  /** Current nesting depth */
  depth: number;
  /** Render function for list items */
  renderItem: (
    itemPath: string,
    index: number,
    itemSchema: UIElementSchema
  ) => React.ReactNode;
}

/**
 * Create default value for a new list item.
 */
function createDefaultItem(template: UIElementSchema | null): ElementFormData {
  if (!template) return { value: '' };

  switch (template.modelType) {
    case 'Property':
      return { value: template.value ?? '' };

    case 'MultiLanguageProperty':
      return { value: {} };

    case 'SubmodelElementCollection': {
      const elements: Record<string, ElementFormData> = {};
      for (const child of template.elements || []) {
        elements[child.idShort] = createDefaultItem(child);
      }
      return { elements };
    }

    case 'Range':
      return { min: '', max: '' };

    case 'File':
      return { value: '', contentType: '' };

    case 'ReferenceElement':
      return { value: '' };

    default:
      return { value: '' };
  }
}

/**
 * Renders a dynamic list with add/remove functionality.
 */
export const ListField: React.FC<ListFieldProps> = ({
  path,
  schema,
  depth,
  renderItem,
}) => {
  const { control } = useFormContext();

  const { fields, append, remove, move } = useFieldArray({
    control,
    name: `${path}.items` as any,
  });

  const displayTitle = schema.semanticLabel || schema.idShort;
  const itemTemplate = schema.itemTemplate;
  const minItems = getMinItems(schema.cardinality);
  const maxItems = getMaxItems(schema.cardinality);
  const canRemove = fields.length > minItems;
  const canAdd = maxItems === undefined || fields.length < maxItems;

  const handleAddItem = () => {
    const newItem = createDefaultItem(itemTemplate || null);
    append(newItem);
  };

  const handleRemoveItem = (index: number) => {
    if (canRemove || fields.length > minItems) {
      remove(index);
    }
  };

  const handleMoveUp = (index: number) => {
    if (index > 0) {
      move(index, index - 1);
    }
  };

  const handleMoveDown = (index: number) => {
    if (index < fields.length - 1) {
      move(index, index + 1);
    }
  };

  // Get the effective item schema for rendering
  const getItemSchema = (index: number): UIElementSchema => {
    // Use existing item schema if available
    if (schema.items && schema.items[index]) {
      return schema.items[index];
    }
    // Fall back to template
    if (itemTemplate) {
      return {
        ...itemTemplate,
        idShort: `${itemTemplate.idShort}_${index}`,
      };
    }
    // Default schema
    return {
      idShort: `item_${index}`,
      modelType: 'Property',
      semanticId: null,
      semanticLabel: null,
      description: null,
      qualifiers: [],
      cardinality: '[1]',
      category: null,
      valueType: 'xs:string',
      inputType: 'text',
    };
  };

  return (
    <div className={`aas-list aas-depth-${depth}`} data-id-short={schema.idShort}>
      <div className="aas-list-header">
        <span className="aas-list-title">{displayTitle}</span>
        <span className="aas-list-count">({fields.length} items)</span>
        {schema.cardinality !== '[1]' && (
          <span className="aas-cardinality">{schema.cardinality}</span>
        )}
        <button
          type="button"
          className="aas-btn aas-btn-add"
          onClick={handleAddItem}
          disabled={!canAdd}
          aria-label="Add item"
        >
          + Add Item
        </button>
      </div>

      {schema.description?.en && (
        <p className="aas-list-description">{schema.description.en}</p>
      )}

      <div className="aas-list-items">
        {fields.length === 0 ? (
          <div className="aas-list-empty">
            <p>No items. Click "Add Item" to add one.</p>
          </div>
        ) : (
          fields.map((field, index) => {
            const itemSchema = getItemSchema(index);
            return (
              <div
                key={field.id}
                className="aas-list-item"
                data-index={index}
              >
                <div className="aas-list-item-header">
                  <span className="aas-list-item-index">Item {index + 1}</span>
                  <div className="aas-list-item-actions">
                    {schema.orderRelevant !== false && (
                      <>
                        <button
                          type="button"
                          className="aas-btn aas-btn-icon"
                          onClick={() => handleMoveUp(index)}
                          disabled={index === 0}
                          aria-label="Move up"
                          title="Move up"
                        >
                          ↑
                        </button>
                        <button
                          type="button"
                          className="aas-btn aas-btn-icon"
                          onClick={() => handleMoveDown(index)}
                          disabled={index === fields.length - 1}
                          aria-label="Move down"
                          title="Move down"
                        >
                          ↓
                        </button>
                      </>
                    )}
                    <button
                      type="button"
                      className="aas-btn aas-btn-icon aas-btn-danger"
                      onClick={() => handleRemoveItem(index)}
                      disabled={!canRemove && fields.length <= minItems}
                      aria-label="Remove item"
                      title="Remove item"
                    >
                      ×
                    </button>
                  </div>
                </div>
                <div className="aas-list-item-content">
                  {renderItem(`${path}.items.${index}`, index, itemSchema)}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default ListField;
