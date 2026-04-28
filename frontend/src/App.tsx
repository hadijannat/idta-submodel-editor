// Copyright (c) 2024-2025 Hadi Jannatabadi <h.jannatabadi@iat.rwth-aachen.de>
// SPDX-License-Identifier: MIT
/**
 * Main application component for the IDTA Submodel Editor.
 */

import { useEffect, useState, useCallback, useMemo, Suspense } from 'react';
import { FormProvider, useWatch } from 'react-hook-form';
import type { TemplateInfo, TemplateVersionInfo } from './types/ui-schema';
import type { SubmodelFormData } from './types/aas-elements';
import { useSubmodelForm } from './hooks/useSubmodelForm';
import TemplateSelector from './components/TemplateSelector';
import AASRenderer from './components/AASRenderer';
import ExportPanel from './components/ExportPanel';
import PCFPanel from './components/PCFPanel';
import { isPCFTemplate } from './components/PCFPanel/pcfUtils';
import { PassportView } from './components/PassportMode';
import { MnestixBrowser } from './components/MnestixBrowser';
import { getTemplateVersions, getPublicSettings, type PublicSettings } from './services/api';
import { updateFeatureFlags } from './services/settingsApi';
import { computeCompletion } from './utils/completion';
import { useTools } from './tools/hooks/useTools';
import { getToolLaunchBlocker, toolRegistry } from './tools';
import type { ToolComponentProps } from './tools/types';
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
  const [showAASBrowser, setShowAASBrowser] = useState(false);
  const [publicSettings, setPublicSettings] = useState<PublicSettings | null>(null);
  const templateStatus = selectedTemplate?.status ?? 'published';

  // Load tool registry
  const {
    wizardSteps,
    isToolEnabled,
    utilityTools,
    refresh: refreshTools,
    loading: toolsLoading,
  } = useTools();
  const [activeUtilityTool, setActiveUtilityTool] = useState<string | null>(null);
  const [dataspaceToggleLoading, setDataspaceToggleLoading] = useState(false);
  const [dataspaceToggleError, setDataspaceToggleError] = useState<string | null>(null);
  const activeUtilityToolTitleId = activeUtilityTool
    ? `utility-tool-title-${activeUtilityTool}`
    : undefined;

  // Load public settings on mount
  useEffect(() => {
    getPublicSettings()
      .then(setPublicSettings)
      .catch((err) => console.error('Failed to load public settings:', err));
  }, []);

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
    conformanceChecking,
    conformanceResult,
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

  const visibleUtilityTools = useMemo(
    () =>
      utilityTools.filter((tool) => {
        if (tool.metadata.id === 'pcf-tools') {
          return !!schema && isPCFTemplate(schema);
        }
        return true;
      }),
    [schema, utilityTools]
  );

  const handleTemplateSelect = useCallback((template: TemplateInfo) => {
    setSelectedTemplate(template);
    setSelectedVersion(null);
    setWizardStep(2);
  }, []);

  const canConfigure = !!selectedTemplate;
  const canEdit = !!schema && !loading && !error;
  const enabledStepIds = useMemo(
    () =>
      wizardSteps
        .filter((step) => step.toolId === null || step.enabled)
        .map((step) => step.id)
        .sort((a, b) => a - b),
    [wizardSteps]
  );
  const enabledStepIdSet = useMemo(() => new Set(enabledStepIds), [enabledStepIds]);
  const stepNavigation = useMemo(() => {
    const next = new Map<number, number>();
    const previous = new Map<number, number>();

    for (let index = 0; index < enabledStepIds.length; index += 1) {
      const current = enabledStepIds[index];
      const prev = enabledStepIds[index - 1] ?? current;
      const nextStep = enabledStepIds[index + 1] ?? current;
      previous.set(current, prev);
      next.set(current, nextStep);
    }

    return { next, previous };
  }, [enabledStepIds]);

  const getNextStepId = useCallback(
    (stepId: number) => stepNavigation.next.get(stepId) ?? stepId,
    [stepNavigation]
  );

  const getPreviousStepId = useCallback(
    (stepId: number) => stepNavigation.previous.get(stepId) ?? stepId,
    [stepNavigation]
  );

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
        if (!enabledStepIdSet.has(step)) {
          return;
        }
        setWizardStep(step);
      }
    },
    [canConfigure, canEdit, enabledStepIdSet]
  );

  const handleDataspaceToggle = useCallback(async () => {
    const nextValue = !isToolEnabled('dataspace-connector');
    setDataspaceToggleLoading(true);
    setDataspaceToggleError(null);

    try {
      await updateFeatureFlags({ dataspace_enabled: nextValue });
      await refreshTools();
    } catch (err) {
      setDataspaceToggleError(
        err instanceof Error ? err.message : 'Failed to update dataspace setting'
      );
    } finally {
      setDataspaceToggleLoading(false);
    }
  }, [isToolEnabled, refreshTools]);

  useEffect(() => {
    if (!selectedTemplate) {
      setWizardStep(1);
    }
  }, [selectedTemplate]);

  useEffect(() => {
    if (!canEdit && activeUtilityTool) {
      setActiveUtilityTool(null);
    }
  }, [activeUtilityTool, canEdit]);

  useEffect(() => {
    if (
      activeUtilityTool &&
      !visibleUtilityTools.some((tool) => tool.metadata.id === activeUtilityTool)
    ) {
      setActiveUtilityTool(null);
    }
  }, [activeUtilityTool, visibleUtilityTools]);

  useEffect(() => {
    if (!activeUtilityTool) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setActiveUtilityTool(null);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeUtilityTool]);

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

  // Build tool component props
  const toolProps: ToolComponentProps = useMemo(
    () => ({
      templateName: selectedTemplate?.name ?? '',
      templateStatus: templateStatus as 'published' | 'deprecated' | 'local',
      templateVersion: selectedVersion,
      form,
      schema,
      onComplete: () => handleStepChange(getNextStepId(wizardStep)),
      onNavigate: handleStepChange,
    }),
    [
      selectedTemplate,
      templateStatus,
      selectedVersion,
      form,
      schema,
      wizardStep,
      handleStepChange,
      getNextStepId,
    ]
  );

  /**
   * Render a tool step using the registry.
   */
  const renderToolStep = (toolId: string) => {
    const backStep = getPreviousStepId(wizardStep);
    const nextStep = getNextStepId(wizardStep);
    const tool = toolRegistry.getTool(toolId);

    if (!tool) {
      return (
        <div className="wizard-panel">
          <div className="app-error" role="alert">
            <h2>Tool Not Available</h2>
            <p>The tool "{toolId}" is not available.</p>
          </div>
          <div className="wizard-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => handleStepChange(backStep)}
            >
              Back
            </button>
          </div>
        </div>
      );
    }

    const launchBlocker = getToolLaunchBlocker(tool);
    if (launchBlocker) {
      return (
        <div className="wizard-panel">
          <div className="app-welcome">
            <h2>{tool.metadata.name} is unavailable</h2>
            <p>{tool.metadata.description}</p>
            <p className="wizard-step-disabled-reason">{launchBlocker}</p>
          </div>
          <div className="wizard-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => handleStepChange(backStep)}
            >
              Back
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => handleStepChange(nextStep)}
            >
              Skip
            </button>
          </div>
        </div>
      );
    }

    const ToolComponent = tool.component;

    return (
      <div className="wizard-panel">
        <Suspense
          fallback={
            <div className="app-loading">
              <span className="spinner" />
              <p>Loading {tool.metadata.name}...</p>
            </div>
          }
        >
          <ToolComponent {...toolProps} />
        </Suspense>

        <div className="wizard-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => handleStepChange(backStep)}
          >
            Back
          </button>
          {nextStep !== wizardStep && (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => handleStepChange(nextStep)}
            >
              Continue
            </button>
          )}
        </div>
      </div>
    );
  };

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
              onClick={() => handleStepChange(getNextStepId(2))}
              disabled={!schema}
            >
              Continue
            </button>
          </div>
        </div>
      );
    }

    // Step 5: Fill Required Fields (hardcoded - contains form editor)
    if (wizardStep === 5) {
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
              onClick={() => handleStepChange(getPreviousStepId(5))}
            >
              Back
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => handleStepChange(getNextStepId(5))}
            >
              Continue
            </button>
          </div>
        </div>
      );
    }

    // Step 6: Review & Export (hardcoded - contains validation UI)
    if (wizardStep === 6) {
      const nextAfterReview = getNextStepId(6);

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
              onClick={() => handleStepChange(getPreviousStepId(6))}
            >
              Back to fields
            </button>
            {nextAfterReview !== 6 && (
              <button
                type="button"
                className="btn btn-primary"
                onClick={() => handleStepChange(nextAfterReview)}
              >
                Continue
              </button>
            )}
          </div>
        </div>
      );
    }

    const stepInfo = wizardSteps.find((step) => step.id === wizardStep);
    if (stepInfo?.toolId) {
      return renderToolStep(stepInfo.toolId);
    }

    return null;
  };

  // Render AAS Browser overlay
  if (showAASBrowser) {
    return (
      <div className="app app--browser-mode">
        <MnestixBrowser onClose={() => setShowAASBrowser(false)} />
      </div>
    );
  }

  const dataspaceEnabled = isToolEnabled('dataspace-connector');

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header-content">
          <div className="app-header-title">
            <h1>IDTA Submodel Template Editor</h1>
            <p className="app-subtitle">
              Universal metamodel-driven editor for Asset Administration Shell submodels
            </p>
          </div>
          {publicSettings?.mnestix_enabled && (
            <div className="app-header-actions">
              <button
                type="button"
                className="app-header-btn"
                onClick={() => setShowAASBrowser(true)}
              >
                AAS Browser
              </button>
            </div>
          )}
        </div>
      </header>

      <div className="app-layout wizard-layout">
        <aside className="app-sidebar wizard-sidebar">
          <div className="wizard-card wizard-stepper">
            <h3>Wizard Steps</h3>
            <div className="wizard-step-list">
              {wizardSteps.map((step) => {
                // Determine if step is disabled
                const isDisabled =
                  (step.id === 2 && !canConfigure) ||
                  (step.id >= 3 && !canEdit) ||
                  (step.toolId !== null && !step.enabled);
                const isActive = wizardStep === step.id;
                const isCompleted = wizardStep > step.id;

                return (
                  <button
                    key={step.id}
                    type="button"
                    className={`wizard-step${isActive ? ' active' : ''}${
                      isCompleted ? ' completed' : ''
                    }${!step.enabled && step.toolId ? ' disabled-tool' : ''}`}
                    onClick={() => handleStepChange(step.id)}
                    disabled={isDisabled}
                  >
                    <span className="wizard-step-index">{step.id}</span>
                    <span className="wizard-step-text">
                      <span className="wizard-step-title">{step.title}</span>
                      <span className="wizard-step-desc">{step.description}</span>
                      {step.id === 5 && schema && (
                        <span className="wizard-step-meta">
                          Required remaining: {requiredRemaining}
                        </span>
                      )}
                      {step.toolId && !step.enabled && (
                        <span className="wizard-step-meta wizard-step-disabled">
                          {step.disabledReason ?? '(disabled)'}
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

          {selectedTemplate && (
            <div className="wizard-card dataspace-toggle-card">
              <h4>Dataspace Publishing</h4>
              <p>
                Enable dataspace integration to publish submodels to Manufacturing-X /
                Catena-X.
              </p>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleDataspaceToggle}
                disabled={dataspaceToggleLoading || toolsLoading}
              >
                {dataspaceToggleLoading
                  ? 'Updating...'
                  : dataspaceEnabled
                    ? 'Disable'
                    : 'Enable'}
              </button>
              <p className="dataspace-toggle-hint">
                Requires dataspace services to be configured on the backend.
              </p>
              {dataspaceToggleError && (
                <p className="dataspace-toggle-error">{dataspaceToggleError}</p>
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

          {visibleUtilityTools.length > 0 && canEdit && (
            <div className="wizard-card utility-tools-card">
              <h4>Utility Tools</h4>
              <div className="utility-tool-list">
                {visibleUtilityTools.map((tool) => {
                  const disabledReason = getToolLaunchBlocker(tool);
                  return (
                    <button
                      key={tool.metadata.id}
                      type="button"
                      className="utility-tool-btn"
                      onClick={() => {
                        if (!disabledReason) {
                          setActiveUtilityTool(tool.metadata.id);
                        }
                      }}
                      disabled={!!disabledReason}
                      title={disabledReason ?? undefined}
                    >
                      <span className="utility-tool-name">{tool.metadata.name}</span>
                      <span className="utility-tool-desc">{tool.metadata.description}</span>
                      {disabledReason && (
                        <span className="utility-tool-status">{disabledReason}</span>
                      )}
                    </button>
                  );
                })}
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
              conformanceChecking={conformanceChecking}
              conformanceResult={conformanceResult}
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

      {activeUtilityTool && (
        <div
          className="utility-tool-overlay"
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setActiveUtilityTool(null);
            }
          }}
        >
          <div
            className="utility-tool-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby={activeUtilityToolTitleId}
          >
            <div className="utility-tool-modal-header">
              <h2 id={activeUtilityToolTitleId}>
                {utilityTools.find((t) => t.metadata.id === activeUtilityTool)?.metadata.name}
              </h2>
              <button
                type="button"
                className="utility-tool-close-btn"
                onClick={() => setActiveUtilityTool(null)}
                aria-label="Close"
              >
                &times;
              </button>
            </div>
            <div className="utility-tool-modal-content">
              <Suspense
                fallback={
                  <div className="app-loading">
                    <span className="spinner" />
                    <p>Loading tool...</p>
                  </div>
                }
              >
                {(() => {
                  const tool = toolRegistry.getTool(activeUtilityTool);
                  if (!tool) return <p>Tool not found</p>;
                  const ToolComponent = tool.component;
                  return (
                    <ToolComponent
                      {...toolProps}
                      onComplete={() => setActiveUtilityTool(null)}
                    />
                  );
                })()}
              </Suspense>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
