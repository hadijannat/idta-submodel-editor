/**
 * Main application component for the IDTA Submodel Editor.
 */

import { useEffect, useState, useCallback, useMemo } from 'react';
import { FormProvider, useWatch } from 'react-hook-form';
import type {
  SubmodelUISchema,
  TemplateInfo,
  TemplateVersionInfo,
  UIElementSchema,
} from './types/ui-schema';
import type { ElementFormData, SubmodelFormData } from './types/aas-elements';
import { isRequired } from './types/aas-elements';
import { useSubmodelForm } from './hooks/useSubmodelForm';
import TemplateSelector from './components/TemplateSelector';
import AASRenderer from './components/AASRenderer';
import ExportPanel from './components/ExportPanel';
import { getTemplateVersions } from './services/api';
import './App.css';

type CompletionMetrics = {
  required: number;
  completed: number;
};

const hasValue = (value: unknown): boolean => {
  if (value === null || value === undefined) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  if (typeof value === 'number') return true;
  if (typeof value === 'boolean') return true;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'object') {
    return Object.values(value).some(hasValue);
  }
  return true;
};

const countElementCompletion = (
  element: UIElementSchema,
  data?: ElementFormData
): CompletionMetrics => {
  const required = isRequired(element.cardinality);

  switch (element.modelType) {
    case 'SubmodelElementCollection': {
      const children = element.elements ?? [];
      return children.reduce<CompletionMetrics>(
        (acc, child) => {
          const childData = data?.elements?.[child.idShort];
          const counts = countElementCompletion(child, childData);
          acc.required += counts.required;
          acc.completed += counts.completed;
          return acc;
        },
        { required: 0, completed: 0 }
      );
    }

    case 'Entity': {
      const statements = element.statements ?? [];
      return statements.reduce<CompletionMetrics>(
        (acc, child) => {
          const childData = data?.statements?.[child.idShort];
          const counts = countElementCompletion(child, childData);
          acc.required += counts.required;
          acc.completed += counts.completed;
          return acc;
        },
        { required: 0, completed: 0 }
      );
    }

    case 'SubmodelElementList': {
      const items = data?.items ?? [];
      if (items.length === 0) {
        return required ? { required: 1, completed: 0 } : { required: 0, completed: 0 };
      }

      if (element.itemTemplate) {
        return items.reduce<CompletionMetrics>(
          (acc, item) => {
            const counts = countElementCompletion(element.itemTemplate as UIElementSchema, item);
            acc.required += counts.required;
            acc.completed += counts.completed;
            return acc;
          },
          { required: 0, completed: 0 }
        );
      }

      return required ? { required: 1, completed: 1 } : { required: 0, completed: 0 };
    }

    case 'Range': {
      if (!required) return { required: 0, completed: 0 };
      const filled = hasValue(data?.min) && hasValue(data?.max);
      return { required: 1, completed: filled ? 1 : 0 };
    }

    case 'MultiLanguageProperty': {
      if (!required) return { required: 0, completed: 0 };
      const filled = hasValue(data?.value);
      return { required: 1, completed: filled ? 1 : 0 };
    }

    default: {
      if (!required) return { required: 0, completed: 0 };
      const filled = hasValue(data?.value);
      return { required: 1, completed: filled ? 1 : 0 };
    }
  }
};

const computeCompletion = (
  schema: SubmodelUISchema | null,
  values?: SubmodelFormData
): CompletionMetrics => {
  if (!schema) return { required: 0, completed: 0 };

  return schema.elements.reduce<CompletionMetrics>(
    (acc, element) => {
      const elementData = values?.elements?.[element.idShort];
      const counts = countElementCompletion(element, elementData);
      acc.required += counts.required;
      acc.completed += counts.completed;
      return acc;
    },
    { required: 0, completed: 0 }
  );
};

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
      title: 'Fill Required Fields',
      description: 'Complete mandatory elements',
    },
    {
      id: 4,
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
                  placeholder="1.0"
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
              Continue to fields
            </button>
          </div>
        </div>
      );
    }

    if (wizardStep === 3) {
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

          <div className="wizard-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => handleStepChange(2)}
            >
              Back to configuration
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => handleStepChange(4)}
            >
              Review & export
            </button>
          </div>
        </div>
      );
    }

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
            <h4>Export readiness</h4>
            <p>Export actions are available in the panel on the right.</p>
          </div>
        </div>

        <div className="wizard-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => handleStepChange(3)}
          >
            Back to fields
          </button>
        </div>
      </div>
    );
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
                      {step.id === 3 && schema && (
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
