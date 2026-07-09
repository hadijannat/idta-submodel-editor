/**
 * ExportButton Component
 *
 * Renders a button to export the passport card as a PNG image.
 * Shows loading state during export and handles errors gracefully.
 */
import { useState, useCallback, useEffect, useRef } from 'react';
import { usePassportI18n } from './i18n';
import { exportToPng, isExportSupported } from './utils/exportImage';
import type { PassportCardType } from './utils/passportRegistry';

export interface ExportButtonProps {
  /** Reference to the card element to export */
  cardRef: React.RefObject<HTMLDivElement | null>;
  /** Type of passport card (used for filename) */
  passportType?: PassportCardType;
  /** Whether the button should be disabled */
  disabled?: boolean;
  /** Optional callback on export success */
  onExportSuccess?: (filename: string) => void;
  /** Optional callback on export error */
  onExportError?: (error: string) => void;
}

/** Download icon SVG (16x16 viewBox) */
const DownloadIcon = () => (
  <svg
    width="16"
    height="16"
    viewBox="0 0 16 16"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <path
      d="M8 1v9m0 0L5 7m3 3l3-3M2 12v1a2 2 0 002 2h8a2 2 0 002-2v-1"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
  </svg>
);

/** Spinner icon for loading state */
const SpinnerIcon = () => (
  <svg
    width="16"
    height="16"
    viewBox="0 0 16 16"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
    className="passport-export-spinner"
  >
    <circle
      cx="8"
      cy="8"
      r="6"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeDasharray="28"
      strokeDashoffset="8"
    />
  </svg>
);

/**
 * Maps passport type to human-readable filename prefix.
 */
function getFilenameForType(type?: PassportCardType): string {
  switch (type) {
    case 'nameplate':
      return 'Digital-Nameplate';
    case 'pcf':
      return 'Product-Carbon-Footprint';
    case 'generic':
    default:
      return 'Passport-Card';
  }
}

/**
 * Export button component for passport cards.
 *
 * @example
 * ```tsx
 * const cardRef = useRef<HTMLDivElement>(null);
 *
 * <PassportCard ref={cardRef} ... />
 * <ExportButton cardRef={cardRef} passportType="nameplate" />
 * ```
 */
export function ExportButton({
  cardRef,
  passportType,
  disabled = false,
  onExportSuccess,
  onExportError,
}: ExportButtonProps) {
  const { t } = usePassportI18n();
  const [isExporting, setIsExporting] = useState(false);
  const [exportStatus, setExportStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const resetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(false);

  const supported = isExportSupported();

  const clearResetTimer = useCallback(() => {
    if (resetTimerRef.current) {
      clearTimeout(resetTimerRef.current);
      resetTimerRef.current = null;
    }
  }, []);

  const scheduleStatusReset = useCallback(
    (delay: number) => {
      clearResetTimer();
      resetTimerRef.current = setTimeout(() => {
        setExportStatus('idle');
        resetTimerRef.current = null;
      }, delay);
    },
    [clearResetTimer]
  );

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      clearResetTimer();
    };
  }, [clearResetTimer]);

  const handleExport = useCallback(async () => {
    if (!cardRef.current || isExporting || disabled) return;

    clearResetTimer();
    setIsExporting(true);
    setExportStatus('idle');

    try {
      const filename = getFilenameForType(passportType);
      const result = await exportToPng(cardRef.current, { filename });

      if (!mountedRef.current) return;

      if (result.success) {
        setExportStatus('success');
        onExportSuccess?.(result.filename || filename);
        // Reset success status after brief display
        scheduleStatusReset(2000);
      } else {
        setExportStatus('error');
        onExportError?.(result.error || 'Unknown error');
        scheduleStatusReset(3000);
      }
    } catch (err) {
      if (!mountedRef.current) return;
      const errorMessage = err instanceof Error ? err.message : 'Export failed';
      setExportStatus('error');
      onExportError?.(errorMessage);
      scheduleStatusReset(3000);
    } finally {
      if (mountedRef.current) {
        setIsExporting(false);
      }
    }
  }, [
    cardRef,
    passportType,
    isExporting,
    disabled,
    onExportSuccess,
    onExportError,
    clearResetTimer,
    scheduleStatusReset,
  ]);

  // Don't render if export isn't supported
  if (!supported) {
    return null;
  }

  const buttonClassName = [
    'passport-export-button',
    isExporting && 'passport-export-button--loading',
    exportStatus === 'success' && 'passport-export-button--success',
    exportStatus === 'error' && 'passport-export-button--error',
    disabled && 'passport-export-button--disabled',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <button
      type="button"
      className={buttonClassName}
      onClick={handleExport}
      disabled={disabled || isExporting}
      title={isExporting ? t('export.exporting') : t('export.tooltip')}
      aria-label={isExporting ? t('export.exporting') : t('export.tooltip')}
      data-export-ignore="true"
    >
      {isExporting ? <SpinnerIcon /> : <DownloadIcon />}
      <span className="passport-export-button-text">
        {isExporting ? t('export.exporting') : t('export.button')}
      </span>
    </button>
  );
}

export default ExportButton;
