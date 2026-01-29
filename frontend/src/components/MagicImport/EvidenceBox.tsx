/**
 * EvidenceBox - Interactive bounding box overlay for PDF evidence highlighting.
 *
 * Features:
 * - Numbered badge (top-left corner)
 * - Confidence-based border color (green/yellow/red)
 * - Hover state with tooltip showing exact quote
 * - Click handler for bidirectional selection
 */

import { useState, useCallback } from 'react';
import type { BBox } from '../../services/magicImportApi';
import './MagicImport.css';

export interface EvidenceBoxProps {
  /** The bounding box data with coordinates */
  box: BBox;
  /** 1-indexed box number for display */
  index: number;
  /** Whether this box is currently selected */
  isSelected: boolean;
  /** Whether this box is currently hovered from the table */
  isHighlightedFromTable: boolean;
  /** Overall evidence confidence (0-1) */
  confidence: number;
  /** Evidence quote text to show in tooltip */
  quote?: string;
  /** Callback when mouse enters the box */
  onHover: () => void;
  /** Callback when mouse leaves the box */
  onHoverEnd: () => void;
  /** Callback when box is clicked */
  onClick: () => void;
}

/**
 * Get CSS class based on confidence level.
 */
function getConfidenceClass(confidence: number): string {
  if (confidence >= 0.9) return 'evidence-box--high';
  if (confidence >= 0.7) return 'evidence-box--medium';
  return 'evidence-box--low';
}

/**
 * Get tooltip text based on confidence and quote.
 */
function getTooltipText(confidence: number, quote?: string): string {
  const confidenceText = `Confidence: ${Math.round(confidence * 100)}%`;
  if (quote) {
    const truncatedQuote = quote.length > 100 ? `${quote.slice(0, 100)}…` : quote;
    return `${confidenceText}\n"${truncatedQuote}"`;
  }
  return confidenceText;
}

export default function EvidenceBox({
  box,
  index,
  isSelected,
  isHighlightedFromTable,
  confidence,
  quote,
  onHover,
  onHoverEnd,
  onClick,
}: EvidenceBoxProps) {
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseEnter = useCallback(() => {
    setIsHovered(true);
    onHover();
  }, [onHover]);

  const handleMouseLeave = useCallback(() => {
    setIsHovered(false);
    onHoverEnd();
  }, [onHoverEnd]);

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onClick();
    },
    [onClick]
  );

  const confidenceClass = getConfidenceClass(confidence);
  const tooltipText = getTooltipText(confidence, quote);

  // Determine visual state
  const isActive = isSelected || isHighlightedFromTable || isHovered;

  return (
    <div
      className={`evidence-box ${confidenceClass} ${isActive ? 'evidence-box--active' : ''} ${
        isSelected ? 'evidence-box--selected' : ''
      }`}
      style={{
        left: `${box.x0 * 100}%`,
        top: `${box.y0 * 100}%`,
        width: `${(box.x1 - box.x0) * 100}%`,
        height: `${(box.y1 - box.y0) * 100}%`,
      }}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onClick={handleClick}
      title={tooltipText}
      role="button"
      tabIndex={0}
      aria-label={`Evidence box ${index}`}
    >
      {/* Numbered badge */}
      <span className="evidence-box__badge">{index}</span>

      {/* Hover tooltip (shown on hover) */}
      {isHovered && (
        <div className="evidence-box__tooltip">
          <div className="evidence-box__tooltip-confidence">
            {Math.round(confidence * 100)}% confidence
          </div>
          {quote && (
            <div className="evidence-box__tooltip-quote">
              "{quote.length > 80 ? `${quote.slice(0, 80)}…` : quote}"
            </div>
          )}
          <div className="evidence-box__tooltip-hint">Click to focus this evidence</div>
        </div>
      )}
    </div>
  );
}
