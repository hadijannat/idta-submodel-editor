/**
 * TemplateSelector component for browsing and selecting IDTA templates.
 */

import React from 'react';
import type { TemplateInfo } from '../../types/ui-schema';
import { useTemplateList } from '../../hooks/useTemplateList';

interface TemplateSelectorProps {
  /** Called when a template is selected */
  onSelect: (template: TemplateInfo) => void;
  /** Currently selected template name */
  selectedTemplate?: string;
}

/**
 * Displays a searchable list of available IDTA templates.
 */
export const TemplateSelector: React.FC<TemplateSelectorProps> = ({
  onSelect,
  selectedTemplate,
}) => {
  const {
    templates,
    loading,
    error,
    search,
    setSearch,
    refresh,
    cached,
  } = useTemplateList();

  return (
    <div className="template-selector">
      <div className="template-selector-header">
        <h2>IDTA Submodel Templates</h2>
        <button
          type="button"
          className="btn btn-refresh"
          onClick={refresh}
          disabled={loading}
          title="Refresh from GitHub"
        >
          {loading ? 'Loading...' : '↻ Refresh'}
        </button>
      </div>

      <div className="template-selector-search">
        <input
          type="search"
          placeholder="Search templates..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="search-input"
          aria-label="Search templates"
        />
      </div>

      {error && (
        <div className="template-selector-error" role="alert">
          <p>Error loading templates: {error}</p>
          <button type="button" onClick={refresh}>
            Retry
          </button>
        </div>
      )}

      {cached && !loading && (
        <p className="template-selector-cache-notice">
          Showing cached templates
        </p>
      )}

      <div className="template-list" role="listbox" aria-label="Available templates">
        {loading && templates.length === 0 ? (
          <div className="template-list-loading">
            <span className="spinner" />
            Loading templates...
          </div>
        ) : templates.length === 0 ? (
          <div className="template-list-empty">
            <p>No templates found</p>
            {search && <p>Try adjusting your search</p>}
          </div>
        ) : (
          templates.map((template) => (
            <div
              key={template.name}
              className={`template-item ${selectedTemplate === template.name ? 'selected' : ''}`}
              role="option"
              aria-selected={selectedTemplate === template.name}
              onClick={() => onSelect(template)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onSelect(template);
                }
              }}
              tabIndex={0}
            >
              <div className="template-item-header">
                {template.idta_number && (
                  <span className="template-idta-number">
                    IDTA {template.idta_number}
                  </span>
                )}
                <span className="template-title">
                  {template.title || template.name}
                </span>
              </div>
              <div className="template-item-name">{template.name}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default TemplateSelector;
