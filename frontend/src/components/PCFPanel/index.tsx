/**
 * PCFPanel - Main component for PCF Calculator & Validator.
 *
 * This panel is conditionally rendered when the template is a Carbon Footprint template.
 * It provides:
 * - CO2e calculator for emission activities
 * - PCF validation against IDTA 02023 rules
 */

import type { UseFormReturn } from 'react-hook-form';
import type { SubmodelUISchema } from '../../types/ui-schema';
import type { SubmodelFormData } from '../../types/aas-elements';
import { usePCFPanel } from './usePCFPanel';
import PCFDeclaration from './PCFDeclaration';
import PCFCalculator from './PCFCalculator';
import PCFValidator from './PCFValidator';
import './PCFPanel.css';

interface PCFPanelProps {
  schema: SubmodelUISchema | null;
  form: UseFormReturn<SubmodelFormData>;
}

export default function PCFPanel({ schema, form }: PCFPanelProps) {
  const {
    workspace,
    validationResult,
    error,
    calculating,
    validating,
    searchingFactors,
    factorResults,
    factorsMeta,
    activeInstanceIndex,
    instanceCount,
    instanceKind,
    setActiveInstanceIndex,
    referenceUnit,
    setReferenceUnit,
    referenceQuantity,
    setReferenceQuantity,
    publicationDate,
    setPublicationDate,
    lifeCyclePhaseCount,
    addActivity,
    updateActivity,
    removeActivity,
    calculate,
    validate,
    applyToForm,
    searchFactors,
    clearFactorResults,
    applyFactorToActivity,
  } = usePCFPanel({ schema, form });

  return (
    <div className="pcf-panel">
      {schema?.pcfActivityListInjected && (
        <div className="pcf-panel__banner">
          <p>
            Activity list injected for export. Update the template to persist
            PCF activities.
          </p>
        </div>
      )}
      <div className="pcf-panel__section">
        <PCFDeclaration
          instanceKind={instanceKind}
          instanceCount={instanceCount}
          activeInstanceIndex={activeInstanceIndex}
          onInstanceChange={setActiveInstanceIndex}
          referenceUnit={referenceUnit}
          onReferenceUnitChange={setReferenceUnit}
          referenceQuantity={referenceQuantity}
          onReferenceQuantityChange={setReferenceQuantity}
          publicationDate={publicationDate}
          onPublicationDateChange={setPublicationDate}
          lifeCyclePhaseCount={lifeCyclePhaseCount}
        />
      </div>

      <div className="pcf-panel__section">
        <PCFCalculator
          activities={workspace.activities}
          totalCo2eKg={workspace.totalCo2eKg}
          warnings={workspace.warnings}
          calculating={calculating}
          searchingFactors={searchingFactors}
          factorResults={factorResults}
          factorsMeta={factorsMeta ?? null}
          onAddActivity={addActivity}
          onUpdateActivity={updateActivity}
          onRemoveActivity={removeActivity}
          onCalculate={calculate}
          onApplyToForm={applyToForm}
          onSearchFactors={searchFactors}
          onClearFactorResults={clearFactorResults}
          onApplyFactor={applyFactorToActivity}
        />
      </div>

      <div className="pcf-panel__section">
        <PCFValidator
          validationResult={validationResult}
          validating={validating}
          onValidate={validate}
        />
      </div>

      {error && (
        <div className="pcf-panel__error">
          <p>{error}</p>
        </div>
      )}
    </div>
  );
}
