import React from 'react';
import './PCFPanel.css';

interface PCFDeclarationProps {
  instanceKind: 'list' | 'collection' | null;
  instanceCount: number;
  activeInstanceIndex: number;
  onInstanceChange: (index: number) => void;
  referenceUnit: string;
  onReferenceUnitChange: (value: string) => void;
  referenceQuantity: string;
  onReferenceQuantityChange: (value: string) => void;
  publicationDate: string;
  onPublicationDateChange: (value: string) => void;
  lifeCyclePhaseCount: number;
}

const formatInstanceLabel = (index: number): string =>
  `Instance ${index + 1}`;

const PCFDeclaration: React.FC<PCFDeclarationProps> = ({
  instanceKind,
  instanceCount,
  activeInstanceIndex,
  onInstanceChange,
  referenceUnit,
  onReferenceUnitChange,
  referenceQuantity,
  onReferenceQuantityChange,
  publicationDate,
  onPublicationDateChange,
  lifeCyclePhaseCount,
}) => {
  const isInstanceMissing = instanceKind === 'list' && instanceCount === 0;

  return (
    <div className="pcf-declaration">
      <div className="pcf-declaration__header">
        <h3>PCF Declaration</h3>
        <p>
          Set required calculation metadata for the active ProductCarbonFootprint
          instance.
        </p>
      </div>

      {instanceKind === 'list' && (
        <div className="pcf-declaration__row">
          <label htmlFor="pcf-instance">ProductCarbonFootprint instance</label>
          {instanceCount > 0 ? (
            <select
              id="pcf-instance"
              value={activeInstanceIndex}
              onChange={(event) =>
                onInstanceChange(Number(event.target.value))
              }
            >
              {Array.from({ length: instanceCount }).map((_, index) => (
                <option key={index} value={index}>
                  {formatInstanceLabel(index)}
                </option>
              ))}
            </select>
          ) : (
            <p className="pcf-declaration__note">
              No ProductCarbonFootprint instances found. Add one in the form.
            </p>
          )}
        </div>
      )}

      <div className="pcf-declaration__grid">
        <div className="pcf-declaration__field">
          <label htmlFor="pcf-reference-unit">
            Reference impact unit for calculation
          </label>
          <input
            id="pcf-reference-unit"
            type="text"
            value={referenceUnit}
            onChange={(event) => onReferenceUnitChange(event.target.value)}
            placeholder="e.g., piece"
            disabled={isInstanceMissing}
          />
        </div>

        <div className="pcf-declaration__field">
          <label htmlFor="pcf-reference-quantity">
            Quantity of measure for calculation
          </label>
          <input
            id="pcf-reference-quantity"
            type="number"
            inputMode="decimal"
            value={referenceQuantity}
            onChange={(event) => onReferenceQuantityChange(event.target.value)}
            placeholder="e.g., 1"
            disabled={isInstanceMissing}
          />
        </div>

        <div className="pcf-declaration__field">
          <label htmlFor="pcf-publication-date">Publication date</label>
          <input
            id="pcf-publication-date"
            type="date"
            value={publicationDate}
            onChange={(event) => onPublicationDateChange(event.target.value)}
            disabled={isInstanceMissing}
          />
        </div>
      </div>

      <div
        className={
          lifeCyclePhaseCount === 0
            ? 'pcf-declaration__status pcf-declaration__status--warning'
            : 'pcf-declaration__status'
        }
      >
        LifeCyclePhases selected: {lifeCyclePhaseCount}
      </div>
    </div>
  );
};

export default PCFDeclaration;
