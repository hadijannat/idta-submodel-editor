/**
 * ExportPanel component for exporting filled submodels.
 */

import React, { useState } from 'react';
import { ApiError } from '../../services/api';
import type { ConformanceCheckResult } from '../../services/api';

interface ExportPanelProps {
  /** Template name */
  templateName: string;
  /** Export as AASX */
  onExportAasx: (filename?: string) => Promise<void>;
  /** Export as JSON */
  onExportJson: (filename?: string) => Promise<void>;
  /** Export as PDF */
  onExportPdf: (filename?: string) => Promise<void>;
  /** Verify export without downloading */
  onVerify: () => Promise<void>;
  /** Whether conformance verification is running */
  conformanceChecking?: boolean;
  /** Last conformance result */
  conformanceResult?: ConformanceCheckResult | null;
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
  onVerify,
  conformanceChecking = false,
  conformanceResult = null,
  onValidate,
  onReset,
  validating = false,
  validationResult,
}) => {
  const [exporting, setExporting] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [customFilename, setCustomFilename] = useState('');
  const [serverErrors, setServerErrors] = useState<string[]>([]);
  const [serverWarnings, setServerWarnings] = useState<string[]>([]);

  const clearServerIssues = () => {
    setServerErrors([]);
    setServerWarnings([]);
  };

  const captureServerIssues = (err: unknown): boolean => {
    if (!(err instanceof ApiError) || !err.details) {
      return false;
    }

    const rawDetails =
      typeof err.details === 'object' && err.details !== null ? err.details : undefined;
    const details =
      rawDetails &&
      'detail' in rawDetails &&
      typeof (rawDetails as Record<string, unknown>).detail !== 'undefined'
        ? (rawDetails as Record<string, unknown>).detail
        : rawDetails;

    if (typeof details !== 'object' || details === null) {
      return false;
    }

    const record = details as Record<string, unknown>;
    const errors = Array.isArray(record.errors) ? record.errors : [];
    const warnings = Array.isArray(record.warnings) ? record.warnings : [];

    if (errors.length === 0 && warnings.length === 0) {
      return false;
    }

    const formatIssue = (issue: unknown) => {
      if (typeof issue === 'object' && issue !== null) {
        const issueRecord = issue as Record<string, unknown>;
        const field = typeof issueRecord.field === 'string' ? issueRecord.field : '';
        const message = typeof issueRecord.message === 'string' ? issueRecord.message : '';
        if (field && message) {
          return `${field}: ${message}`;
        }
        if (message) {
          return message;
        }
      }
      return String(issue);
    };

    setServerErrors(errors.map(formatIssue));
    setServerWarnings(warnings.map(formatIssue));
    return true;
  };

  const handleExport = async (
    format: 'aasx' | 'json' | 'pdf',
    exportFn: (filename?: string) => Promise<void>
  ) => {
    setExporting(format);
    setError(null);
    clearServerIssues();

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
      if (captureServerIssues(err)) {
        setError('Server-side validation failed. Please review the errors below.');
      } else {
        const message = err instanceof Error ? err.message : 'Export failed';
        setError(message);
      }
    } finally {
      setExporting(null);
    }
  };

  const handleVerify = async () => {
    setVerifying(true);
    setError(null);
    clearServerIssues();

    try {
      const isValid = await onValidate();
      if (!isValid) {
        setError('Please fix validation errors before verifying');
        return;
      }

      await onVerify();
    } catch (err) {
      if (captureServerIssues(err)) {
        setError('Server-side validation failed. Please review the errors below.');
      } else {
        const message = err instanceof Error ? err.message : 'Verify failed';
        setError(message);
      }
    } finally {
      setVerifying(false);
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
          disabled={!!exporting || verifying}
        >
          {exporting === 'aasx' ? 'Exporting...' : 'Export AASX'}
        </button>

        <button
          type="button"
          className="btn btn-secondary btn-export"
          onClick={() => handleExport('json', onExportJson)}
          disabled={!!exporting || verifying}
        >
          {exporting === 'json' ? 'Exporting...' : 'Export JSON'}
        </button>

        <button
          type="button"
          className="btn btn-secondary btn-export"
          onClick={() => handleExport('pdf', onExportPdf)}
          disabled={!!exporting || verifying}
        >
          {exporting === 'pdf' ? 'Exporting...' : 'Export PDF'}
        </button>
      </div>

      <div className="export-utilities">
        <button
          type="button"
          className="btn btn-validate"
          onClick={onValidate}
          disabled={validating || verifying || !!exporting}
        >
          {validating ? 'Validating...' : 'Validate'}
        </button>

        <button
          type="button"
          className="btn btn-verify"
          onClick={handleVerify}
          disabled={validating || verifying || !!exporting || conformanceChecking}
        >
          {verifying || conformanceChecking ? 'Verifying...' : 'Verify'}
        </button>

        <button
          type="button"
          className="btn btn-reset"
          onClick={() => {
            if (window.confirm('Are you sure you want to reset all fields?')) {
              onReset();
            }
          }}
          disabled={!!exporting || verifying}
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

      {(serverErrors.length > 0 || serverWarnings.length > 0) && (
        <div className="validation-result invalid">
          <p className="validation-failure">✗ Server-side validation failed</p>
          {serverErrors.length > 0 && (
            <ul className="validation-errors">
              {serverErrors.map((err, idx) => (
                <li key={idx} className="validation-error">
                  {err}
                </li>
              ))}
            </ul>
          )}
          {serverWarnings.length > 0 && (
            <ul className="validation-warnings">
              {serverWarnings.map((warn, idx) => (
                <li key={idx} className="validation-warning">
                  ⚠ {warn}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {conformanceResult && (
        <div
          className={`validation-result ${
            conformanceResult.passed ? 'valid' : 'invalid'
          }`}
        >
          <p
            className={
              conformanceResult.passed ? 'validation-success' : 'validation-failure'
            }
          >
            {conformanceResult.passed
              ? '✓ AAS conformance check passed'
              : '✗ AAS conformance check failed'}
          </p>
          <p className="validation-info">
            Engine: {conformanceResult.engine_version || 'unknown'} | Duration:{' '}
            {conformanceResult.duration_ms}ms
          </p>
          {conformanceResult.errors.length > 0 && (
            <ul className="validation-errors">
              {conformanceResult.errors.map((issue, idx) => (
                <li key={`conformance-error-${idx}`} className="validation-error">
                  {issue.message}
                </li>
              ))}
            </ul>
          )}
          {conformanceResult.warnings.length > 0 && (
            <ul className="validation-warnings">
              {conformanceResult.warnings.map((issue, idx) => (
                <li key={`conformance-warning-${idx}`} className="validation-warning">
                  ⚠ {issue.message}
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
