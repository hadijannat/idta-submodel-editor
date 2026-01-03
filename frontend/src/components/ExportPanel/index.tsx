/**
 * ExportPanel component for exporting filled submodels.
 */

import React, { useState } from 'react';

interface ExportPanelProps {
  /** Template name */
  templateName: string;
  /** Export as AASX */
  onExportAasx: (filename?: string) => Promise<void>;
  /** Export as JSON */
  onExportJson: (filename?: string) => Promise<void>;
  /** Export as PDF */
  onExportPdf: (filename?: string) => Promise<void>;
  /** Validate the form */
  onValidate: () => Promise<boolean>;
  /** Reset the form */
  onReset: () => void;
  /** Whether validation is in progress */
  validating?: boolean;
  /** Validation result */
  validationResult?: {
    valid: boolean;
    errors: string[];
    warnings: string[];
  } | null;
}

/**
 * Panel with export options and validation.
 */
export const ExportPanel: React.FC<ExportPanelProps> = ({
  templateName,
  onExportAasx,
  onExportJson,
  onExportPdf,
  onValidate,
  onReset,
  validating = false,
  validationResult,
}) => {
  const [exporting, setExporting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [customFilename, setCustomFilename] = useState('');

  const handleExport = async (
    format: 'aasx' | 'json' | 'pdf',
    exportFn: (filename?: string) => Promise<void>
  ) => {
    setExporting(format);
    setError(null);

    try {
      // Validate first
      const isValid = await onValidate();
      if (!isValid) {
        setError('Please fix validation errors before exporting');
        setExporting(null);
        return;
      }

      const filename = customFilename || undefined;
      await exportFn(filename);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Export failed';
      setError(message);
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="export-panel">
      <h3>Export Options</h3>

      <div className="export-filename">
        <label htmlFor="export-filename">Custom filename (optional)</label>
        <input
          id="export-filename"
          type="text"
          value={customFilename}
          onChange={(e) => setCustomFilename(e.target.value)}
          placeholder={templateName}
          className="export-filename-input"
        />
      </div>

      <div className="export-actions">
        <button
          type="button"
          className="btn btn-primary btn-export"
          onClick={() => handleExport('aasx', onExportAasx)}
          disabled={!!exporting}
        >
          {exporting === 'aasx' ? 'Exporting...' : 'Export AASX'}
        </button>

        <button
          type="button"
          className="btn btn-secondary btn-export"
          onClick={() => handleExport('json', onExportJson)}
          disabled={!!exporting}
        >
          {exporting === 'json' ? 'Exporting...' : 'Export JSON'}
        </button>

        <button
          type="button"
          className="btn btn-secondary btn-export"
          onClick={() => handleExport('pdf', onExportPdf)}
          disabled={!!exporting}
        >
          {exporting === 'pdf' ? 'Exporting...' : 'Export PDF'}
        </button>
      </div>

      <div className="export-utilities">
        <button
          type="button"
          className="btn btn-validate"
          onClick={onValidate}
          disabled={validating}
        >
          {validating ? 'Validating...' : 'Validate'}
        </button>

        <button
          type="button"
          className="btn btn-reset"
          onClick={() => {
            if (window.confirm('Are you sure you want to reset all fields?')) {
              onReset();
            }
          }}
        >
          Reset Form
        </button>
      </div>

      {error && (
        <div className="export-error" role="alert">
          {error}
        </div>
      )}

      {validationResult && (
        <div
          className={`validation-result ${validationResult.valid ? 'valid' : 'invalid'}`}
        >
          {validationResult.valid ? (
            <p className="validation-success">✓ Form is valid</p>
          ) : (
            <>
              <p className="validation-failure">✗ Validation failed</p>
              {validationResult.errors.length > 0 && (
                <ul className="validation-errors">
                  {validationResult.errors.map((err, idx) => (
                    <li key={idx} className="validation-error">
                      {err}
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}

          {validationResult.warnings.length > 0 && (
            <ul className="validation-warnings">
              {validationResult.warnings.map((warn, idx) => (
                <li key={idx} className="validation-warning">
                  ⚠ {warn}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
};

export default ExportPanel;
