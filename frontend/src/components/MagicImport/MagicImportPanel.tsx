/**
 * MagicImportPanel - Main wizard UI for Magic Import.
 *
 * Provides:
 * - PDF upload
 * - Processing progress
 * - Extraction review with PDF viewer
 * - Apply to form
 */

import { useCallback, useMemo, useRef } from 'react';
import type { UseFormReturn } from 'react-hook-form';
import type { SubmodelFormData } from '../../types/aas-elements';
import { useMagicImport } from './useMagicImport';
import PdfViewer from './PdfViewer';
import ExtractionReviewTable from './ExtractionReviewTable';
import './MagicImport.css';

interface MagicImportPanelProps {
  templateName: string;
  templateStatus: 'published' | 'deprecated';
  templateVersion?: string | null;
  form: UseFormReturn<SubmodelFormData>;
  onClose?: () => void;
}

export default function MagicImportPanel({
  templateName,
  templateStatus,
  templateVersion,
  form,
  onClose,
}: MagicImportPanelProps) {
  const {
    job,
    result,
    extractions,
    selectedExtractionPath,
    isUploading,
    isProcessing,
    error,
    uploadPdf,
    cancelJob,
    selectExtraction,
    updateExtraction,
    approveExtraction,
    approveAll,
    applyToForm,
    reset,
    pdfUrl,
  } = useMagicImport({
    templateName,
    templateStatus,
    templateVersion,
    form,
  });

  const fileInputRef = useRef<HTMLInputElement>(null);

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

  // Get selected extraction for highlighting
  const selectedExtraction = useMemo(
    () => extractions.find((e) => e.path === selectedExtractionPath),
    [extractions, selectedExtractionPath]
  );

  // Count ready extractions
  const readyCount = extractions.filter((e) => e.user_approved || !e.needs_review).length;

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
            <button className="magic-import-panel__close" onClick={onClose}>
              &times;
            </button>
          )}
        </div>

        <div
          className="magic-import-panel__dropzone"
          onDrop={handleDrop}
          onDragOver={handleDragOver}
        >
          <input
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
        </div>

        {error && <div className="magic-import-panel__error">{error}</div>}
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
            <button className="magic-import-panel__close" onClick={onClose}>
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

          <button className="magic-import-panel__cancel" onClick={cancelJob}>
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
            <button className="magic-import-panel__close" onClick={onClose}>
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
          <button className="magic-import-panel__retry" onClick={reset}>
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
            <span>{result.fields_extracted} fields extracted</span>
            <span className="magic-import-panel__separator">|</span>
            <span>
              {result.fields_needing_review > 0
                ? `${result.fields_needing_review} need review`
                : 'All ready'}
            </span>
            <span className="magic-import-panel__separator">|</span>
            <span>Avg confidence: {Math.round(result.average_confidence * 100)}%</span>
          </div>
        )}
        {onClose && (
          <button className="magic-import-panel__close" onClick={onClose}>
            &times;
          </button>
        )}
      </div>

      <div className="magic-import-panel__content">
        {/* PDF Viewer (left side) */}
        <div className="magic-import-panel__viewer">
          <PdfViewer url={pdfUrl} evidence={selectedExtraction?.evidence ?? null} />
        </div>

        {/* Review Table (right side) */}
        <div className="magic-import-panel__review">
          <ExtractionReviewTable
            extractions={extractions}
            selectedPath={selectedExtractionPath}
            onSelect={selectExtraction}
            onUpdate={updateExtraction}
            onApprove={approveExtraction}
            onApproveAll={approveAll}
          />
        </div>
      </div>

      <div className="magic-import-panel__footer">
        <button className="magic-import-panel__btn--secondary" onClick={reset}>
          Start Over
        </button>
        <button
          className="magic-import-panel__btn--primary"
          onClick={applyToForm}
          disabled={readyCount === 0}
        >
          Apply {readyCount} Fields to Form
        </button>
      </div>
    </div>
  );
}
