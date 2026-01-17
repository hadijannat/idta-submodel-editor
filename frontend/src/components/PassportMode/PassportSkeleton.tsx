/**
 * PassportSkeleton - Loading placeholder for passport card transitions.
 *
 * Displays a skeleton UI with shimmer animation while passport data
 * is being prepared. Respects prefers-reduced-motion.
 */

import { memo } from 'react';
import { usePassportI18n } from './i18n';

interface PassportSkeletonProps {
  /** Card type hint for tailored skeleton layout */
  cardType?: 'nameplate' | 'pcf' | 'generic';
}

/**
 * Skeleton placeholder box with shimmer effect.
 */
function SkeletonBox({
  width,
  height,
  className = '',
}: {
  width?: string;
  height?: string;
  className?: string;
}) {
  return (
    <div
      className={`passport-skeleton-box ${className}`}
      style={{ width, height }}
      aria-hidden="true"
    />
  );
}

/**
 * Skeleton row for label-value pairs.
 */
function SkeletonRow({ labelWidth = '30%', valueWidth = '50%' }: { labelWidth?: string; valueWidth?: string }) {
  return (
    <div className="passport-skeleton-row">
      <SkeletonBox width={labelWidth} height="12px" />
      <SkeletonBox width={valueWidth} height="16px" />
    </div>
  );
}

/**
 * Nameplate-style skeleton with header, marker bar, and grid fields.
 */
function NameplateSkeleton() {
  return (
    <div className="passport-skeleton nameplate-skeleton">
      {/* Header */}
      <div className="passport-skeleton-header">
        <SkeletonBox width="60%" height="28px" />
        <SkeletonBox width="40%" height="16px" className="skeleton-margin-top" />
      </div>

      {/* Marker bar */}
      <div className="passport-skeleton-marker">
        <SkeletonBox width="80%" height="28px" />
      </div>

      {/* Fields grid */}
      <div className="passport-skeleton-grid">
        <SkeletonRow labelWidth="40%" valueWidth="70%" />
        <SkeletonRow labelWidth="35%" valueWidth="60%" />
        <SkeletonRow labelWidth="45%" valueWidth="65%" />
        <SkeletonRow labelWidth="38%" valueWidth="55%" />
      </div>
    </div>
  );
}

/**
 * PCF-style skeleton with main metric, pie chart, and details.
 */
function PCFSkeleton() {
  return (
    <div className="passport-skeleton pcf-skeleton">
      {/* Header */}
      <div className="passport-skeleton-header pcf-skeleton-header">
        <SkeletonBox width="70%" height="24px" />
        <SkeletonBox width="40%" height="14px" className="skeleton-margin-top" />
      </div>

      {/* Main metric */}
      <div className="passport-skeleton-metric">
        <SkeletonBox width="30%" height="12px" />
        <SkeletonBox width="50%" height="48px" className="skeleton-margin-top" />
      </div>

      {/* Chart section */}
      <div className="passport-skeleton-chart">
        <SkeletonBox width="160px" height="160px" className="skeleton-circle" />
        <div className="passport-skeleton-legend">
          <SkeletonRow labelWidth="60%" valueWidth="25%" />
          <SkeletonRow labelWidth="70%" valueWidth="20%" />
          <SkeletonRow labelWidth="55%" valueWidth="30%" />
        </div>
      </div>

      {/* Details */}
      <div className="passport-skeleton-details">
        <SkeletonRow labelWidth="35%" valueWidth="60%" />
        <SkeletonRow labelWidth="40%" valueWidth="50%" />
      </div>
    </div>
  );
}

/**
 * Generic skeleton with header and field rows.
 */
function GenericSkeleton() {
  return (
    <div className="passport-skeleton generic-skeleton">
      {/* Header */}
      <div className="passport-skeleton-header generic-skeleton-header">
        <SkeletonBox width="65%" height="24px" />
        <SkeletonBox width="100%" height="12px" className="skeleton-margin-top" />
      </div>

      {/* Content sections */}
      <div className="passport-skeleton-section">
        <SkeletonBox width="30%" height="14px" className="skeleton-section-title" />
        <SkeletonRow labelWidth="35%" valueWidth="55%" />
        <SkeletonRow labelWidth="40%" valueWidth="45%" />
        <SkeletonRow labelWidth="30%" valueWidth="65%" />
      </div>

      <div className="passport-skeleton-section">
        <SkeletonBox width="25%" height="14px" className="skeleton-section-title" />
        <SkeletonRow labelWidth="38%" valueWidth="50%" />
        <SkeletonRow labelWidth="42%" valueWidth="40%" />
      </div>
    </div>
  );
}

/**
 * PassportSkeleton component.
 *
 * Renders an appropriate skeleton layout based on expected card type.
 * Falls back to generic skeleton if type is unknown.
 */
function PassportSkeleton({ cardType = 'generic' }: PassportSkeletonProps) {
  const { t } = usePassportI18n();

  return (
    <div
      className="passport-skeleton-container"
      role="status"
      aria-label={t('loading.ariaLabel')}
      aria-live="polite"
    >
      {cardType === 'nameplate' && <NameplateSkeleton />}
      {cardType === 'pcf' && <PCFSkeleton />}
      {cardType === 'generic' && <GenericSkeleton />}
      <span className="visually-hidden">{t('loading.loading')}</span>
    </div>
  );
}

export default memo(PassportSkeleton);
