/**
 * ISO 639-1 language code utilities for MultiLanguageProperty handling.
 *
 * Provides validation, Unicode safety, and translation gap detection.
 */

/**
 * ISO 639-1 language metadata.
 */
export interface LanguageInfo {
  /** Native name of the language */
  name: string;
  /** English name of the language */
  englishName: string;
  /** Whether the language is right-to-left */
  rtl: boolean;
}

/**
 * ISO 639-1 language codes with metadata.
 * Subset of most common languages used in AAS templates.
 */
export const ISO_639_1: Record<string, LanguageInfo> = {
  // Major global languages
  en: { name: 'English', englishName: 'English', rtl: false },
  de: { name: 'Deutsch', englishName: 'German', rtl: false },
  fr: { name: 'Français', englishName: 'French', rtl: false },
  es: { name: 'Español', englishName: 'Spanish', rtl: false },
  it: { name: 'Italiano', englishName: 'Italian', rtl: false },
  pt: { name: 'Português', englishName: 'Portuguese', rtl: false },
  nl: { name: 'Nederlands', englishName: 'Dutch', rtl: false },
  pl: { name: 'Polski', englishName: 'Polish', rtl: false },
  ru: { name: 'Русский', englishName: 'Russian', rtl: false },
  uk: { name: 'Українська', englishName: 'Ukrainian', rtl: false },

  // Asian languages
  zh: { name: '中文', englishName: 'Chinese', rtl: false },
  ja: { name: '日本語', englishName: 'Japanese', rtl: false },
  ko: { name: '한국어', englishName: 'Korean', rtl: false },
  vi: { name: 'Tiếng Việt', englishName: 'Vietnamese', rtl: false },
  th: { name: 'ไทย', englishName: 'Thai', rtl: false },

  // RTL languages
  ar: { name: 'العربية', englishName: 'Arabic', rtl: true },
  he: { name: 'עברית', englishName: 'Hebrew', rtl: true },
  fa: { name: 'فارسی', englishName: 'Persian', rtl: true },

  // Nordic languages
  sv: { name: 'Svenska', englishName: 'Swedish', rtl: false },
  no: { name: 'Norsk', englishName: 'Norwegian', rtl: false },
  da: { name: 'Dansk', englishName: 'Danish', rtl: false },
  fi: { name: 'Suomi', englishName: 'Finnish', rtl: false },

  // Other European languages
  cs: { name: 'Čeština', englishName: 'Czech', rtl: false },
  sk: { name: 'Slovenčina', englishName: 'Slovak', rtl: false },
  hu: { name: 'Magyar', englishName: 'Hungarian', rtl: false },
  ro: { name: 'Română', englishName: 'Romanian', rtl: false },
  bg: { name: 'Български', englishName: 'Bulgarian', rtl: false },
  el: { name: 'Ελληνικά', englishName: 'Greek', rtl: false },
  tr: { name: 'Türkçe', englishName: 'Turkish', rtl: false },
} as const;

/**
 * Validate if a string is a valid ISO 639-1 language code.
 */
export function validateLanguageCode(code: string): boolean {
  if (!code || typeof code !== 'string') return false;
  return code.toLowerCase() in ISO_639_1;
}

/**
 * Get language info for a code, with fallback for unknown codes.
 */
export function getLanguageInfo(code: string): LanguageInfo {
  const info = ISO_639_1[code.toLowerCase()];
  if (info) return info;

  // Fallback for unknown codes
  return {
    name: code.toUpperCase(),
    englishName: code.toUpperCase(),
    rtl: false,
  };
}

/**
 * Check if a language code represents an RTL language.
 */
export function isRtlLanguage(code: string): boolean {
  return getLanguageInfo(code).rtl;
}

/**
 * Detect which required languages are missing translations.
 */
export function detectMissingLanguages(
  value: Record<string, string> | undefined | null,
  requiredLanguages: string[]
): string[] {
  if (!value) return requiredLanguages;
  return requiredLanguages.filter((lang) => {
    const translation = value[lang];
    return !translation || translation.trim().length === 0;
  });
}

/**
 * Count how many languages have translations.
 */
export function countFilledLanguages(
  value: Record<string, string> | undefined | null,
  languages: string[]
): number {
  if (!value) return 0;
  return languages.filter((lang) => {
    const translation = value[lang];
    return translation && translation.trim().length > 0;
  }).length;
}

/**
 * Sanitize Unicode text for safe storage.
 *
 * - Removes BOM (Byte Order Mark)
 * - Normalizes to NFC form
 * - Trims whitespace
 */
export function sanitizeUnicode(text: string): string {
  if (!text) return '';

  // Remove BOM (U+FEFF)
  let sanitized = text.replace(/^\uFEFF/, '');

  // Normalize to NFC (composed form)
  sanitized = sanitized.normalize('NFC');

  // Trim whitespace
  sanitized = sanitized.trim();

  return sanitized;
}

/**
 * Check if text contains potentially problematic Unicode.
 */
export function hasProblematicUnicode(text: string): boolean {
  if (!text) return false;

  // Check for BOM
  if (text.charCodeAt(0) === 0xfeff) return true;

  // Check for zero-width characters
  if (/[\u200B-\u200F\u202A-\u202E\uFEFF]/.test(text)) return true;

  // Check if normalization would change the text
  if (text !== text.normalize('NFC')) return true;

  return false;
}

/**
 * Get display label for a language code.
 */
export function getLanguageLabel(code: string, useNative = true): string {
  const info = getLanguageInfo(code);
  return useNative ? info.name : info.englishName;
}

/**
 * Sort language codes with common languages first.
 */
export function sortLanguageCodes(codes: string[]): string[] {
  const priority = ['en', 'de', 'fr', 'es', 'it', 'zh', 'ja'];
  return [...codes].sort((a, b) => {
    const aIndex = priority.indexOf(a.toLowerCase());
    const bIndex = priority.indexOf(b.toLowerCase());

    if (aIndex !== -1 && bIndex !== -1) return aIndex - bIndex;
    if (aIndex !== -1) return -1;
    if (bIndex !== -1) return 1;

    return a.localeCompare(b);
  });
}
