/**
 * MigrationConfidenceBadge - Visual indicator for migration match confidence.
 */

import './TemplateOps.css';

interface MigrationConfidenceBadgeProps {
  confidence: number;
  matchReason: 'exact_path' | 'semantic_id' | 'fuzzy' | 'unmapped';
  breakingChange?: boolean;
  size?: 'sm' | 'md';
}

/**
 * Get label for match reason.
 */
function getReasonLabel(reason: string): string {
  switch (reason) {
    case 'exact_path':
      return 'Exact';
    case 'semantic_id':
      return 'Semantic';
    case 'fuzzy':
      return 'Fuzzy';
    case 'unmapped':
      return 'Unmapped';
    default:
      return reason;
  }
}

export default function MigrationConfidenceBadge({
  confidence,
  matchReason,
  breakingChange = false,
  size = 'md',
}: MigrationConfidenceBadgeProps) {
  let badgeClass = 'migration-badge';

  // Color based on match quality
  if (matchReason === 'unmapped') {
    badgeClass += ' migration-badge--unmapped';
  } else if (breakingChange) {
    badgeClass += ' migration-badge--breaking';
  } else if (confidence >= 0.9) {
    badgeClass += ' migration-badge--high';
  } else if (confidence >= 0.7) {
    badgeClass += ' migration-badge--medium';
  } else {
    badgeClass += ' migration-badge--low';
  }

  if (size === 'sm') {
    badgeClass += ' migration-badge--sm';
  }

  const tooltipParts = [
    `Confidence: ${Math.round(confidence * 100)}%`,
    `Match Type: ${getReasonLabel(matchReason)}`,
  ];
  if (breakingChange) {
    tooltipParts.push('⚠️ Breaking change detected');
  }

  return (
    <span className={badgeClass} title={tooltipParts.join('\n')}>
      <span className="migration-badge__confidence">
        {matchReason === 'unmapped' ? '—' : `${Math.round(confidence * 100)}%`}
      </span>
      <span className="migration-badge__reason">{getReasonLabel(matchReason)}</span>
      {breakingChange && <span className="migration-badge__warning">⚠️</span>}
    </span>
  );
}
