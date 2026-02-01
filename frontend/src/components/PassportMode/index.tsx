/**
 * PassportMode - WYSIWYG visualization mode for submodel data.
 *
 * Provides a toggle between Editor mode and Passport mode, where
 * Passport mode renders a card visualization of the form data.
 */

import { useState, useEffect, useTransition, useRef } from 'react';
import type { SubmodelUISchema } from '../../types/ui-schema';
import type { SubmodelFormData } from '../../types/aas-elements';
import PassportCard from './PassportCard';
import PassportSkeleton from './PassportSkeleton';
import { ErrorBoundary } from './ErrorBoundary';
import { ExportButton } from './ExportButton';
import { detectPassportType } from './utils/passportRegistry';
import { usePassportI18n } from './i18n';
import './PassportMode.css';

const STORAGE_KEY = 'passport-mode-preference';

export type ViewMode = 'editor' | 'passport';

interface PassportModeToggleProps {
  mode: ViewMode;
  onModeChange: (mode: ViewMode) => void;
  editorId?: string;
  passportId?: string;
}

/**
 * Toggle button group for switching between Editor and Passport modes.
 */
export function PassportModeToggle({
  mode,
  onModeChange,
  editorId,
  passportId,
}: PassportModeToggleProps) {
  const { t } = usePassportI18n();

  return (
    <div className="passport-mode-toggle" role="group" aria-label={t('toggle.viewModeLabel')}>
      <button
        type="button"
        aria-pressed={mode === 'editor'}
        aria-controls={editorId}
        className={mode === 'editor' ? 'active' : ''}
        onClick={() => onModeChange('editor')}
      >
        <span className="mode-icon" aria-hidden="true">
          {/* Edit icon */}
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
            <path d="M12.146.854a.5.5 0 0 1 .708 0l2.292 2.292a.5.5 0 0 1 0 .708l-9.5 9.5a.5.5 0 0 1-.168.11l-4 1.5a.5.5 0 0 1-.65-.65l1.5-4a.5.5 0 0 1 .11-.168l9.5-9.5zM11.207 2L2 11.207V12h.793L12 2.793 11.207 2z" />
          </svg>
        </span>
        {t('toggle.editor')}
      </button>
      <button
        type="button"
        aria-pressed={mode === 'passport'}
        aria-controls={passportId}
        className={mode === 'passport' ? 'active' : ''}
        onClick={() => onModeChange('passport')}
      >
        <span className="mode-icon" aria-hidden="true">
          {/* Card/ID icon */}
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
            <path d="M0 4a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H2a2 2 0 0 1-2-2V4zm2-1a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V4a1 1 0 0 0-1-1H2z" />
            <path d="M6 9a1 1 0 1 0 0-2 1 1 0 0 0 0 2zm3 0h2a.5.5 0 0 0 0-1H9a.5.5 0 0 0 0 1zm-3 2a1 1 0 1 0 0-2 1 1 0 0 0 0 2zm3 0h2a.5.5 0 0 0 0-1H9a.5.5 0 0 0 0 1z" />
          </svg>
        </span>
        {t('toggle.passportView')}
      </button>
    </div>
  );
}

interface PassportViewProps {
  schema: SubmodelUISchema;
  formData: SubmodelFormData | undefined;
  children: React.ReactNode;
}

/**
 * PassportView container that manages mode switching.
 *
 * Renders either the editor (children) or the passport card visualization.
 * Uses CSS display:none to hide the inactive view, preserving form state.
 * Shows a skeleton during mode transitions for smoother UX.
 */
export function PassportView({ schema, formData, children }: PassportViewProps) {
  const [mode, setMode] = useState<ViewMode>(() => {
    // Initialize from localStorage
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === 'passport') return 'passport';
    } catch {
      // localStorage not available
    }
    return 'editor';
  });

  // Use transition for smoother mode switches
  const [isPending, startTransition] = useTransition();
  const [showSkeleton, setShowSkeleton] = useState(false);

  // Ref for the passport card container (used for export)
  const cardContainerRef = useRef<HTMLDivElement>(null);

  // Handle mode change with transition
  const handleModeChange = (newMode: ViewMode) => {
    if (newMode === 'passport' && mode !== 'passport') {
      // Show skeleton briefly when switching to passport mode
      setShowSkeleton(true);
      startTransition(() => {
        setMode(newMode);
      });
      // Hide skeleton after a short delay
      setTimeout(() => setShowSkeleton(false), 150);
    } else {
      setMode(newMode);
    }
  };

  // Persist preference
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, mode);
    } catch {
      // localStorage not available
    }
  }, [mode]);

  const editorId = 'passport-editor-panel';
  const passportId = 'passport-card-panel';
  const isEditor = mode === 'editor';
  const isPassport = mode === 'passport';
  const cardType = detectPassportType(schema);
  const isCardVisible = isPassport && !showSkeleton && !isPending;

  return (
    <>
      <div className="passport-mode-header">
        <PassportModeToggle
          mode={mode}
          onModeChange={handleModeChange}
          editorId={editorId}
          passportId={passportId}
        />

        {/* Export button - only visible in passport mode */}
        {isPassport && (
          <ExportButton
            cardRef={cardContainerRef}
            passportType={cardType}
            disabled={!isCardVisible}
          />
        )}
      </div>

      {/* Editor content - hidden via CSS when in passport mode */}
      <div
        id={editorId}
        className={`passport-content-area ${isEditor ? 'visible' : 'hidden'}`}
        hidden={!isEditor}
        aria-hidden={!isEditor}
      >
        {children}
      </div>

      {/* Passport card - only rendered when in passport mode */}
      <div
        id={passportId}
        data-testid="passport-view"
        className={`passport-content-area ${isPassport ? 'visible' : 'hidden'}`}
        hidden={!isPassport}
        aria-hidden={!isPassport}
      >
        {isPassport && (
          <ErrorBoundary>
            {(showSkeleton || isPending) ? (
              <PassportSkeleton cardType={cardType} />
            ) : (
              <div ref={cardContainerRef} className="passport-card-export-container">
                <PassportCard schema={schema} formData={formData} />
              </div>
            )}
          </ErrorBoundary>
        )}
      </div>
    </>
  );
}

/**
 * Hook for managing passport mode state externally.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function usePassportMode() {
  const [mode, setMode] = useState<ViewMode>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === 'passport') return 'passport';
    } catch {
      // localStorage not available
    }
    return 'editor';
  });

  const toggleMode = () => {
    setMode((prev) => (prev === 'editor' ? 'passport' : 'editor'));
  };

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, mode);
    } catch {
      // localStorage not available
    }
  }, [mode]);

  return {
    mode,
    setMode,
    toggleMode,
    isPassportMode: mode === 'passport',
    isEditorMode: mode === 'editor',
  };
}

export { PassportCard };
export { default as PassportSkeleton } from './PassportSkeleton';
export { ErrorBoundary };
export { ExportButton } from './ExportButton';
// eslint-disable-next-line react-refresh/only-export-components
export { detectPassportType, getCardTypeLabel } from './utils/passportRegistry';
export type { PassportCardType } from './utils/passportRegistry';

// i18n exports
// eslint-disable-next-line react-refresh/only-export-components
export { usePassportI18n, PassportI18nProvider, detectLocale, DEFAULT_LOCALE } from './i18n';
export type { PassportLocale, PassportTranslations, TranslationKey } from './i18n';
