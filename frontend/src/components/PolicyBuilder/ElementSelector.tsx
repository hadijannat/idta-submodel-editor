/**
 * ElementSelector - Tree view of AAS elements with checkboxes for selection.
 *
 * Renders a recursive tree from the UI schema, allowing users to select
 * specific elements to include in access policies.
 */

import React, { useState, useCallback, useMemo } from 'react';
import type { UIElementSchema } from '../../types/ui-schema';

export interface SelectedElement {
  path: string;
  idShort: string;
  modelType: string;
  semanticId: string | null;
}

interface ElementSelectorProps {
  /** Elements from the UI schema */
  elements: UIElementSchema[];
  /** Currently selected element paths */
  selectedPaths: Set<string>;
  /** Callback when selection changes */
  onSelectionChange: (paths: Set<string>, selected: SelectedElement[]) => void;
  /** Optional search filter */
  searchFilter?: string;
}

interface ElementItemProps {
  element: UIElementSchema;
  path: string;
  depth: number;
  selectedPaths: Set<string>;
  expandedPaths: Set<string>;
  onToggleSelect: (path: string) => void;
  onToggleExpand: (path: string) => void;
  searchFilter: string;
}

/**
 * Get display name for an element model type
 */
function getTypeLabel(modelType: string): string {
  const labels: Record<string, string> = {
    Property: 'Prop',
    SubmodelElementCollection: 'SMC',
    SubmodelElementList: 'SML',
    MultiLanguageProperty: 'MLP',
    File: 'File',
    Blob: 'Blob',
    Range: 'Range',
    ReferenceElement: 'Ref',
    Entity: 'Entity',
    RelationshipElement: 'Rel',
    AnnotatedRelationshipElement: 'AnnRel',
    Operation: 'Op',
    Capability: 'Cap',
    BasicEventElement: 'Event',
  };
  return labels[modelType] || modelType.slice(0, 4);
}

/**
 * Check if an element or its children match the search filter
 */
function matchesSearch(
  element: UIElementSchema,
  filter: string
): boolean {
  if (!filter) return true;
  const lower = filter.toLowerCase();

  // Check element's own fields
  if (element.idShort.toLowerCase().includes(lower)) return true;
  if (element.semanticLabel?.toLowerCase().includes(lower)) return true;
  if (element.semanticId?.toLowerCase().includes(lower)) return true;

  // Check children recursively
  const children = getChildren(element);
  return children.some((child) => matchesSearch(child, filter));
}

/**
 * Get children of an element based on its type
 */
function getChildren(element: UIElementSchema): UIElementSchema[] {
  if (element.modelType === 'SubmodelElementCollection') {
    return element.elements || [];
  }
  if (element.modelType === 'SubmodelElementList') {
    return element.items || [];
  }
  if (element.modelType === 'Entity') {
    return element.statements || [];
  }
  return [];
}

/**
 * Check if element has expandable children
 */
function hasChildren(element: UIElementSchema): boolean {
  return getChildren(element).length > 0;
}

/**
 * Collect all paths from an element tree
 */
function collectAllPaths(
  elements: UIElementSchema[],
  basePath: string = ''
): string[] {
  const paths: string[] = [];

  for (const element of elements) {
    const path = basePath ? `${basePath}.${element.idShort}` : element.idShort;
    paths.push(path);

    const children = getChildren(element);
    if (children.length > 0) {
      paths.push(...collectAllPaths(children, path));
    }
  }

  return paths;
}

/**
 * Single element item in the tree
 */
const ElementItem: React.FC<ElementItemProps> = ({
  element,
  path,
  depth,
  selectedPaths,
  expandedPaths,
  onToggleSelect,
  onToggleExpand,
  searchFilter,
}) => {
  const children = getChildren(element);
  const isExpanded = expandedPaths.has(path);
  const isSelected = selectedPaths.has(path);
  const hasExpandableChildren = hasChildren(element);

  // If search filter is active and element doesn't match, hide it
  if (searchFilter && !matchesSearch(element, searchFilter)) {
    return null;
  }

  const displayLabel = element.semanticLabel || element.idShort;

  return (
    <div className="element-selector__item-wrapper">
      <div
        className={`element-selector__item ${isSelected ? 'element-selector__item--selected' : ''}`}
        style={{ paddingLeft: depth * 16 }}
      >
        {hasExpandableChildren ? (
          <button
            type="button"
            className="element-selector__expand-btn"
            onClick={() => onToggleExpand(path)}
            aria-label={isExpanded ? 'Collapse' : 'Expand'}
          >
            {isExpanded ? '\u25BC' : '\u25B6'}
          </button>
        ) : (
          <span className="element-selector__expand-placeholder" />
        )}

        <input
          type="checkbox"
          className="element-selector__checkbox"
          checked={isSelected}
          onChange={() => onToggleSelect(path)}
          aria-label={`Select ${displayLabel}`}
        />

        <div className="element-selector__item-content">
          <div className="element-selector__item-label">
            <span>{displayLabel}</span>
            <span className="element-selector__item-type">
              {getTypeLabel(element.modelType)}
            </span>
          </div>
          {element.semanticId && (
            <div className="element-selector__item-semantic">
              {element.semanticId.split('/').pop()}
            </div>
          )}
        </div>
      </div>

      {hasExpandableChildren && isExpanded && (
        <div className="element-selector__children">
          {children.map((child) => (
            <ElementItem
              key={child.idShort}
              element={child}
              path={`${path}.${child.idShort}`}
              depth={depth + 1}
              selectedPaths={selectedPaths}
              expandedPaths={expandedPaths}
              onToggleSelect={onToggleSelect}
              onToggleExpand={onToggleExpand}
              searchFilter={searchFilter}
            />
          ))}
        </div>
      )}
    </div>
  );
};

/**
 * ElementSelector component
 */
export const ElementSelector: React.FC<ElementSelectorProps> = ({
  elements,
  selectedPaths,
  onSelectionChange,
  searchFilter = '',
}) => {
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(() => {
    // Start with top-level elements expanded
    return new Set(elements.map((e) => e.idShort));
  });
  const [localSearch, setLocalSearch] = useState('');

  const effectiveSearch = searchFilter || localSearch;

  // Build a map of path -> element for quick lookup
  const elementMap = useMemo(() => {
    const map = new Map<string, UIElementSchema>();

    function traverse(elems: UIElementSchema[], basePath: string) {
      for (const elem of elems) {
        const path = basePath ? `${basePath}.${elem.idShort}` : elem.idShort;
        map.set(path, elem);
        const children = getChildren(elem);
        if (children.length > 0) {
          traverse(children, path);
        }
      }
    }

    traverse(elements, '');
    return map;
  }, [elements]);

  const handleToggleSelect = useCallback(
    (path: string) => {
      const newPaths = new Set(selectedPaths);

      if (newPaths.has(path)) {
        newPaths.delete(path);
      } else {
        newPaths.add(path);
      }

      // Convert paths to SelectedElement objects
      const selected: SelectedElement[] = Array.from(newPaths).map((p) => {
        const elem = elementMap.get(p);
        return {
          path: p,
          idShort: elem?.idShort || p.split('.').pop() || '',
          modelType: elem?.modelType || 'Property',
          semanticId: elem?.semanticId || null,
        };
      });

      onSelectionChange(newPaths, selected);
    },
    [selectedPaths, onSelectionChange, elementMap]
  );

  const handleToggleExpand = useCallback((path: string) => {
    setExpandedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  const handleSelectAll = useCallback(() => {
    const allPaths = collectAllPaths(elements);
    const newPaths = new Set(allPaths);

    const selected: SelectedElement[] = Array.from(newPaths).map((p) => {
      const elem = elementMap.get(p);
      return {
        path: p,
        idShort: elem?.idShort || p.split('.').pop() || '',
        modelType: elem?.modelType || 'Property',
        semanticId: elem?.semanticId || null,
      };
    });

    onSelectionChange(newPaths, selected);
  }, [elements, onSelectionChange, elementMap]);

  const handleSelectNone = useCallback(() => {
    onSelectionChange(new Set(), []);
  }, [onSelectionChange]);

  const handleExpandAll = useCallback(() => {
    const allPaths = collectAllPaths(elements);
    setExpandedPaths(new Set(allPaths));
  }, [elements]);

  const handleCollapseAll = useCallback(() => {
    setExpandedPaths(new Set());
  }, []);

  if (elements.length === 0) {
    return (
      <div className="element-selector__empty">
        No elements available. Load a submodel schema first.
      </div>
    );
  }

  return (
    <div className="element-selector">
      <div className="element-selector__search">
        <span className="element-selector__search-icon">{'\u{1F50D}'}</span>
        <input
          type="text"
          placeholder="Search elements..."
          value={localSearch}
          onChange={(e) => setLocalSearch(e.target.value)}
          aria-label="Search elements"
        />
      </div>

      <div className="element-selector__actions">
        <button
          type="button"
          className="element-selector__action-btn"
          onClick={handleSelectAll}
        >
          Select All
        </button>
        <button
          type="button"
          className="element-selector__action-btn"
          onClick={handleSelectNone}
        >
          Clear
        </button>
        <button
          type="button"
          className="element-selector__action-btn"
          onClick={handleExpandAll}
        >
          Expand
        </button>
        <button
          type="button"
          className="element-selector__action-btn"
          onClick={handleCollapseAll}
        >
          Collapse
        </button>
      </div>

      <div className="element-selector__tree">
        {elements.map((element) => (
          <ElementItem
            key={element.idShort}
            element={element}
            path={element.idShort}
            depth={0}
            selectedPaths={selectedPaths}
            expandedPaths={expandedPaths}
            onToggleSelect={handleToggleSelect}
            onToggleExpand={handleToggleExpand}
            searchFilter={effectiveSearch}
          />
        ))}
      </div>
    </div>
  );
};

export default ElementSelector;
