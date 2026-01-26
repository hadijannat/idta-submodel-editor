/**
 * TemplateOpsPanel - Template Operations utility panel.
 *
 * Provides:
 * - Template diff between versions
 * - Template validation diagnostics
 * - Migration planning
 */

import { useState, useCallback } from 'react';
import type { TemplateInfo } from '../../types/ui-schema';
import {
  diffTemplates,
  validateTemplate,
  generateMigrationPlan,
  type TemplateDiffResult,
  type ValidationDiagnostics,
  type MigrationPlan,
} from '../../services/api';
import './TemplateOps.css';

type TabId = 'diff' | 'validate' | 'migrate';

interface TemplateOpsProps {
  templates: TemplateInfo[];
  selectedTemplate?: string;
  selectedVersion?: string;
  selectedStatus?: 'published' | 'deprecated' | 'local';
  onClose?: () => void;
}

export default function TemplateOpsPanel({
  templates,
  selectedTemplate,
  selectedVersion,
  selectedStatus = 'published',
  onClose,
}: TemplateOpsProps) {
  const [activeTab, setActiveTab] = useState<TabId>('validate');

  // Validation state
  const [validationResult, setValidationResult] = useState<ValidationDiagnostics | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [validationTemplate, setValidationTemplate] = useState(selectedTemplate || '');

  // Diff state
  const [diffResult, setDiffResult] = useState<TemplateDiffResult | null>(null);
  const [isDiffing, setIsDiffing] = useState(false);
  const [sourceTemplate, setSourceTemplate] = useState(selectedTemplate || '');
  const [targetTemplate, setTargetTemplate] = useState('');

  // Migration state
  const [migrationPlan, setMigrationPlan] = useState<MigrationPlan | null>(null);
  const [isMigrating, setIsMigrating] = useState(false);
  const [migrationSource, setMigrationSource] = useState(selectedTemplate || '');
  const [migrationTarget, setMigrationTarget] = useState('');

  const [error, setError] = useState<string | null>(null);

  // Validate template
  const handleValidate = useCallback(async () => {
    if (!validationTemplate) return;
    setIsValidating(true);
    setError(null);
    try {
      const result = await validateTemplate(validationTemplate, {
        templateStatus: selectedStatus,
        templateVersion: selectedVersion ?? undefined,
      });
      setValidationResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Validation failed');
    } finally {
      setIsValidating(false);
    }
  }, [validationTemplate, selectedStatus, selectedVersion]);

  // Diff templates
  const handleDiff = useCallback(async () => {
    if (!sourceTemplate || !targetTemplate) return;
    setIsDiffing(true);
    setError(null);
    try {
      const result = await diffTemplates(sourceTemplate, targetTemplate, {
        sourceStatus: selectedStatus,
        targetStatus: selectedStatus,
      });
      setDiffResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Diff failed');
    } finally {
      setIsDiffing(false);
    }
  }, [sourceTemplate, targetTemplate, selectedStatus]);

  // Generate migration plan
  const handleMigrate = useCallback(async () => {
    if (!migrationSource || !migrationTarget) return;
    setIsMigrating(true);
    setError(null);
    try {
      const result = await generateMigrationPlan(migrationSource, migrationTarget, {
        sourceStatus: selectedStatus,
        targetStatus: selectedStatus,
      });
      setMigrationPlan(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Migration planning failed');
    } finally {
      setIsMigrating(false);
    }
  }, [migrationSource, migrationTarget, selectedStatus]);

  return (
    <div className="template-ops-panel">
      <div className="template-ops-panel__header">
        <h3>Template Operations</h3>
        {onClose && (
          <button type="button" className="btn btn-icon" onClick={onClose} aria-label="Close">
            &times;
          </button>
        )}
      </div>

      <div className="template-ops-panel__tabs">
        <button
          type="button"
          className={`tab-btn ${activeTab === 'validate' ? 'active' : ''}`}
          onClick={() => setActiveTab('validate')}
        >
          Validate
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'diff' ? 'active' : ''}`}
          onClick={() => setActiveTab('diff')}
        >
          Diff
        </button>
        <button
          type="button"
          className={`tab-btn ${activeTab === 'migrate' ? 'active' : ''}`}
          onClick={() => setActiveTab('migrate')}
        >
          Migrate
        </button>
      </div>

      {error && (
        <div className="template-ops-panel__error" role="alert">
          {error}
        </div>
      )}

      <div className="template-ops-panel__content">
        {activeTab === 'validate' && (
          <ValidateTab
            templates={templates}
            templateName={validationTemplate}
            onTemplateChange={setValidationTemplate}
            result={validationResult}
            isLoading={isValidating}
            onValidate={handleValidate}
          />
        )}
        {activeTab === 'diff' && (
          <DiffTab
            templates={templates}
            sourceTemplate={sourceTemplate}
            targetTemplate={targetTemplate}
            onSourceChange={setSourceTemplate}
            onTargetChange={setTargetTemplate}
            result={diffResult}
            isLoading={isDiffing}
            onDiff={handleDiff}
          />
        )}
        {activeTab === 'migrate' && (
          <MigrateTab
            templates={templates}
            sourceTemplate={migrationSource}
            targetTemplate={migrationTarget}
            onSourceChange={setMigrationSource}
            onTargetChange={setMigrationTarget}
            plan={migrationPlan}
            isLoading={isMigrating}
            onMigrate={handleMigrate}
          />
        )}
      </div>
    </div>
  );
}

// Validate Tab
interface ValidateTabProps {
  templates: TemplateInfo[];
  templateName: string;
  onTemplateChange: (name: string) => void;
  result: ValidationDiagnostics | null;
  isLoading: boolean;
  onValidate: () => void;
}

function ValidateTab({
  templates,
  templateName,
  onTemplateChange,
  result,
  isLoading,
  onValidate,
}: ValidateTabProps) {
  return (
    <div className="template-ops-tab">
      <div className="template-ops-form">
        <label className="form-label">
          Template
          <select
            value={templateName}
            onChange={(e) => onTemplateChange(e.target.value)}
            className="form-select"
          >
            <option value="">Select a template...</option>
            {templates.map((t) => (
              <option key={t.name} value={t.name}>
                {t.title || t.name}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="btn btn-primary"
          onClick={onValidate}
          disabled={!templateName || isLoading}
        >
          {isLoading ? 'Validating...' : 'Validate Template'}
        </button>
      </div>

      {result && (
        <div className="validation-result">
          <div className="validation-summary">
            <div className={`validation-status ${result.valid ? 'valid' : 'invalid'}`}>
              {result.valid ? 'Valid' : 'Invalid'}
            </div>
            <div className="validation-stats">
              <span>{result.element_count} elements</span>
              <span>{Math.round(result.semantic_coverage * 100)}% semantic coverage</span>
              {result.conformance_level && <span>{result.conformance_level}</span>}
            </div>
          </div>

          {result.errors.length > 0 && (
            <DiagnosticList title="Errors" items={result.errors} severity="error" />
          )}
          {result.warnings.length > 0 && (
            <DiagnosticList title="Warnings" items={result.warnings} severity="warning" />
          )}
          {result.info.length > 0 && (
            <DiagnosticList title="Info" items={result.info} severity="info" />
          )}
        </div>
      )}
    </div>
  );
}

// Diff Tab
interface DiffTabProps {
  templates: TemplateInfo[];
  sourceTemplate: string;
  targetTemplate: string;
  onSourceChange: (name: string) => void;
  onTargetChange: (name: string) => void;
  result: TemplateDiffResult | null;
  isLoading: boolean;
  onDiff: () => void;
}

function DiffTab({
  templates,
  sourceTemplate,
  targetTemplate,
  onSourceChange,
  onTargetChange,
  result,
  isLoading,
  onDiff,
}: DiffTabProps) {
  return (
    <div className="template-ops-tab">
      <div className="template-ops-form template-ops-form--dual">
        <label className="form-label">
          Source Template
          <select
            value={sourceTemplate}
            onChange={(e) => onSourceChange(e.target.value)}
            className="form-select"
          >
            <option value="">Select source...</option>
            {templates.map((t) => (
              <option key={t.name} value={t.name}>
                {t.title || t.name}
              </option>
            ))}
          </select>
        </label>
        <label className="form-label">
          Target Template
          <select
            value={targetTemplate}
            onChange={(e) => onTargetChange(e.target.value)}
            className="form-select"
          >
            <option value="">Select target...</option>
            {templates.map((t) => (
              <option key={t.name} value={t.name}>
                {t.title || t.name}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="btn btn-primary"
          onClick={onDiff}
          disabled={!sourceTemplate || !targetTemplate || isLoading}
        >
          {isLoading ? 'Comparing...' : 'Compare Templates'}
        </button>
      </div>

      {result && (
        <div className="diff-result">
          <div className="diff-summary">
            <div className={`diff-status ${result.is_breaking ? 'breaking' : 'compatible'}`}>
              {result.is_breaking ? 'Breaking Changes' : 'Compatible'}
            </div>
            <p className="diff-summary-text">{result.summary}</p>
          </div>

          {result.elements_added.length > 0 && (
            <div className="diff-section diff-section--added">
              <h4>Added Elements ({result.elements_added.length})</h4>
              <ul className="diff-list">
                {result.elements_added.map((path) => (
                  <li key={path} className="diff-item diff-item--added">
                    + {path}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result.elements_removed.length > 0 && (
            <div className="diff-section diff-section--removed">
              <h4>Removed Elements ({result.elements_removed.length})</h4>
              <ul className="diff-list">
                {result.elements_removed.map((path) => (
                  <li key={path} className="diff-item diff-item--removed">
                    - {path}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result.cardinality_changes.length > 0 && (
            <div className="diff-section diff-section--modified">
              <h4>Cardinality Changes ({result.cardinality_changes.length})</h4>
              <ul className="diff-list">
                {result.cardinality_changes.map((change) => (
                  <li
                    key={change.path}
                    className={`diff-item ${change.breaking ? 'diff-item--breaking' : ''}`}
                  >
                    {change.path}: {change.old_cardinality} &rarr; {change.new_cardinality}
                    {change.breaking && <span className="badge badge--danger">Breaking</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Migrate Tab
interface MigrateTabProps {
  templates: TemplateInfo[];
  sourceTemplate: string;
  targetTemplate: string;
  onSourceChange: (name: string) => void;
  onTargetChange: (name: string) => void;
  plan: MigrationPlan | null;
  isLoading: boolean;
  onMigrate: () => void;
}

function MigrateTab({
  templates,
  sourceTemplate,
  targetTemplate,
  onSourceChange,
  onTargetChange,
  plan,
  isLoading,
  onMigrate,
}: MigrateTabProps) {
  return (
    <div className="template-ops-tab">
      <div className="template-ops-form template-ops-form--dual">
        <label className="form-label">
          Source Template
          <select
            value={sourceTemplate}
            onChange={(e) => onSourceChange(e.target.value)}
            className="form-select"
          >
            <option value="">Select source...</option>
            {templates.map((t) => (
              <option key={t.name} value={t.name}>
                {t.title || t.name}
              </option>
            ))}
          </select>
        </label>
        <label className="form-label">
          Target Template
          <select
            value={targetTemplate}
            onChange={(e) => onTargetChange(e.target.value)}
            className="form-select"
          >
            <option value="">Select target...</option>
            {templates.map((t) => (
              <option key={t.name} value={t.name}>
                {t.title || t.name}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="btn btn-primary"
          onClick={onMigrate}
          disabled={!sourceTemplate || !targetTemplate || isLoading}
        >
          {isLoading ? 'Planning...' : 'Generate Migration Plan'}
        </button>
      </div>

      {plan && (
        <div className="migration-result">
          <div className="migration-summary">
            <div className="migration-coverage">
              <span className="coverage-value">
                {Math.round(plan.mapping_coverage * 100)}%
              </span>
              <span className="coverage-label">Mapping Coverage</span>
            </div>
            <div className="migration-stats">
              <span>{plan.auto_mappings.length} auto-mappings</span>
              <span>{plan.unmapped_source.length} unmapped source</span>
              <span>{plan.unmapped_target.length} unmapped target</span>
            </div>
          </div>

          {plan.warnings.length > 0 && (
            <div className="migration-warnings">
              {plan.warnings.map((warning, idx) => (
                <div key={idx} className="warning-item">
                  {warning}
                </div>
              ))}
            </div>
          )}

          {plan.auto_mappings.length > 0 && (
            <div className="mappings-table-wrapper">
              <h4>Auto-Mappings</h4>
              <table className="mappings-table">
                <thead>
                  <tr>
                    <th>Source Path</th>
                    <th>Target Path</th>
                    <th>Confidence</th>
                    <th>Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {plan.auto_mappings.map((mapping, idx) => (
                    <tr key={idx}>
                      <td className="path-cell">{mapping.source_path}</td>
                      <td className="path-cell">{mapping.target_path}</td>
                      <td>
                        <span
                          className={`confidence-badge confidence-badge--${getConfidenceLevel(mapping.confidence)}`}
                        >
                          {Math.round(mapping.confidence * 100)}%
                        </span>
                      </td>
                      <td>
                        <span className={`reason-badge reason-badge--${mapping.match_reason}`}>
                          {mapping.match_reason}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Diagnostic List Component
interface DiagnosticListProps {
  title: string;
  items: { path: string; code: string; message: string; suggestion: string | null }[];
  severity: 'error' | 'warning' | 'info';
}

function DiagnosticList({ title, items, severity }: DiagnosticListProps) {
  return (
    <div className={`diagnostic-section diagnostic-section--${severity}`}>
      <h4>
        {title} ({items.length})
      </h4>
      <ul className="diagnostic-list">
        {items.map((item, idx) => (
          <li key={idx} className="diagnostic-item">
            <span className="diagnostic-path">{item.path}</span>
            <span className="diagnostic-code">[{item.code}]</span>
            <span className="diagnostic-message">{item.message}</span>
            {item.suggestion && (
              <span className="diagnostic-suggestion">{item.suggestion}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function getConfidenceLevel(confidence: number): 'high' | 'medium' | 'low' {
  if (confidence >= 0.9) return 'high';
  if (confidence >= 0.7) return 'medium';
  return 'low';
}
