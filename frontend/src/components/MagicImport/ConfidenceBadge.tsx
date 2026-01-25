/**
 * ConfidenceBadge - Visual indicator for extraction confidence.
 */

import './MagicImport.css';

interface ConfidenceBadgeProps {
  confidence: number;
  needsReview: boolean;
  userApproved: boolean;
  userEdited: boolean;
  size?: 'sm' | 'md';
}

export default function ConfidenceBadge({
  confidence,
  needsReview,
  userApproved,
  userEdited,
  size = 'md',
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

  return (
    <span className={badgeClass} title={`Confidence: ${Math.round(confidence * 100)}%`}>
      {label}
    </span>
  );
}
