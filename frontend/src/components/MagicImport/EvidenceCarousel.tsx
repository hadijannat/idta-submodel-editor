/**
 * EvidenceCarousel - Navigation UI for multi-box evidence.
 *
 * When an extraction has evidence spanning multiple bounding boxes
 * (possibly on different pages), this component provides navigation
 * between them with visual indicators.
 *
 * Features:
 * - Prev/Next navigation arrows
 * - Page number badges showing evidence locations
 * - Mini-map dots for quick navigation
 * - "View All" toggle to highlight all boxes simultaneously
 */

import { useCallback } from 'react';
import type { EvidenceRef } from '../../services/magicImportApi';
import './MagicImport.css';

export interface EvidenceCarouselProps {
  /** Evidence data with multiple boxes */
  evidence: EvidenceRef;
  /** Currently focused box index */
  currentBoxIndex: number;
  /** Callback when navigating to a specific box */
  onNavigate: (boxIndex: number) => void;
  /** Whether "View All" mode is active */
  viewAllActive?: boolean;
  /** Callback to toggle "View All" mode */
  onToggleViewAll?: () => void;
}

export default function EvidenceCarousel({
  evidence,
  currentBoxIndex,
  onNavigate,
  viewAllActive = false,
  onToggleViewAll,
}: EvidenceCarouselProps) {
  const totalBoxes = evidence.boxes.length;

  // Navigation handlers
  const handlePrev = useCallback(() => {
    if (currentBoxIndex > 0) {
      onNavigate(currentBoxIndex - 1);
    }
  }, [currentBoxIndex, onNavigate]);

  const handleNext = useCallback(() => {
    if (currentBoxIndex < totalBoxes - 1) {
      onNavigate(currentBoxIndex + 1);
    }
  }, [currentBoxIndex, totalBoxes, onNavigate]);

  // Don't render if only one box
  if (totalBoxes <= 1) {
    return null;
  }

  return (
    <div className="evidence-carousel">
      <div className="evidence-carousel__header">
        <span className="evidence-carousel__title">
          Evidence Location {currentBoxIndex + 1} of {totalBoxes}
        </span>
        {onToggleViewAll && (
          <button
            type="button"
            className={`evidence-carousel__view-all ${viewAllActive ? 'active' : ''}`}
            onClick={onToggleViewAll}
            title={viewAllActive ? 'Show single box' : 'Show all boxes'}
          >
            {viewAllActive ? 'Show One' : 'View All'}
          </button>
        )}
      </div>

      <div className="evidence-carousel__nav">
        <button
          type="button"
          className="evidence-carousel__arrow evidence-carousel__arrow--prev"
          onClick={handlePrev}
          disabled={currentBoxIndex === 0}
          aria-label="Previous evidence"
        >
          ‹
        </button>

        {/* Mini-map dots */}
        <div className="evidence-carousel__dots">
          {evidence.boxes.map((box, idx) => (
            <button
              key={box.box_id || idx}
              type="button"
              className={`evidence-carousel__dot ${
                idx === currentBoxIndex ? 'evidence-carousel__dot--active' : ''
              }`}
              onClick={() => onNavigate(idx)}
              aria-label={`Go to evidence ${idx + 1}`}
              title={`Evidence ${idx + 1}${box.word_confidence ? ` (${Math.round(box.word_confidence * 100)}% OCR)` : ''}`}
            >
              {idx + 1}
            </button>
          ))}
        </div>

        <button
          type="button"
          className="evidence-carousel__arrow evidence-carousel__arrow--next"
          onClick={handleNext}
          disabled={currentBoxIndex === totalBoxes - 1}
          aria-label="Next evidence"
        >
          ›
        </button>
      </div>

      {/* Current box info */}
      <div className="evidence-carousel__info">
        <span className="evidence-carousel__page-badge">
          Page {evidence.page + 1}
        </span>
        <span className="evidence-carousel__method-badge">
          {evidence.method}
        </span>
        {evidence.boxes[currentBoxIndex]?.word_confidence !== undefined &&
          evidence.boxes[currentBoxIndex]?.word_confidence !== null && (
            <span className="evidence-carousel__confidence-badge">
              OCR: {Math.round(evidence.boxes[currentBoxIndex].word_confidence! * 100)}%
            </span>
          )}
      </div>
    </div>
  );
}
