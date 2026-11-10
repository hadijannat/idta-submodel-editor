/**
 * TemplateSelector component for browsing and selecting IDTA templates.
 */

import React, { useState } from 'react';
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
  const [showDeprecated, setShowDeprecated] = useState(false);
  const statusFilter = showDeprecated ? 'all' : 'published';
  const {
    templates,
    loading,
    error,
    search,
    setSearch,
    refresh,
    cached,
  } = useTemplateList({ status: statusFilter });

  return (
    <div className="template-selector">
      <div className="template-selector-header">
        <h2>IDTA Submodel Templates</h2>
        <div className="template-selector-actions">
          <label className="template-filter">
            <input
              type="checkbox"
              checked={showDeprecated}
              onChange={(e) => setShowDeprecated(e.target.checked)}
            />
            Show deprecated
          </label>
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

      {!loading && !error && templates.length > 0 && (
        <p className="template-selector-cache-notice">
          {templates.length} template{templates.length === 1 ? '' : 's'}
          {cached ? ' (cached list)' : ''} · the newest release of each template is used
          unless you pick another version in the next step
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
          templates.map((template, index) => (
            <React.Fragment key={`${template.status ?? 'published'}:${template.name}`}>
            {template.group && templates[index - 1]?.group !== template.group && (
              <div className="template-group-heading">
                {template.group}
                <span className="template-group-count">
                  {templates.filter((entry) => entry.group === template.group).length} parts
                </span>
              </div>
            )}
            <div
              className={`template-item ${template.group ? 'template-item-part' : ''} ${selectedTemplate === template.name ? 'selected' : ''}`}
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
                {template.status === 'deprecated' && (
                  <span className="template-status template-status-deprecated">
                    Deprecated
                  </span>
                )}
                <span className="template-title">
                  {template.group && template.part
                    ? template.part
                    : template.title || template.name}
                </span>
                {template.latest_version && (
                  <span className="template-version" title="Latest published release">
                    v{template.latest_version}
                  </span>
                )}
              </div>
              <div className="template-item-name">{template.name}</div>
              <div className="template-item-meta">
                {template.versions && template.versions.length > 1 && (
                  <span>{template.versions.length} releases</span>
                )}
                {template.has_specification && <span>Specification PDF</span>}
              </div>
            </div>
            </React.Fragment>
          ))
        )}
      </div>
    </div>
  );
};

export default TemplateSelector;
