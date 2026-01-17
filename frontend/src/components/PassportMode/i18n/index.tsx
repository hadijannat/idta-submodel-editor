/**
 * PassportMode i18n - Internationalization infrastructure.
 *
 * Provides a lightweight, type-safe i18n system for PassportMode components.
 * Uses React Context to allow runtime locale switching without page reload.
 *
 * @example
 * // In a component:
 * const { t } = usePassportI18n();
 * return <span>{t('toggle.editor')}</span>;
 *
 * @example
 * // To change locale:
 * const { setLocale } = usePassportI18n();
 * setLocale('de');
 */

import { createContext, useContext, useState, useCallback, useMemo, ReactNode } from 'react';
import type { PassportTranslations, TranslationKey } from './types';
import { en } from './en';
import { de } from './de';

/**
 * Supported locales.
 */
export type PassportLocale = 'en' | 'de';

/**
 * Default locale when none is specified.
 */
export const DEFAULT_LOCALE: PassportLocale = 'en';

/**
 * All available translations.
 */
const translations: Record<PassportLocale, PassportTranslations> = {
  en,
  de,
};

/**
 * Get a nested value from an object using dot notation.
 */
function getNestedValue(obj: PassportTranslations, path: string): string | undefined {
  const keys = path.split('.');
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let current: any = obj;

  for (const key of keys) {
    if (current === undefined || current === null) {
      return undefined;
    }
    current = current[key];
  }

  return typeof current === 'string' ? current : undefined;
}

/**
 * i18n context value interface.
 */
interface PassportI18nContextValue {
  /** Current locale */
  locale: PassportLocale;
  /** Set the current locale */
  setLocale: (locale: PassportLocale) => void;
  /** Translate a key */
  t: (key: TranslationKey, params?: Record<string, string | number>) => string;
  /** Get all available locales */
  availableLocales: PassportLocale[];
}

/**
 * React Context for i18n state.
 */
const PassportI18nContext = createContext<PassportI18nContextValue | null>(null);

/**
 * Detect preferred locale from browser settings.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function detectLocale(): PassportLocale {
  if (typeof navigator === 'undefined') {
    return DEFAULT_LOCALE;
  }

  const browserLang = navigator.language.split('-')[0].toLowerCase();
  if (browserLang === 'de') return 'de';
  return DEFAULT_LOCALE;
}

/**
 * Provider component for PassportMode i18n.
 *
 * Wrap your PassportMode components to enable i18n support.
 * If not provided, components will use the default standalone hook.
 */
export function PassportI18nProvider({
  children,
  initialLocale,
}: {
  children: ReactNode;
  initialLocale?: PassportLocale;
}) {
  const [locale, setLocaleState] = useState<PassportLocale>(
    initialLocale ?? detectLocale()
  );

  const setLocale = useCallback((newLocale: PassportLocale) => {
    if (translations[newLocale]) {
      setLocaleState(newLocale);
    } else {
      console.warn(`[PassportMode] Unknown locale: ${newLocale}, falling back to ${DEFAULT_LOCALE}`);
      setLocaleState(DEFAULT_LOCALE);
    }
  }, []);

  const t = useCallback(
    (key: TranslationKey, params?: Record<string, string | number>): string => {
      const translation = getNestedValue(translations[locale], key);

      if (!translation) {
        // Fallback to English
        const fallback = getNestedValue(translations.en, key);
        if (!fallback) {
          console.warn(`[PassportMode] Missing translation for key: ${key}`);
          return key;
        }
        return interpolate(fallback, params);
      }

      return interpolate(translation, params);
    },
    [locale]
  );

  const value = useMemo(
    () => ({
      locale,
      setLocale,
      t,
      availableLocales: Object.keys(translations) as PassportLocale[],
    }),
    [locale, setLocale, t]
  );

  return (
    <PassportI18nContext.Provider value={value}>
      {children}
    </PassportI18nContext.Provider>
  );
}

/**
 * Interpolate parameters into a translation string.
 *
 * @example
 * interpolate('Hello {{name}}!', { name: 'World' }) // 'Hello World!'
 */
function interpolate(text: string, params?: Record<string, string | number>): string {
  if (!params) return text;

  return text.replace(/\{\{(\w+)\}\}/g, (_, key) => {
    const value = params[key];
    return value !== undefined ? String(value) : `{{${key}}}`;
  });
}

/**
 * Hook to access i18n functionality within PassportMode components.
 *
 * Can be used with or without the PassportI18nProvider:
 * - With provider: shares locale state across all components
 * - Without provider: uses standalone state (useful for simple usage)
 */
// eslint-disable-next-line react-refresh/only-export-components
export function usePassportI18n(): PassportI18nContextValue {
  const context = useContext(PassportI18nContext);

  // Always call all hooks unconditionally to satisfy React's rules of hooks
  const [standaloneLocale, setStandaloneLocaleState] = useState<PassportLocale>(detectLocale);

  const setStandaloneLocale = useCallback((newLocale: PassportLocale) => {
    if (translations[newLocale]) {
      setStandaloneLocaleState(newLocale);
    } else {
      setStandaloneLocaleState(DEFAULT_LOCALE);
    }
  }, []);

  const standaloneT = useCallback(
    (key: TranslationKey, params?: Record<string, string | number>): string => {
      const translation = getNestedValue(translations[standaloneLocale], key);

      if (!translation) {
        const fallback = getNestedValue(translations.en, key);
        if (!fallback) {
          return key;
        }
        return interpolate(fallback, params);
      }

      return interpolate(translation, params);
    },
    [standaloneLocale]
  );

  const standaloneValue = useMemo(
    () => ({
      locale: standaloneLocale,
      setLocale: setStandaloneLocale,
      t: standaloneT,
      availableLocales: Object.keys(translations) as PassportLocale[],
    }),
    [standaloneLocale, setStandaloneLocale, standaloneT]
  );

  // Return context if provider exists, otherwise use standalone
  return context ?? standaloneValue;
}

// Re-export types
export type { PassportTranslations, TranslationKey } from './types';
