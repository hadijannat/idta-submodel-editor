/**
 * ConfidenceBadge - Visual indicator for extraction confidence with optional reasons.
 */

import type { ConfidenceBreakdown, ConfidenceReason } from '../../services/magicImportApi';
import './MagicImport.css';

interface ConfidenceBadgeProps {
  confidence: number;
  needsReview: boolean;
  userApproved: boolean;
  userEdited: boolean;
  size?: 'sm' | 'md';
  confidenceBreakdown?: ConfidenceBreakdown | null;
  confidenceReasons?: ConfidenceReason[];
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

export default function ConfidenceBadge({
  confidence,
  needsReview,
  userApproved,
  userEdited,
  size = 'md',
  confidenceBreakdown,
  confidenceReasons = [],
}: ConfidenceBadgeProps) {
  // Determine badge type
  let badgeClass = 'confidence-badge';
  let label: string;

  if (userEdited) {
    badgeClass += ' confidence-badge--edited';
    label = 'Edited';
  } else if (userApproved) {
    badgeClass += ' confidence-badge--approved';
    label = 'Approved';
  } else if (needsReview) {
    badgeClass += ' confidence-badge--review';
    label = `${Math.round(confidence * 100)}%`;
  } else if (confidence >= 0.9) {
    badgeClass += ' confidence-badge--high';
    label = `${Math.round(confidence * 100)}%`;
  } else if (confidence >= 0.8) {
    badgeClass += ' confidence-badge--medium';
    label = `${Math.round(confidence * 100)}%`;
  } else {
    badgeClass += ' confidence-badge--low';
    label = `${Math.round(confidence * 100)}%`;
  }

  if (size === 'sm') {
    badgeClass += ' confidence-badge--sm';
  }

  // Get primary reason (highest severity)
  const sortedReasons = [...confidenceReasons].sort((a, b) => {
    const severityOrder = { error: 0, warning: 1, info: 2 };
    return severityOrder[a.severity] - severityOrder[b.severity];
  });
  const primaryReason = sortedReasons[0];

  // Build tooltip content
  const buildTooltipTitle = () => {
    const parts: string[] = [`Confidence: ${Math.round(confidence * 100)}%`];

    if (confidenceBreakdown) {
      parts.push(
        `\nBreakdown:`,
        `  LLM: ${Math.round(confidenceBreakdown.llm * 100)}%`,
        `  Localizer: ${Math.round(confidenceBreakdown.localizer * 100)}%`,
        `  OCR: ${Math.round(confidenceBreakdown.ocr * 100)}%`,
        `  Rules: ${Math.round(confidenceBreakdown.rules * 100)}%`
      );
    }

    if (confidenceReasons.length > 0) {
      parts.push(`\nReasons:`);
      for (const reason of sortedReasons) {
        parts.push(`  ${getSeverityIcon(reason.severity)} ${reason.message}`);
      }
    }

    return parts.join('\n');
  };

  const hasReasons = confidenceReasons.length > 0;

  return (
    <span
      className={`${badgeClass} ${hasReasons ? 'confidence-badge--has-reasons' : ''}`}
      title={buildTooltipTitle()}
    >
      <span className="confidence-badge__label">{label}</span>
      {primaryReason && !userEdited && !userApproved && (
        <span className="confidence-badge__reason-hint">
          {getSeverityIcon(primaryReason.severity)}
        </span>
      )}
    </span>
  );
}
