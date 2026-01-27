/**
 * MigrationWizard - Step-by-step flow for migrating recipes or form data.
 *
 * Steps:
 * 1. Select artifact (recipe from list or current form data)
 * 2. Select target version
 * 3. Preview migration mappings with confidence scores
 * 4. Review/override low-confidence mappings
 * 5. Apply migration
 */

import { useState, useCallback, useMemo } from 'react';
import type {
  RecipeMigrationRequest,
  RecipeMigrationResult,
  FormDataMigrationRequest,
  FormDataMigrationResult,
  MappingMigrationItem,
} from '../../services/templateOpsApi';
import { migrateRecipe, migrateFormData } from '../../services/templateOpsApi';
import MappingTable from './MappingTable';
import './TemplateOps.css';

type WizardStep = 'select-artifact' | 'select-target' | 'preview' | 'review' | 'complete';

interface MigrationWizardProps {
  templateName: string;
  templateVersion?: string | null;
  templateStatus?: 'published' | 'deprecated' | 'local';
  availableVersions?: Array<{ version: string; status: string }>;
  recipes?: Array<{ name: string; template: { name: string; version?: string | null } }>;
  currentFormData?: Record<string, unknown>;
  onMigrationComplete?: (result: RecipeMigrationResult | FormDataMigrationResult) => void;
  onClose?: () => void;
}

export default function MigrationWizard({
  templateName,
  templateVersion,
  templateStatus = 'published',
  availableVersions = [],
  recipes = [],
  currentFormData,
  onMigrationComplete,
  onClose,
}: MigrationWizardProps) {
  const [step, setStep] = useState<WizardStep>('select-artifact');
  const [artifactType, setArtifactType] = useState<'recipe' | 'form_data' | null>(null);
  const [selectedRecipe, setSelectedRecipe] = useState<Record<string, unknown> | null>(null);
  const [targetVersion, setTargetVersion] = useState<string | null>(null);
  const [targetStatus, setTargetStatus] = useState<'published' | 'deprecated' | 'local'>(
    'published'
  );
  const [migrationResult, setMigrationResult] = useState<
    RecipeMigrationResult | FormDataMigrationResult | null
  >(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filter recipes for current template
  const compatibleRecipes = useMemo(
    () => recipes.filter((r) => r.template.name === templateName),
    [recipes, templateName]
  );

  const handleSelectArtifact = useCallback(
    (type: 'recipe' | 'form_data', recipe?: Record<string, unknown>) => {
      setArtifactType(type);
      if (type === 'recipe' && recipe) {
        setSelectedRecipe(recipe);
      }
      setStep('select-target');
    },
    []
  );

  const handleSelectTarget = useCallback((version: string, status: string) => {
    setTargetVersion(version);
    setTargetStatus(status as 'published' | 'deprecated' | 'local');
    setStep('preview');
  }, []);

  const handleRunMigration = useCallback(async () => {
    if (!targetVersion) return;

    setLoading(true);
    setError(null);

    try {
      let result: RecipeMigrationResult | FormDataMigrationResult;

      if (artifactType === 'recipe' && selectedRecipe) {
        const request: RecipeMigrationRequest = {
          recipe: selectedRecipe,
          target_template: templateName,
          target_version: targetVersion,
          target_status: targetStatus,
          min_confidence: 0.5,
          preserve_transforms: true,
        };
        result = await migrateRecipe(request);
      } else if (artifactType === 'form_data' && currentFormData) {
        const request: FormDataMigrationRequest = {
          form_data: currentFormData,
          source_template: templateName,
          source_version: templateVersion,
          source_status: templateStatus,
          target_template: templateName,
          target_version: targetVersion,
          target_status: targetStatus,
          min_confidence: 0.5,
        };
        result = await migrateFormData(request);
      } else {
        throw new Error('No artifact selected');
      }

      setMigrationResult(result);
      setStep('review');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Migration failed');
    } finally {
      setLoading(false);
    }
  }, [
    artifactType,
    selectedRecipe,
    currentFormData,
    templateName,
    templateVersion,
    templateStatus,
    targetVersion,
    targetStatus,
  ]);

  const handleApplyMigration = useCallback(() => {
    if (migrationResult) {
      onMigrationComplete?.(migrationResult);
      setStep('complete');
    }
  }, [migrationResult, onMigrationComplete]);

  const handleBack = useCallback(() => {
    switch (step) {
      case 'select-target':
        setStep('select-artifact');
        break;
      case 'preview':
        setStep('select-target');
        break;
      case 'review':
        setStep('preview');
        break;
      default:
        break;
    }
  }, [step]);

  const renderStepIndicator = () => {
    const steps = [
      { key: 'select-artifact', label: '1. Select' },
      { key: 'select-target', label: '2. Target' },
      { key: 'preview', label: '3. Preview' },
      { key: 'review', label: '4. Review' },
      { key: 'complete', label: '5. Done' },
    ];

    const currentIndex = steps.findIndex((s) => s.key === step);

    return (
      <div className="wizard-steps">
        {steps.map((s, index) => (
          <div
            key={s.key}
            className={`wizard-step ${
              index < currentIndex
                ? 'wizard-step--completed'
                : index === currentIndex
                  ? 'wizard-step--active'
                  : ''
            }`}
          >
            <span className="wizard-step__label">{s.label}</span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="migration-wizard">
      <div className="migration-wizard__header">
        <h3>Migration Wizard</h3>
        {onClose && (
          <button type="button" className="btn btn--icon" onClick={onClose} aria-label="Close">
            ✕
          </button>
        )}
      </div>

      {renderStepIndicator()}

      <div className="migration-wizard__content">
        {error && (
          <div className="migration-wizard__error">
            <p>{error}</p>
            <button type="button" className="btn btn--secondary" onClick={() => setError(null)}>
              Dismiss
            </button>
          </div>
        )}

        {step === 'select-artifact' && (
          <div className="wizard-step-content">
            <h4>Select what to migrate</h4>
            <div className="artifact-options">
              {currentFormData && (
                <button
                  type="button"
                  className="artifact-option"
                  onClick={() => handleSelectArtifact('form_data')}
                >
                  <span className="artifact-option__icon">📄</span>
                  <span className="artifact-option__title">Current Form Data</span>
                  <span className="artifact-option__desc">
                    Migrate the values you&apos;ve entered to the new template version
                  </span>
                </button>
              )}

              {compatibleRecipes.length > 0 && (
                <div className="artifact-option-group">
                  <h5>Saved Recipes</h5>
                  {compatibleRecipes.map((recipe) => (
                    <button
                      type="button"
                      key={recipe.name}
                      className="artifact-option artifact-option--recipe"
                      onClick={() =>
                        handleSelectArtifact('recipe', recipe as unknown as Record<string, unknown>)
                      }
                    >
                      <span className="artifact-option__icon">📋</span>
                      <span className="artifact-option__title">{recipe.name}</span>
                      <span className="artifact-option__desc">
                        Version: {recipe.template.version || 'Latest'}
                      </span>
                    </button>
                  ))}
                </div>
              )}

              {!currentFormData && compatibleRecipes.length === 0 && (
                <p className="no-artifacts">
                  No form data or recipes available for migration.
                </p>
              )}
            </div>
          </div>
        )}

        {step === 'select-target' && (
          <div className="wizard-step-content">
            <h4>Select target version</h4>
            <p className="wizard-step-content__hint">
              Current: {templateName} {templateVersion ? `v${templateVersion}` : '(latest)'}
            </p>
            <div className="version-options">
              {availableVersions.map((v) => (
                <button
                  type="button"
                  key={v.version}
                  className={`version-option ${v.version === templateVersion ? 'version-option--current' : ''}`}
                  onClick={() => handleSelectTarget(v.version, v.status)}
                  disabled={v.version === templateVersion}
                >
                  <span className="version-option__version">v{v.version}</span>
                  <span className="version-option__status">{v.status}</span>
                  {v.version === templateVersion && (
                    <span className="version-option__current-tag">Current</span>
                  )}
                </button>
              ))}
              {availableVersions.length === 0 && (
                <p className="no-versions">No other versions available for this template.</p>
              )}
            </div>
          </div>
        )}

        {step === 'preview' && (
          <div className="wizard-step-content">
            <h4>Preview Migration</h4>
            <p className="wizard-step-content__hint">
              Migrating {artifactType === 'recipe' ? 'recipe' : 'form data'} from v
              {templateVersion || 'latest'} to v{targetVersion}
            </p>
            {loading ? (
              <div className="wizard-loading">
                <div className="wizard-loading__spinner" />
                <p>Computing migration mappings...</p>
              </div>
            ) : (
              <div className="preview-actions">
                <button
                  type="button"
                  className="btn btn--primary"
                  onClick={handleRunMigration}
                  disabled={loading}
                >
                  Compute Migration
                </button>
              </div>
            )}
          </div>
        )}

        {step === 'review' && migrationResult && (
          <div className="wizard-step-content">
            <h4>Review Migration</h4>

            <div className="migration-summary">
              <div className="migration-summary__stat">
                <span className="migration-summary__label">Coverage</span>
                <span className="migration-summary__value">
                  {Math.round(migrationResult.migration_coverage * 100)}%
                </span>
              </div>
              {'breaking_changes' in migrationResult &&
                migrationResult.breaking_changes.length > 0 && (
                  <div className="migration-summary__stat migration-summary__stat--warning">
                    <span className="migration-summary__label">Breaking Changes</span>
                    <span className="migration-summary__value">
                      {migrationResult.breaking_changes.length}
                    </span>
                  </div>
                )}
            </div>

            {'mapping_migrations' in migrationResult && (
              <MappingTable
                mappings={migrationResult.mapping_migrations as MappingMigrationItem[]}
                readonly
              />
            )}

            {migrationResult.warnings.length > 0 && (
              <div className="migration-warnings">
                <h5>Warnings</h5>
                <ul>
                  {migrationResult.warnings.map((warning, i) => (
                    <li key={i}>{warning}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {step === 'complete' && (
          <div className="wizard-step-content wizard-step-content--complete">
            <div className="complete-icon">✓</div>
            <h4>Migration Complete</h4>
            <p>
              Your {artifactType === 'recipe' ? 'recipe' : 'form data'} has been migrated to v
              {targetVersion}.
            </p>
          </div>
        )}
      </div>

      <div className="migration-wizard__footer">
        {step !== 'select-artifact' && step !== 'complete' && (
          <button type="button" className="btn btn--secondary" onClick={handleBack}>
            Back
          </button>
        )}
        {step === 'review' && (
          <button type="button" className="btn btn--primary" onClick={handleApplyMigration}>
            Apply Migration
          </button>
        )}
        {step === 'complete' && onClose && (
          <button type="button" className="btn btn--primary" onClick={onClose}>
            Done
          </button>
        )}
      </div>
    </div>
  );
}
