/**
 * ProvenancePanel - Shows detailed provenance information for a selected extraction.
 *
 * Displays evidence quote, confidence breakdown, reasons, and action buttons.
 * For extractions with multi-box evidence, includes an EvidenceCarousel for navigation.
 */

import { useState, useCallback, useEffect } from 'react';
import type { FieldExtraction } from '../../services/magicImportApi';
import EvidenceCarousel from './EvidenceCarousel';
import './MagicImport.css';

interface ProvenancePanelProps {
  extraction: FieldExtraction | null;
  onGoToPdf?: () => void;
  onEdit?: () => void;
  onApprove?: () => void;
  onReExtract?: () => void;
  onClose?: () => void;
  isReExtracting?: boolean;
  /** Callback when user navigates to a specific evidence box */
  onFocusBox?: (boxIndex: number) => void;
  /** Callback when "View All" is toggled */
  onToggleViewAll?: (active: boolean) => void;
}

/**
 * Get severity icon for a reason.
 */
function getSeverityIcon(severity: 'info' | 'warning' | 'error'): string {
  switch (severity) {
    case 'error':
      return '⛔';
    case 'warning':
      return '⚠️';
    case 'info':
      return 'ℹ️';
  }
}

/**
 * Get color class for confidence bar segment.
 */
function getBarColor(value: number): string {
  if (value >= 0.9) return 'provenance-panel__bar--high';
  if (value >= 0.7) return 'provenance-panel__bar--medium';
  return 'provenance-panel__bar--low';
}

export default function ProvenancePanel({
  extraction,
  onGoToPdf,
  onEdit,
  onApprove,
  onReExtract,
  onClose,
  isReExtracting = false,
  onFocusBox,
  onToggleViewAll,
}: ProvenancePanelProps) {
  const [expanded, setExpanded] = useState(true);
  const [currentBoxIndex, setCurrentBoxIndex] = useState(0);
  const [viewAllActive, setViewAllActive] = useState(false);

  // Handle carousel navigation
  const handleCarouselNavigate = useCallback(
    (boxIndex: number) => {
      setCurrentBoxIndex(boxIndex);
      if (viewAllActive) {
        setViewAllActive(false);
        onToggleViewAll?.(false);
      }
      onFocusBox?.(boxIndex);
    },
    [onFocusBox, onToggleViewAll, viewAllActive]
  );

  // Toggle "View All" mode
  const handleToggleViewAll = useCallback(() => {
    setViewAllActive((prev) => {
      const next = !prev;
      onToggleViewAll?.(next);
      if (!next) {
        onFocusBox?.(currentBoxIndex);
      }
      return next;
    });
  }, [currentBoxIndex, onFocusBox, onToggleViewAll]);

  // Reset carousel state when extraction changes
  useEffect(() => {
    setCurrentBoxIndex(0);
    setViewAllActive(false);
    onToggleViewAll?.(false);
  }, [extraction?.path, onToggleViewAll]);

  if (!extraction) {
    return null;
  }

  const { confidence_breakdown, confidence_reasons, evidence } = extraction;
  const hasMultipleBoxes = evidence && evidence.boxes.length > 1;

  // Sort reasons by severity
  const sortedReasons = [...(confidence_reasons || [])].sort((a, b) => {
    const severityOrder = { error: 0, warning: 1, info: 2 };
    return severityOrder[a.severity] - severityOrder[b.severity];
  });

  return (
    <div className={`provenance-panel ${expanded ? 'provenance-panel--expanded' : ''}`}>
      <div className="provenance-panel__header">
        <button
          type="button"
          className="provenance-panel__toggle"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? '▼' : '▶'} Field Provenance
        </button>
        {onClose && (
          <button
            type="button"
            className="provenance-panel__close"
            onClick={onClose}
            title="Close panel"
          >
            ×
          </button>
        )}
      </div>

      {expanded && (
        <div className="provenance-panel__content">
          {/* Field info */}
          <div className="provenance-panel__field-info">
            <div className="provenance-panel__field-path">{extraction.path}</div>
            <div className="provenance-panel__field-value">
              <strong>Value:</strong> {extraction.value_raw || '—'}
            </div>
            {extraction.value_type && (
              <div className="provenance-panel__field-type">
                <strong>Type:</strong> {extraction.value_type}
              </div>
            )}
          </div>

          {/* Evidence quote */}
          {evidence ? (
            <div className="provenance-panel__evidence">
              <div className="provenance-panel__section-title">
                Evidence
                {hasMultipleBoxes && (
                  <span className="provenance-panel__box-count">
                    ({evidence.boxes.length} locations)
                  </span>
                )}
              </div>
              <blockquote className="provenance-panel__quote">
                "{evidence.quote}"
              </blockquote>
              <div className="provenance-panel__evidence-meta">
                Page {evidence.page + 1} • {evidence.method} •{' '}
                {Math.round(evidence.locator_score * 100)}% match
              </div>

              {/* Carousel for multi-box evidence */}
              {hasMultipleBoxes && (
                <EvidenceCarousel
                  evidence={evidence}
                  currentBoxIndex={currentBoxIndex}
                  onNavigate={handleCarouselNavigate}
                  viewAllActive={viewAllActive}
                  onToggleViewAll={handleToggleViewAll}
                />
              )}
            </div>
          ) : (
            <div className="provenance-panel__no-evidence">
              No evidence located in document
            </div>
          )}

          {/* Confidence breakdown */}
          {confidence_breakdown && (
            <div className="provenance-panel__breakdown">
              <div className="provenance-panel__section-title">
                Confidence Breakdown ({Math.round(extraction.confidence * 100)}%)
              </div>
              <div className="provenance-panel__bars">
                <div className="provenance-panel__bar-row">
                  <span className="provenance-panel__bar-label">LLM (35%)</span>
                  <div className="provenance-panel__bar-track">
                    <div
                      className={`provenance-panel__bar-fill ${getBarColor(confidence_breakdown.llm)}`}
                      style={{ width: `${confidence_breakdown.llm * 100}%` }}
                    />
                  </div>
                  <span className="provenance-panel__bar-value">
                    {Math.round(confidence_breakdown.llm * 100)}%
                  </span>
                </div>
                <div className="provenance-panel__bar-row">
                  <span className="provenance-panel__bar-label">Localizer (40%)</span>
                  <div className="provenance-panel__bar-track">
                    <div
                      className={`provenance-panel__bar-fill ${getBarColor(confidence_breakdown.localizer)}`}
                      style={{ width: `${confidence_breakdown.localizer * 100}%` }}
                    />
                  </div>
                  <span className="provenance-panel__bar-value">
                    {Math.round(confidence_breakdown.localizer * 100)}%
                  </span>
                </div>
                <div className="provenance-panel__bar-row">
                  <span className="provenance-panel__bar-label">OCR (15%)</span>
                  <div className="provenance-panel__bar-track">
                    <div
                      className={`provenance-panel__bar-fill ${getBarColor(confidence_breakdown.ocr)}`}
                      style={{ width: `${confidence_breakdown.ocr * 100}%` }}
                    />
                  </div>
                  <span className="provenance-panel__bar-value">
                    {Math.round(confidence_breakdown.ocr * 100)}%
                  </span>
                </div>
                <div className="provenance-panel__bar-row">
                  <span className="provenance-panel__bar-label">Rules (10%)</span>
                  <div className="provenance-panel__bar-track">
                    <div
                      className={`provenance-panel__bar-fill ${getBarColor(confidence_breakdown.rules)}`}
                      style={{ width: `${confidence_breakdown.rules * 100}%` }}
                    />
                  </div>
                  <span className="provenance-panel__bar-value">
                    {Math.round(confidence_breakdown.rules * 100)}%
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Confidence reasons */}
          {sortedReasons.length > 0 && (
            <div className="provenance-panel__reasons">
              <div className="provenance-panel__section-title">Issues & Warnings</div>
              <ul className="provenance-panel__reason-list">
                {sortedReasons.map((reason, idx) => (
                  <li
                    key={idx}
                    className={`provenance-panel__reason provenance-panel__reason--${reason.severity}`}
                  >
                    <span className="provenance-panel__reason-icon">
                      {getSeverityIcon(reason.severity)}
                    </span>
                    <span className="provenance-panel__reason-message">
                      {reason.message}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Actions */}
          <div className="provenance-panel__actions">
            {evidence && onGoToPdf && (
              <button
                type="button"
                className="provenance-panel__btn provenance-panel__btn--secondary"
                onClick={onGoToPdf}
              >
                Go to PDF
              </button>
            )}
            {onEdit && (
              <button
                type="button"
                className="provenance-panel__btn provenance-panel__btn--secondary"
                onClick={onEdit}
              >
                Edit
              </button>
            )}
            {onReExtract && (
              <button
                type="button"
                className="provenance-panel__btn provenance-panel__btn--secondary"
                onClick={onReExtract}
                disabled={isReExtracting}
              >
                {isReExtracting ? 'Re-extracting…' : 'Re-extract'}
              </button>
            )}
            {onApprove && extraction.needs_review && !extraction.user_approved && (
              <button
                type="button"
                className="provenance-panel__btn provenance-panel__btn--primary"
                onClick={onApprove}
              >
                Approve
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
