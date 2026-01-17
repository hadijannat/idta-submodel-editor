/**
 * PassportMode - WYSIWYG visualization mode for submodel data.
 *
 * Provides a toggle between Editor mode and Passport mode, where
 * Passport mode renders a card visualization of the form data.
 */

import { useState, useEffect } from 'react';
import type { SubmodelUISchema } from '../../types/ui-schema';
import type { SubmodelFormData } from '../../types/aas-elements';
import PassportCard from './PassportCard';
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
  return (
    <div className="passport-mode-toggle" role="group" aria-label="View mode">
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
        Editor
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
        Passport View
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

  return (
    <>
      <PassportModeToggle
        mode={mode}
        onModeChange={setMode}
        editorId={editorId}
        passportId={passportId}
      />

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
        className={`passport-content-area ${isPassport ? 'visible' : 'hidden'}`}
        hidden={!isPassport}
        aria-hidden={!isPassport}
      >
        {isPassport && <PassportCard schema={schema} formData={formData} />}
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
// eslint-disable-next-line react-refresh/only-export-components
export { detectPassportType, getCardTypeLabel } from './utils/passportRegistry';
export type { PassportCardType } from './utils/passportRegistry';
