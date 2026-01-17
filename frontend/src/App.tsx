/**
 * Main application component for the IDTA Submodel Editor.
 */

import { useEffect, useState, useCallback, useMemo } from 'react';
import { FormProvider, useWatch } from 'react-hook-form';
import type { TemplateInfo, TemplateVersionInfo } from './types/ui-schema';
import type { SubmodelFormData } from './types/aas-elements';
import { useSubmodelForm } from './hooks/useSubmodelForm';
import TemplateSelector from './components/TemplateSelector';
import AASRenderer from './components/AASRenderer';
import ExportPanel from './components/ExportPanel';
import SmartMapperPage from './components/SmartMapper/SmartMapperPage';
import PCFPanel from './components/PCFPanel';
import { isPCFTemplate } from './components/PCFPanel/pcfUtils';
import { PassportView } from './components/PassportMode';
import { getTemplateVersions } from './services/api';
import { computeCompletion } from './utils/completion';
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
  const [wizardStep, setWizardStep] = useState(1);
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

  const watchedValues = useWatch({ control: form.control }) as
    | SubmodelFormData
    | undefined;

  const completion = useMemo(
    () => computeCompletion(schema, watchedValues),
    [schema, watchedValues]
  );

  const requiredRemaining = Math.max(completion.required - completion.completed, 0);
  const completionPercent = completion.required
    ? Math.round((completion.completed / completion.required) * 100)
    : 100;

  const steps = [
    {
      id: 1,
      title: 'Choose Template',
      description: 'Select an IDTA template',
    },
    {
      id: 2,
      title: 'Configure Instance',
      description: 'Review identifiers and versioning',
    },
    {
      id: 3,
      title: 'Smart Mapper',
      description: 'Import and map CSV/XLSX data',
    },
    {
      id: 4,
      title: 'Fill Required Fields',
      description: 'Complete mandatory elements',
    },
    {
      id: 5,
      title: 'Review & Export',
      description: 'Validate and export',
    },
  ];

  const handleTemplateSelect = useCallback((template: TemplateInfo) => {
    setSelectedTemplate(template);
    setSelectedVersion(null);
    setWizardStep(2);
  }, []);

  const canConfigure = !!selectedTemplate;
  const canEdit = !!schema && !loading && !error;

  const handleStepChange = useCallback(
    (step: number) => {
      if (step === 1) {
        setWizardStep(1);
        return;
      }
      if (step === 2 && canConfigure) {
        setWizardStep(2);
        return;
      }
      if (step >= 3 && canEdit) {
        setWizardStep(step);
      }
    },
    [canConfigure, canEdit]
  );

  useEffect(() => {
    if (!selectedTemplate) {
      setWizardStep(1);
    }
  }, [selectedTemplate]);

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

  const renderStepContent = () => {
    if (wizardStep === 1) {
      return (
        <div className="wizard-panel">
          <div className="wizard-panel-header">
            <h2>Choose Template</h2>
            <p>Select an official IDTA submodel template to get started.</p>
          </div>
          <TemplateSelector
            onSelect={handleTemplateSelect}
            selectedTemplate={selectedTemplate?.name}
          />
          <div className="wizard-actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => handleStepChange(2)}
              disabled={!selectedTemplate}
            >
              Continue to configuration
            </button>
          </div>
        </div>
      );
    }

    if (!selectedTemplate) {
      return (
        <div className="app-welcome">
          <h2>Choose a template to continue</h2>
          <p>Select a template in step 1 to unlock configuration and editing.</p>
        </div>
      );
    }

    if (loading) {
      return (
        <div className="app-loading">
          <span className="spinner" />
          <p>Loading template schema...</p>
        </div>
      );
    }

    if (error) {
      return (
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
      );
    }

    if (!schema) {
      return null;
    }

    if (wizardStep === 2) {
      return (
        <div className="wizard-panel">
          <div className="wizard-panel-header">
            <h2>Configure Instance</h2>
            <p>Review identifiers and choose the template version you want to instantiate.</p>
          </div>

          <div className="wizard-card">
            <div className="template-summary">
              <div>
                <p className="template-summary-title">
                  {selectedTemplate.title || selectedTemplate.name}
                </p>
                <p className="template-summary-subtitle">{selectedTemplate.name}</p>
              </div>
              <div className="template-summary-meta">
                {selectedTemplate.idta_number && (
                  <span className="template-idta-number">
                    IDTA {selectedTemplate.idta_number}
                  </span>
                )}
                {selectedTemplate.status === 'deprecated' && (
                  <span className="template-status template-status-deprecated">
                    Deprecated
                  </span>
                )}
              </div>
            </div>

            {templateVersions.length > 0 && (
              <div className="form-field">
                <label htmlFor="template-version">Template version</label>
                <select
                  id="template-version"
                  value={selectedVersion ?? ''}
                  onChange={(e) => setSelectedVersion(e.target.value || null)}
                >
                  <option value="">Latest</option>
                  {templateVersions.map((version) => (
                    <option key={version.version} value={version.version}>
                      {version.version}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          <div className="wizard-card">
            <h3>Instance metadata</h3>
            <div className="metadata-grid">
              <label className="form-field">
                <span>idShort</span>
                <input
                  type="text"
                  placeholder="Short identifier"
                  {...form.register('metadata.idShort')}
                />
              </label>
              <label className="form-field">
                <span>Submodel ID</span>
                <input
                  type="text"
                  placeholder="urn:..."
                  {...form.register('metadata.submodelId')}
                />
              </label>
              <label className="form-field">
                <span>Version</span>
                <input
                  type="text"
                  placeholder="1"
                  {...form.register('metadata.administration.version')}
                />
              </label>
              <label className="form-field">
                <span>Revision</span>
                <input
                  type="text"
                  placeholder="0"
                  {...form.register('metadata.administration.revision')}
                />
              </label>
              <label className="form-field">
                <span>Template ID</span>
                <input
                  type="text"
                  placeholder="template-id"
                  {...form.register('metadata.administration.templateId')}
                />
                <small>Copied into Administration.templateId on export.</small>
              </label>
            </div>
          </div>

          <div className="wizard-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => handleStepChange(1)}
            >
              Back to templates
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => handleStepChange(3)}
              disabled={!schema}
            >
              Continue to Smart Mapper
            </button>
          </div>
        </div>
      );
    }

    if (wizardStep === 3) {
      return (
        <SmartMapperPage
          schema={schema}
          templateName={selectedTemplate.name}
          templateStatus={templateStatus}
          templateVersion={selectedVersion}
          form={form}
          onContinue={() => handleStepChange(4)}
        />
      );
    }

    if (wizardStep === 4) {
      const metadataIdShort =
        watchedValues?.metadata &&
        typeof watchedValues.metadata === 'object' &&
        watchedValues.metadata !== null
          ? (watchedValues.metadata as Record<string, unknown>).idShort
          : undefined;
      const headerIdShort =
        typeof metadataIdShort === 'string' && metadataIdShort
          ? metadataIdShort
          : schema.idShort;
      const headerTemplateName = schema.templateName || selectedTemplate.name;

      return (
        <div className="wizard-panel">
          <div className="submodel-header">
            <h2>{headerIdShort}</h2>
            <p className="submodel-template-id">
              Template ID: <span>{headerTemplateName}</span>
            </p>
            {selectedTemplate.status === 'deprecated' && (
              <p className="submodel-template-status">
                <span className="template-status template-status-deprecated">
                  Deprecated
                </span>
              </p>
            )}
            {schema.semanticId && (
              <p className="submodel-semantic-id">
                Semantic ID: {schema.semanticId}
              </p>
            )}
            {schema.description?.en && (
              <p className="submodel-description">{schema.description.en}</p>
            )}
          </div>

          <PassportView schema={schema} formData={watchedValues}>
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

            {isPCFTemplate(schema) &&
              import.meta.env.VITE_PCF_TOOLS_ENABLED !== 'false' && (
              <div className="pcf-panel-container">
                <h3>PCF Tools</h3>
                <p className="pcf-panel-description">
                  Carbon Footprint Calculator & Validator for IDTA 02023 compliance.
                </p>
                <PCFPanel schema={schema} form={form} />
              </div>
            )}
          </PassportView>

          <div className="wizard-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => handleStepChange(3)}
            >
              Back to Smart Mapper
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => handleStepChange(5)}
            >
              Review & export
            </button>
          </div>
        </div>
      );
    }

    if (wizardStep === 5) {
      return (
        <div className="wizard-panel">
          <div className="wizard-panel-header">
            <h2>Review & Export</h2>
          <p>Validate required fields and export when ready.</p>
        </div>

        <div className="wizard-card review-summary">
          <div className="review-summary-item">
            <h4>Completeness</h4>
            <p>
              {completion.completed}/{completion.required} required fields completed
            </p>
            <p>{requiredRemaining} required fields remaining</p>
          </div>
          <div className="review-summary-item">
            <h4>Validation</h4>
            <p>
              {validationResult?.valid
                ? 'No blocking errors'
                : 'Run validation to check for errors'}
            </p>
            <div className="review-summary-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={validate}
                disabled={validating}
              >
                {validating ? 'Validating...' : 'Run validation'}
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={resetForm}
              >
                Reset form
              </button>
            </div>
          </div>
          <div className="review-summary-item">
            <h4>Issues</h4>
            {!validationResult ? (
              <p>Run validation to see any blocking errors or warnings.</p>
            ) : validationResult.errors.length === 0 &&
              validationResult.warnings.length === 0 ? (
              <p>No issues detected.</p>
            ) : (
              <div className="issue-list">
                {validationResult.errors.map((issue) => (
                  <div key={`error-${issue}`} className="issue-item">
                    <span className="issue-badge issue-badge-error">Error</span>
                    <span>{issue}</span>
                  </div>
                ))}
                {validationResult.warnings.map((issue) => (
                  <div key={`warning-${issue}`} className="issue-item">
                    <span className="issue-badge issue-badge-warning">Warning</span>
                    <span>{issue}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="review-summary-item">
            <h4>Export readiness</h4>
            <p>Export actions are available in the panel on the right.</p>
          </div>
        </div>

          <div className="wizard-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => handleStepChange(4)}
            >
              Back to fields
            </button>
          </div>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>IDTA Submodel Template Editor</h1>
        <p className="app-subtitle">
          Universal metamodel-driven editor for Asset Administration Shell submodels
        </p>
      </header>

      <div className="app-layout wizard-layout">
        <aside className="app-sidebar wizard-sidebar">
          <div className="wizard-card wizard-stepper">
            <h3>Wizard Steps</h3>
            <div className="wizard-step-list">
              {steps.map((step) => {
                const isDisabled =
                  (step.id === 2 && !canConfigure) ||
                  (step.id >= 3 && !canEdit);
                const isActive = wizardStep === step.id;
                const isCompleted = wizardStep > step.id;

                return (
                  <button
                    key={step.id}
                    type="button"
                    className={`wizard-step${isActive ? ' active' : ''}${
                      isCompleted ? ' completed' : ''
                    }`}
                    onClick={() => handleStepChange(step.id)}
                    disabled={isDisabled}
                  >
                    <span className="wizard-step-index">{step.id}</span>
                    <span className="wizard-step-text">
                      <span className="wizard-step-title">{step.title}</span>
                      <span className="wizard-step-desc">{step.description}</span>
                      {step.id === 4 && schema && (
                        <span className="wizard-step-meta">
                          Required remaining: {requiredRemaining}
                        </span>
                      )}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {selectedTemplate && (
            <div className="wizard-card">
              <h4>Selected template</h4>
              <p className="template-summary-title">
                {selectedTemplate.title || selectedTemplate.name}
              </p>
              <p className="template-summary-subtitle">{selectedTemplate.name}</p>
              {selectedTemplate.status === 'deprecated' && (
                <span className="template-status template-status-deprecated">
                  Deprecated
                </span>
              )}
            </div>
          )}

          {schema && (
            <div className="wizard-card completion-card">
              <h4>Completeness meter</h4>
              <div
                className="completion-ring"
                style={{
                  ['--progress' as string]: `${completionPercent}`,
                }}
              >
                <span>{completionPercent}%</span>
              </div>
              <div className="completion-stats">
                <p>
                  Completed required: {completion.completed}/{completion.required}
                </p>
                <p>Required fields remaining: {requiredRemaining}</p>
              </div>
            </div>
          )}
        </aside>

        <main className="app-main wizard-main">
          {schema ? (
            <FormProvider {...form}>
              <form className="submodel-form" onSubmit={form.handleSubmit(() => {})}>
                {renderStepContent()}
              </form>
            </FormProvider>
          ) : (
            renderStepContent()
          )}
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
