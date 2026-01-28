/**
 * ListField component for rendering SubmodelElementList elements.
 *
 * Uses React Hook Form's useFieldArray for dynamic add/remove.
 * Conditionally uses virtualization for lists exceeding VIRTUALIZATION_THRESHOLD.
 */

import React, { useState, useCallback } from 'react';
import { useFormContext, useFieldArray, useWatch } from 'react-hook-form';
import type { UIElementSchema } from '../../types/ui-schema';
import type { ElementFormData } from '../../types/aas-elements';
import { getMaxItems, getMinItems } from '../../types/aas-elements';
import SemanticChip from '../semantic/SemanticChip';
import SemanticLookupModal from '../semantic/SemanticLookupModal';
import { VirtualizedList } from './VirtualizedList';

/** Threshold above which virtualization is enabled for performance */
const VIRTUALIZATION_THRESHOLD = 20;

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
  const withSemanticDefaults = (
    defaults: ElementFormData,
    source?: UIElementSchema | null
  ): ElementFormData => ({
    ...defaults,
    semanticId: source?.semanticId ?? null,
    valueId: source?.valueId ?? null,
    semanticIdListElement: source?.semanticIdListElement ?? null,
  });

  if (!template) return withSemanticDefaults({ value: '' });

  switch (template.modelType) {
    case 'Property':
      return withSemanticDefaults({ value: template.value ?? '' }, template);

    case 'MultiLanguageProperty':
      return withSemanticDefaults({ value: {} }, template);

    case 'SubmodelElementCollection': {
      const elements: Record<string, ElementFormData> = {};
      for (const child of template.elements || []) {
        elements[child.idShort] = createDefaultItem(child);
      }
      return withSemanticDefaults({ elements }, template);
    }

    case 'Range':
      return withSemanticDefaults({ min: '', max: '' }, template);

    case 'File':
      return withSemanticDefaults({ value: '', contentType: '' }, template);

    case 'ReferenceElement':
      return withSemanticDefaults({ value: '' }, template);

    default:
      return withSemanticDefaults({ value: '' }, template);
  }
}

/**
 * Renders a dynamic list with add/remove functionality.
 * Uses virtualization for large lists (> VIRTUALIZATION_THRESHOLD items).
 */
export const ListField: React.FC<ListFieldProps> = ({
  path,
  schema,
  depth,
  renderItem,
}) => {
  const { control, setValue } = useFormContext();
  const [isSemanticOpen, setSemanticOpen] = useState(false);
  const semanticIdListElement = useWatch({
    control,
    name: `${path}.semanticIdListElement`,
  }) as string | null | undefined;

  const { fields, append, remove, move } = useFieldArray({
    control,
    name: `${path}.items` as const,
  });

  const displayTitle = schema.semanticLabel || schema.idShort;
  const itemTemplate = schema.itemTemplate;
  const minItems = getMinItems(schema.cardinality);
  const maxItems = getMaxItems(schema.cardinality);
  const canRemove = fields.length > minItems;
  const canAdd = maxItems === undefined || fields.length < maxItems;

  // Determine if virtualization should be used
  const useVirtualization = fields.length > VIRTUALIZATION_THRESHOLD;

  const handleAddItem = useCallback(() => {
    const newItem = createDefaultItem(itemTemplate || null);
    append(newItem);
  }, [itemTemplate, append]);

  const handleRemoveItem = useCallback(
    (index: number) => {
      if (canRemove || fields.length > minItems) {
        remove(index);
      }
    },
    [canRemove, fields.length, minItems, remove]
  );

  const handleMoveUp = useCallback(
    (index: number) => {
      if (index > 0) {
        move(index, index - 1);
      }
    },
    [move]
  );

  const handleMoveDown = useCallback(
    (index: number) => {
      if (index < fields.length - 1) {
        move(index, index + 1);
      }
    },
    [move, fields.length]
  );

  // Get the effective item schema for rendering
  const getItemSchema = useCallback(
    (index: number): UIElementSchema => {
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
    },
    [schema.items, itemTemplate]
  );

  // Unified render function for a single list item
  const renderListItem = useCallback(
    (field: { id: string }, index: number) => {
      const itemSchema = getItemSchema(index);
      return (
        <div key={field.id} className="aas-list-item" data-index={index}>
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
    },
    [
      getItemSchema,
      schema.orderRelevant,
      handleMoveUp,
      handleMoveDown,
      handleRemoveItem,
      canRemove,
      fields.length,
      minItems,
      renderItem,
      path,
    ]
  );

  return (
    <div className={`aas-list aas-depth-${depth}`} data-id-short={schema.idShort}>
      <div className="aas-list-header">
        <span className="aas-list-title">{displayTitle}</span>
        <span className="aas-list-count">({fields.length} items)</span>
        {schema.cardinality !== '[1]' && (
          <span className="aas-cardinality">{schema.cardinality}</span>
        )}
        {useVirtualization && (
          <span className="aas-virtualized-badge" title="Virtualized for performance">
            ⚡
          </span>
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

      <div className="semantic-row">
        <span className="aas-sublabel">List semantic</span>
        <SemanticChip
          semanticId={semanticIdListElement}
          onOpen={() => setSemanticOpen(true)}
          onClear={() =>
            setValue(`${path}.semanticIdListElement`, null, { shouldDirty: true })
          }
        />
      </div>

      {schema.description?.en && (
        <p className="aas-list-description">{schema.description.en}</p>
      )}

      <div className="aas-list-items">
        {fields.length === 0 ? (
          <div className="aas-list-empty">
            <p>No items. Click "Add Item" to add one.</p>
          </div>
        ) : useVirtualization ? (
          // Use virtualized rendering for large lists
          <VirtualizedList
            fields={fields}
            renderItem={renderListItem}
            className="aas-list-virtualized"
          />
        ) : (
          // Standard rendering for small lists
          fields.map((field, index) => renderListItem(field, index))
        )}
      </div>

      <SemanticLookupModal
        isOpen={isSemanticOpen}
        onClose={() => setSemanticOpen(false)}
        onApply={(value) =>
          setValue(`${path}.semanticIdListElement`, value, { shouldDirty: true })
        }
        currentSemanticId={semanticIdListElement ?? undefined}
        elementType={schema.modelType}
        valueType={schema.valueTypeListElement ?? undefined}
        defaultKind="property"
      />
    </div>
  );
};

export default ListField;
