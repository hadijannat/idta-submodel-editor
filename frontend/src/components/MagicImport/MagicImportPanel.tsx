/**
 * MagicImportPanel - Main wizard UI for Magic Import.
 *
 * Provides:
 * - PDF upload
 * - Processing progress
 * - Extraction review with PDF viewer
 * - Apply to form
 */

import { useCallback, useMemo, useRef, useId, useState, useEffect } from 'react';
import type { UseFormReturn } from 'react-hook-form';
import type { SubmodelFormData } from '../../types/aas-elements';
import type { SubmodelUISchema } from '../../types/ui-schema';
import { useMagicImport } from './useMagicImport';
import PdfViewer from './PdfViewer';
import ExtractionReviewTable from './ExtractionReviewTable';
import ProvenancePanel from './ProvenancePanel';
import ProviderQuickStatus from './ProviderQuickStatus';
import ProviderSelector from './ProviderSelector';
import { LLMSettingsPanel } from '../LLMSettings';
import { downloadAuditReport } from '../../services/magicImportApi';
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
    approveMany,
    unapproveMany,
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
  const [showProviderSelector, setShowProviderSelector] = useState(false);
  const [showAuditMenu, setShowAuditMenu] = useState(false);
  const [auditExporting, setAuditExporting] = useState<'json' | 'pdf' | null>(null);

  // Evidence highlighting state (within selected extraction)
  const [highlightedBoxIndex, setHighlightedBoxIndex] = useState<number | null>(null);
  const [highlightAllBoxes, setHighlightAllBoxes] = useState(false);

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

  // Reset evidence focus when selection changes
  useEffect(() => {
    setHighlightedBoxIndex(null);
    setHighlightAllBoxes(false);
  }, [selectedExtractionPath]);

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

  // Handle hover from PDF viewer
  const handleBoxHover = useCallback((boxIndex: number | null) => {
    setHighlightedBoxIndex(boxIndex);
  }, []);

  // Handle explicit focus from provenance carousel
  const handleBoxFocus = useCallback((boxIndex: number) => {
    setHighlightAllBoxes(false);
    setHighlightedBoxIndex(boxIndex);
  }, []);

  // Handle click from PDF box - pins highlight to that box
  const handleBoxClick = useCallback((boxIndex: number) => {
    setHighlightedBoxIndex(boxIndex);
    setHighlightAllBoxes(false);
  }, []);

  // Handle "View All" toggle from provenance panel
  const handleToggleViewAll = useCallback((active: boolean) => {
    setHighlightAllBoxes(active);
    if (active) {
      setHighlightedBoxIndex(null);
    }
  }, []);

  // Handle audit report export
  const handleAuditExport = useCallback(
    async (format: 'json' | 'pdf') => {
      if (!job?.job_id) return;
      setAuditExporting(format);
      setShowAuditMenu(false);
      try {
        await downloadAuditReport(job.job_id, format);
      } catch (err) {
        console.error('Failed to download audit report:', err);
      } finally {
        setAuditExporting(null);
      }
    },
    [job?.job_id]
  );

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
        <ProviderQuickStatus
          onChangeProviderClick={() => setShowProviderSelector(true)}
          onConfigureClick={() => setShowSettings(true)}
        />

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

        {/* Provider Selector Modal (Quick selection with privacy indicators) */}
        {showProviderSelector && (
          <div
            className="magic-import-panel__settings-overlay"
            onClick={(e) => {
              if (e.target === e.currentTarget) {
                setShowProviderSelector(false);
              }
            }}
          >
            <ProviderSelector
              onClose={() => setShowProviderSelector(false)}
              onProviderSelected={() => {
                setShowProviderSelector(false);
              }}
            />
          </div>
        )}

        {/* Full Settings Modal (for API key configuration) */}
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
        {result?.quality_metrics && (
          <div className="magic-import-panel__quality-metrics">
            <span className="magic-import-panel__metric-chip">
              Quality: {Math.round(result.quality_metrics.weighted_confidence * 100)}%
            </span>
            <span className="magic-import-panel__metric-chip">
              Evidence: {Math.round(result.quality_metrics.evidence_ratio * 100)}%
            </span>
            <span className="magic-import-panel__metric-chip">
              Required: {Math.round(result.quality_metrics.required_field_coverage * 100)}%
            </span>
            {result.quality_metrics.auto_apply_eligible_count > 0 && (
              <span className="magic-import-panel__metric-chip magic-import-panel__metric-chip--success">
                {result.quality_metrics.auto_apply_eligible_count} auto-apply eligible
              </span>
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

      {/* Warning if mismatch is suspected (legacy) */}
      {result?.mismatch_suspected && !result?.quality_metrics?.mismatch_metrics && (
        <div className="magic-import-panel__warning">
          <strong>Possible template mismatch.</strong> The selected template may not
          match this document. Consider choosing a template that fits the PDF content.
          {result.mismatch_reasons && result.mismatch_reasons.length > 0 && (
            <ul className="magic-import-panel__warning-list">
              {result.mismatch_reasons.map((reason) => (
                <li key={reason}>{formatMismatchReason(reason)}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Detailed mismatch warning from quality metrics */}
      {result?.quality_metrics?.mismatch_metrics &&
        result.quality_metrics.mismatch_metrics.mismatch_score >= 0.4 && (
          <div
            className={`magic-import-panel__warning ${
              result.quality_metrics.mismatch_metrics.recommended_action === 'abort'
                ? 'magic-import-panel__warning--severe'
                : ''
            }`}
          >
            <strong>
              {result.quality_metrics.mismatch_metrics.recommended_action === 'abort'
                ? 'Template Mismatch Detected'
                : 'Possible Template Mismatch'}
            </strong>
            <p>
              Mismatch score:{' '}
              {Math.round(result.quality_metrics.mismatch_metrics.mismatch_score * 100)}%
            </p>
            {result.quality_metrics.mismatch_metrics.mismatch_indicators.length > 0 && (
              <ul className="magic-import-panel__warning-list">
                {result.quality_metrics.mismatch_metrics.mismatch_indicators.map(
                  (indicator, i) => (
                    <li key={i}>{indicator}</li>
                  )
                )}
              </ul>
            )}
          </div>
        )}

      {/* Fallback warning if all fields empty */}
      {!result?.mismatch_suspected &&
        extractions.length > 0 &&
        extractions.every((e) => e.status === 'empty') && (
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
            highlightedBoxIndex={highlightedBoxIndex}
            highlightAllBoxes={highlightAllBoxes}
            onBoxHover={handleBoxHover}
            onBoxClick={handleBoxClick}
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
              onApproveMany={approveMany}
              onUnapproveMany={unapproveMany}
              highlightSelectedRow={highlightedBoxIndex !== null || highlightAllBoxes}
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
              onFocusBox={handleBoxFocus}
              onToggleViewAll={handleToggleViewAll}
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
        <div className="magic-import-panel__footer-actions">
          <button
            type="button"
            className="magic-import-panel__btn--secondary"
            onClick={reset}
          >
            Start Over
          </button>
          {/* Audit Report Export */}
          <div className="magic-import-panel__audit-dropdown">
            <button
              type="button"
              className="magic-import-panel__btn--secondary"
              onClick={() => setShowAuditMenu(!showAuditMenu)}
              disabled={!!auditExporting}
              title="Export extraction audit report showing AI reasoning and evidence"
            >
              {auditExporting ? `Exporting ${auditExporting.toUpperCase()}...` : 'Audit Report'}
            </button>
            {showAuditMenu && (
              <div className="magic-import-panel__audit-menu">
                <button
                  type="button"
                  className="magic-import-panel__audit-menu-item"
                  onClick={() => handleAuditExport('json')}
                >
                  Export as JSON
                </button>
                <button
                  type="button"
                  className="magic-import-panel__audit-menu-item"
                  onClick={() => handleAuditExport('pdf')}
                >
                  Export as PDF
                </button>
              </div>
            )}
          </div>
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
    </div>
  );
}

function formatMismatchReason(reason: string): string {
  switch (reason) {
    case 'llm_returned_no_fields':
      return 'LLM returned no candidate fields from the document.';
    case 'all_fields_empty':
      return 'All extracted fields were empty.';
    case 'no_evidence_localized':
      return 'No evidence could be localized in the document.';
    case 'no_keyword_matches':
      return 'Template keywords did not appear in the document text.';
    case 'low_keyword_match_rate':
      return 'Only a small fraction of template keywords appear in the document.';
    default:
      return reason.replace(/_/g, ' ');
  }
}
