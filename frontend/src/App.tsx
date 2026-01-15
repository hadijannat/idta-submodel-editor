/**
 * Main application component for the IDTA Submodel Editor.
 */

import React, { useEffect, useState, useCallback } from 'react';
import { FormProvider } from 'react-hook-form';
import type { TemplateInfo, TemplateVersionInfo } from './types/ui-schema';
import { useSubmodelForm } from './hooks/useSubmodelForm';
import TemplateSelector from './components/TemplateSelector';
import AASRenderer from './components/AASRenderer';
import ExportPanel from './components/ExportPanel';
import { getTemplateVersions } from './services/api';
import './App.css';

/**
 * Main application component.
 *
 * Orchestrates the template selection, form rendering, and export flow.
 */
function App() {
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateInfo | null>(null);
  const [templateVersions, setTemplateVersions] = useState<TemplateVersionInfo[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<string | null>(null);
  const templateStatus = selectedTemplate?.status ?? 'published';

  const {
    schema,
    form,
    loading,
    error,
    validating,
    validationResult,
    loadSchema,
    validate,
    exportAasx,
    exportJson,
    exportPdf,
    verifyExport,
    resetForm,
  } = useSubmodelForm({
    templateName: selectedTemplate?.name,
    templateStatus,
    templateVersion: selectedVersion ?? null,
  });

  const handleTemplateSelect = useCallback(
    (template: TemplateInfo) => {
      setSelectedTemplate(template);
      setSelectedVersion(null);
    },
    []
  );

  useEffect(() => {
    let active = true;

    const loadVersions = async () => {
      if (!selectedTemplate) {
        setTemplateVersions([]);
        setSelectedVersion(null);
        return;
      }

      setSelectedVersion(null);
      try {
        const versions = await getTemplateVersions(
          selectedTemplate.name,
          templateStatus
        );
        if (!active) return;
        setTemplateVersions(versions);
      } catch {
        if (!active) return;
        setTemplateVersions([]);
        setSelectedVersion(null);
      }
    };

    loadVersions();

    return () => {
      active = false;
    };
  }, [selectedTemplate, templateStatus]);


  return (
    <div className="app">
      <header className="app-header">
        <h1>IDTA Submodel Template Editor</h1>
        <p className="app-subtitle">
          Universal metamodel-driven editor for Asset Administration Shell submodels
        </p>
      </header>

      <div className="app-layout">
        <aside className="app-sidebar">
          <TemplateSelector
            onSelect={handleTemplateSelect}
            selectedTemplate={selectedTemplate?.name}
          />
        </aside>

        <main className="app-main">
          {!selectedTemplate ? (
            <div className="app-welcome">
              <h2>Welcome to the IDTA Submodel Editor</h2>
              <p>Select a template from the sidebar to begin editing.</p>
              <div className="app-features">
                <div className="feature">
                  <h3>Universal Editing</h3>
                  <p>
                    Edit any IDTA submodel template without code modifications.
                    The editor dynamically renders forms based on the template
                    structure.
                  </p>
                </div>
                <div className="feature">
                  <h3>Metadata Preservation</h3>
                  <p>
                    All qualifiers, semantic IDs, and embedded data specifications
                    are preserved during editing and export.
                  </p>
                </div>
                <div className="feature">
                  <h3>Multiple Export Formats</h3>
                  <p>
                    Export your filled submodels as AASX packages, JSON files,
                    or PDF reports.
                  </p>
                </div>
              </div>
            </div>
          ) : loading ? (
            <div className="app-loading">
              <span className="spinner" />
              <p>Loading template schema...</p>
            </div>
          ) : error ? (
            <div className="app-error" role="alert">
              <h2>Error Loading Template</h2>
              <p>{error}</p>
              <button
                type="button"
                onClick={() =>
                  loadSchema(
                    selectedTemplate.name,
                    templateStatus,
                    selectedVersion ?? null
                  )
                }
              >
                Retry
              </button>
            </div>
          ) : schema ? (
            <FormProvider {...form}>
              <form
                className="submodel-form"
                onSubmit={form.handleSubmit(() => {})}
              >
                <div className="submodel-header">
                  <h2>{schema.idShort}</h2>
                  {(schema.templateName || selectedTemplate?.name) && (
                    <p className="submodel-template-id">
                      Template ID:{' '}
                      <span>
                        {schema.templateName || selectedTemplate?.name}
                      </span>
                    </p>
                  )}
                  {selectedTemplate?.status === 'deprecated' && (
          <p className="submodel-template-status">
                      <span className="template-status template-status-deprecated">
                        Deprecated
                      </span>
                    </p>
                  )}
                  {templateVersions.length > 0 && (
                    <div className="submodel-template-version">
                      <label htmlFor="template-version">Version</label>
                      <select
                        id="template-version"
                        value={selectedVersion ?? ''}
                        onChange={(e) =>
                          setSelectedVersion(e.target.value || null)
                        }
                      >
                        <option value="">Latest</option>
                        {templateVersions.map((version) => (
                          <option
                            key={version.version}
                            value={version.version}
                          >
                            {version.version}
                          </option>
                        ))}
                      </select>
                    </div>
                  )}
                  {schema.semanticId && (
                    <p className="submodel-semantic-id">
                      Semantic ID: {schema.semanticId}
                    </p>
                  )}
                  {schema.description?.en && (
                    <p className="submodel-description">
                      {schema.description.en}
                    </p>
                  )}
                </div>

                <div className="submodel-elements">
                  {schema.elements.map((element) => (
                    <AASRenderer
                      key={element.idShort}
                      schema={element}
                      path={`elements.${element.idShort}`}
                      depth={0}
                    />
                  ))}
                </div>
              </form>
            </FormProvider>
          ) : null}
        </main>

        {selectedTemplate && schema && (
          <aside className="app-export-sidebar">
            <ExportPanel
              templateName={selectedTemplate.name}
              onExportAasx={exportAasx}
              onExportJson={exportJson}
              onExportPdf={exportPdf}
              onVerify={verifyExport}
              onValidate={validate}
              onReset={resetForm}
              validating={validating}
              validationResult={validationResult}
            />
          </aside>
        )}
      </div>

      <footer className="app-footer">
        <p>
          IDTA Submodel Template Editor | Built with Eclipse BaSyx SDK |{' '}
          <a
            href="https://github.com/admin-shell-io/submodel-templates"
            target="_blank"
            rel="noopener noreferrer"
          >
            IDTA Templates Repository
          </a>
        </p>
      </footer>
    </div>
  );
}

export default App;
