/**
 * MagicImportPanel - Main wizard UI for Magic Import.
 *
 * Provides:
 * - PDF upload
 * - Processing progress
 * - Extraction review with PDF viewer
 * - Apply to form
 */

import { useCallback, useMemo, useRef, useId, useState } from 'react';
import type { UseFormReturn } from 'react-hook-form';
import type { SubmodelFormData } from '../../types/aas-elements';
import type { SubmodelUISchema } from '../../types/ui-schema';
import { useMagicImport } from './useMagicImport';
import PdfViewer from './PdfViewer';
import ExtractionReviewTable from './ExtractionReviewTable';
import ProvenancePanel from './ProvenancePanel';
import ProviderQuickStatus from './ProviderQuickStatus';
import { LLMSettingsPanel } from '../LLMSettings';
import './MagicImport.css';

interface MagicImportPanelProps {
  templateName: string;
  templateStatus: 'published' | 'deprecated';
  templateVersion?: string | null;
  form: UseFormReturn<SubmodelFormData>;
  schema?: SubmodelUISchema | null;
  onClose?: () => void;
}

export default function MagicImportPanel({
  templateName,
  templateStatus,
  templateVersion,
  form,
  schema,
  onClose,
}: MagicImportPanelProps) {
  const {
    job,
    result,
    extractions,
    unmappedFindings,
    selectedExtractionPath,
    isUploading,
    isProcessing,
    isReextracting,
    error,
    uploadPdf,
    cancelJob,
    selectExtraction,
    updateExtraction,
    approveExtraction,
    approveAll,
    reextractPaths,
    applyToForm,
    reset,
    pdfUrl,
  } = useMagicImport({
    templateName,
    templateStatus,
    templateVersion,
    form,
    schema,
  });

  const fileInputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();
  const [focusToken, setFocusToken] = useState(0);
  const [showSettings, setShowSettings] = useState(false);

  // Handle file selection
  const handleFileSelect = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        await uploadPdf(file);
      }
      // Reset input so same file can be selected again
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    },
    [uploadPdf]
  );

  // Handle drag and drop
  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file && file.type === 'application/pdf') {
        await uploadPdf(file);
      }
    },
    [uploadPdf]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
  }, []);

  const handleDropzoneKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLLabelElement>) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        fileInputRef.current?.click();
      }
    },
    []
  );

  // Get selected extraction for highlighting
  const selectedExtraction = useMemo(
    () => extractions.find((e) => e.path === selectedExtractionPath),
    [extractions, selectedExtractionPath]
  );

  // Count ready extractions
  const readyCount = extractions.filter((e) => e.user_approved || e.status === 'filled').length;
  const fieldsExtracted = extractions.length;
  const fieldsNeedingReview = extractions.filter(
    (e) => e.status === 'needs_review' || e.status === 'conflict'
  ).length;
  const avgConfidence =
    extractions.length > 0
      ? Math.round(
          (extractions.reduce((sum, e) => sum + e.confidence, 0) / extractions.length) *
            100
        )
      : 0;
  const validationErrors = result?.validation_result?.errors ?? [];
  const validationWarnings = result?.validation_result?.warnings ?? [];
  const hasValidationErrors = validationErrors.length > 0;
  const canApply = readyCount > 0 && !hasValidationErrors;

  const handleFocusEvidence = useCallback(() => {
    setFocusToken((token) => token + 1);
  }, []);

  // Render upload state
  if (!job) {
    return (
      <div className="magic-import-panel">
        <div className="magic-import-panel__header">
          <h3>Magic Import</h3>
          <p className="magic-import-panel__subtitle">
            Extract data from PDF datasheets using AI
          </p>
          {onClose && (
            <button
              type="button"
              className="magic-import-panel__close"
              onClick={onClose}
            >
              &times;
            </button>
          )}
        </div>

        {/* Provider Status */}
        <ProviderQuickStatus onConfigureClick={() => setShowSettings(true)} />

        <label
          htmlFor={inputId}
          className="magic-import-panel__dropzone"
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onKeyDown={handleDropzoneKeyDown}
          tabIndex={0}
          aria-label="Upload PDF"
        >
          <input
            id={inputId}
            ref={fileInputRef}
            type="file"
            accept=".pdf"
            onChange={handleFileSelect}
            className="magic-import-panel__input"
          />
          <div className="magic-import-panel__dropzone-content">
            <span className="magic-import-panel__icon">📄</span>
            <p>Drop a PDF here or click to upload</p>
            <p className="magic-import-panel__hint">
              Supports datasheets, nameplates, and technical documents
            </p>
          </div>
        </label>

        {error && <div className="magic-import-panel__error">{error}</div>}

        {/* Settings Modal */}
        {showSettings && (
          <div
            className="magic-import-panel__settings-overlay"
            onClick={(e) => {
              if (e.target === e.currentTarget) {
                setShowSettings(false);
              }
            }}
          >
            <div className="magic-import-panel__settings-modal">
              <LLMSettingsPanel onClose={() => setShowSettings(false)} />
            </div>
          </div>
        )}
      </div>
    );
  }

  // Render processing state
  if (isProcessing || isUploading) {
    return (
      <div className="magic-import-panel">
        <div className="magic-import-panel__header">
          <h3>Magic Import</h3>
          {onClose && (
            <button
              type="button"
              className="magic-import-panel__close"
              onClick={onClose}
            >
              &times;
            </button>
          )}
        </div>

        <div className="magic-import-panel__processing">
          <div className="magic-import-panel__spinner" />
          <p className="magic-import-panel__status">
            {job.progress_message || 'Processing...'}
          </p>
          <div className="magic-import-panel__progress">
            <div
              className="magic-import-panel__progress-bar"
              style={{ width: `${job.progress * 100}%` }}
            />
          </div>
          <p className="magic-import-panel__progress-text">
            {Math.round(job.progress * 100)}%
          </p>

          {job.pdf_info && (
            <div className="magic-import-panel__info">
              <span>
                {job.pdf_info.total_pages} pages, {job.pdf_info.total_words} words
              </span>
              {job.pdf_info.pages_needing_ocr > 0 && (
                <span> ({job.pdf_info.pages_needing_ocr} pages needed OCR)</span>
              )}
            </div>
          )}

          <button
            type="button"
            className="magic-import-panel__cancel"
            onClick={cancelJob}
          >
            Cancel
          </button>
        </div>

        {error && <div className="magic-import-panel__error">{error}</div>}
      </div>
    );
  }

  // Render failed state
  if (job.status === 'failed') {
    return (
      <div className="magic-import-panel">
        <div className="magic-import-panel__header">
          <h3>Magic Import</h3>
          {onClose && (
            <button
              type="button"
              className="magic-import-panel__close"
              onClick={onClose}
            >
              &times;
            </button>
          )}
        </div>

        <div className="magic-import-panel__failed">
          <span className="magic-import-panel__icon">❌</span>
          <p>Processing failed</p>
          <p className="magic-import-panel__error-detail">
            {job.error_message || 'Unknown error'}
          </p>
          <button type="button" className="magic-import-panel__retry" onClick={reset}>
            Try Again
          </button>
        </div>
      </div>
    );
  }

  // Render review state
  return (
    <div className="magic-import-panel magic-import-panel--review">
      <div className="magic-import-panel__header">
        <h3>Magic Import - Review Extractions</h3>
        {result && (
          <div className="magic-import-panel__summary">
            <span>{fieldsExtracted} fields extracted</span>
            <span className="magic-import-panel__separator">|</span>
            <span>
              {fieldsNeedingReview > 0
                ? `${fieldsNeedingReview} need review`
                : 'All ready'}
            </span>
            <span className="magic-import-panel__separator">|</span>
            <span>Avg confidence: {avgConfidence}%</span>
            {result.llm_provider && (
              <>
                <span className="magic-import-panel__separator">|</span>
                <span className="magic-import-panel__llm-info">
                  {result.llm_provider}/{result.llm_model}
                </span>
                <span className="magic-import-panel__separator">|</span>
                <span>{result.processing_time_seconds.toFixed(1)}s</span>
              </>
            )}
          </div>
        )}
        {onClose && (
          <button
            type="button"
            className="magic-import-panel__close"
            onClick={onClose}
          >
            &times;
          </button>
        )}
      </div>
      {error && <div className="magic-import-panel__error">{error}</div>}

      {/* Warning if all fields empty */}
      {extractions.length > 0 && extractions.every(e => e.status === 'empty') && (
        <div className="magic-import-panel__warning">
          ⚠️ All fields returned empty. The selected template may not match this document.
          Consider using a different template that matches your document content.
        </div>
      )}

      <div className="magic-import-panel__content">
        {/* PDF Viewer (left side) */}
        <div className="magic-import-panel__viewer">
          <PdfViewer
            url={pdfUrl}
            evidence={selectedExtraction?.evidence ?? null}
            confidence={selectedExtraction?.confidence}
            focusToken={focusToken}
          />
        </div>

        {/* Review Table (right side) */}
        <div className="magic-import-panel__review">
          <div className="magic-import-panel__review-content">
            <ExtractionReviewTable
              extractions={extractions}
              unmappedFindings={unmappedFindings}
              selectedPath={selectedExtractionPath}
              onSelect={selectExtraction}
              onUpdate={updateExtraction}
              onApprove={approveExtraction}
              onApproveAll={approveAll}
            />
            <ProvenancePanel
              extraction={selectedExtraction ?? null}
              onGoToPdf={selectedExtraction?.evidence ? handleFocusEvidence : undefined}
              onApprove={
                selectedExtraction?.path ? () => approveExtraction(selectedExtraction.path) : undefined
              }
              onReExtract={
                selectedExtraction?.path
                  ? () => reextractPaths([selectedExtraction.path])
                  : undefined
              }
              onClose={() => selectExtraction(null)}
              isReExtracting={isReextracting}
            />
          </div>
        </div>
      </div>

      <div className="magic-import-panel__footer">
        <div className="magic-import-panel__validation">
          {result?.validation_result ? (
            <>
              <div
                className={`magic-import-panel__validation-status ${
                  hasValidationErrors ? 'error' : validationWarnings.length > 0 ? 'warning' : 'ok'
                }`}
              >
                {hasValidationErrors
                  ? `Validation failed (${validationErrors.length} errors)`
                  : validationWarnings.length > 0
                  ? `Validation warnings (${validationWarnings.length})`
                  : 'Validation passed'}
              </div>
              {(validationErrors.length > 0 || validationWarnings.length > 0) && (
                <div className="magic-import-panel__validation-details">
                  {validationErrors.slice(0, 3).map((err) => (
                    <div key={`err-${err.path}-${err.code}`} className="magic-import-panel__validation-item">
                      <strong>{err.path || 'General'}:</strong> {err.message}
                    </div>
                  ))}
                  {validationWarnings.slice(0, 2).map((warn) => (
                    <div key={`warn-${warn.path}-${warn.code}`} className="magic-import-panel__validation-item">
                      <strong>{warn.path || 'General'}:</strong> {warn.message}
                    </div>
                  ))}
                  {(validationErrors.length > 3 || validationWarnings.length > 2) && (
                    <div className="magic-import-panel__validation-more">
                      See validation report for full details
                    </div>
                  )}
                </div>
              )}
            </>
          ) : (
            <div className="magic-import-panel__validation-status info">
              Validation not available
            </div>
          )}
        </div>
        <button
          type="button"
          className="magic-import-panel__btn--secondary"
          onClick={reset}
        >
          Start Over
        </button>
        <button
          type="button"
          className="magic-import-panel__btn--primary"
          onClick={applyToForm}
          disabled={!canApply}
        >
          Apply {readyCount} Fields to Form
        </button>
      </div>
    </div>
  );
}
