/**
 * MultiLangField component for rendering MultiLanguageProperty elements.
 *
 * Provides a tabbed interface for entering translations in multiple languages.
 * Features ISO 639-1 validation, translation gap indicators, and Unicode safety.
 */

import React, { useState, useCallback } from 'react';
import { useFormContext, Controller, useWatch } from 'react-hook-form';
import type { UIElementSchema } from '../../types/ui-schema';
import DescriptionText from './DescriptionText';
import SemanticChip from '../semantic/SemanticChip';
import SemanticLookupModal from '../semantic/SemanticLookupModal';
import {
  getLanguageLabel,
  getLanguageInfo,
  detectMissingLanguages,
  countFilledLanguages,
  sanitizeUnicode,
  hasProblematicUnicode,
  validateLanguageCode,
} from '../../utils/language-utils';

interface MultiLangFieldProps {
  /** Form path for the value object */
  path: string;
  /** Element schema */
  schema: UIElementSchema;
  /** Display label */
  label: string;
  /** Whether at least one translation is required */
  required: boolean;
  /** Languages considered required for translation completeness (default: ['en']) */
  requiredLanguages?: string[];
}

/**
 * Renders a tabbed interface for multi-language text input.
 * Features ISO 639-1 validation, translation gap indicators, and Unicode safety.
 */
export const MultiLangField: React.FC<MultiLangFieldProps> = ({
  path,
  schema,
  label,
  required,
  requiredLanguages = ['en'],
}) => {
  const { control, watch, setValue } = useFormContext();
  const languages = schema.supportedLanguages || ['en', 'de'];
  const [activeTab, setActiveTab] = useState(0);
  const [isSemanticOpen, setSemanticOpen] = useState(false);
  const basePath = path.replace(/\.value$/, '');
  const semanticId = useWatch({
    control,
    name: `${basePath}.semanticId`,
  }) as string | null | undefined;

  // Watch all language values to show indicators
  const values = watch(path) as Record<string, string> | undefined;

  // Count filled translations using utility
  const filledCount = countFilledLanguages(values, languages);

  // Detect missing required languages
  const missingLanguages = detectMissingLanguages(values, requiredLanguages);

  // Check if a language has a value
  const hasValue = useCallback(
    (lang: string) => {
      return values?.[lang] && values[lang].trim().length > 0;
    },
    [values]
  );

  // Check if text has Unicode issues
  const hasUnicodeIssue = useCallback(
    (lang: string) => {
      const text = values?.[lang];
      return text ? hasProblematicUnicode(text) : false;
    },
    [values]
  );

  // Handle text change with Unicode sanitization
  const handleTextChange = useCallback(
    (lang: string, text: string) => {
      // Sanitize Unicode on paste/input
      const sanitized = sanitizeUnicode(text);
      setValue(`${path}.${lang}`, sanitized, { shouldDirty: true });
    },
    [path, setValue]
  );

  // Get RTL direction for language
  const getTextDirection = useCallback((lang: string): 'ltr' | 'rtl' => {
    return getLanguageInfo(lang).rtl ? 'rtl' : 'ltr';
  }, []);

  return (
    <div className="aas-field aas-field-multilang">
      <div className="aas-multilang-header">
        <label className="aas-label">
          {label}
          {required && <span className="aas-required">*</span>}
        </label>
        <span className="aas-multilang-count">
          {filledCount}/{languages.length} translations
          {missingLanguages.length > 0 && required && (
            <span className="aas-multilang-missing" title={`Missing: ${missingLanguages.join(', ')}`}>
              (missing: {missingLanguages.join(', ')})
            </span>
          )}
        </span>
      </div>

      <div className="semantic-row">
        <span className="aas-sublabel">Semantic</span>
        <SemanticChip
          semanticId={semanticId}
          onOpen={() => setSemanticOpen(true)}
          onClear={() => setValue(`${basePath}.semanticId`, null, { shouldDirty: true })}
        />
      </div>

      <DescriptionText description={schema.description} />

      <div className="aas-multilang-tabs" role="tablist">
        {languages.map((lang, index) => {
          const isValidCode = validateLanguageCode(lang);
          const langInfo = getLanguageInfo(lang);

          return (
            <button
              key={lang}
              type="button"
              role="tab"
              aria-selected={activeTab === index}
              aria-controls={`${path}-panel-${lang}`}
              className={`aas-tab ${activeTab === index ? 'active' : ''} ${hasValue(lang) ? 'has-value' : ''} ${!isValidCode ? 'invalid-code' : ''}`}
              onClick={() => setActiveTab(index)}
              title={isValidCode ? langInfo.englishName : `Unknown language code: ${lang}`}
            >
              {getLanguageLabel(lang)}
              {hasValue(lang) && <span className="aas-tab-indicator">●</span>}
              {hasUnicodeIssue(lang) && (
                <span className="aas-tab-warning" title="Text contains problematic Unicode">⚠</span>
              )}
            </button>
          );
        })}
      </div>

      <div className="aas-multilang-panels">
        {languages.map((lang, index) => {
          const langInfo = getLanguageInfo(lang);
          const textDirection = getTextDirection(lang);

          return (
            <div
              key={lang}
              id={`${path}-panel-${lang}`}
              role="tabpanel"
              aria-labelledby={`${path}-tab-${lang}`}
              hidden={activeTab !== index}
              className="aas-multilang-panel"
            >
              <Controller
                name={`${path}.${lang}`}
                control={control}
                defaultValue={(schema.value as Record<string, string>)?.[lang] || ''}
                rules={{
                  required:
                    required && requiredLanguages.includes(lang)
                      ? `${label} (${langInfo.englishName}) is required`
                      : false,
                }}
                render={({ field, fieldState }) => (
                  <>
                    <textarea
                      {...field}
                      rows={3}
                      dir={textDirection}
                      placeholder={`Enter ${label} in ${langInfo.englishName}`}
                      className={`aas-input aas-textarea ${fieldState.error ? 'aas-input-error' : ''}`}
                      aria-label={`${label} in ${langInfo.englishName}`}
                      onChange={(e) => {
                        field.onChange(e);
                        // Auto-sanitize on change
                        if (hasProblematicUnicode(e.target.value)) {
                          handleTextChange(lang, e.target.value);
                        }
                      }}
                    />
                    {fieldState.error && (
                      <span className="aas-error-message">
                        {fieldState.error.message}
                      </span>
                    )}
                    {hasUnicodeIssue(lang) && (
                      <span className="aas-warning-message">
                        Text contains problematic Unicode characters that will be sanitized on save
                      </span>
                    )}
                  </>
                )}
              />
            </div>
          );
        })}
      </div>

      <SemanticLookupModal
        isOpen={isSemanticOpen}
        onClose={() => setSemanticOpen(false)}
        onApply={(value) =>
          setValue(`${basePath}.semanticId`, value, { shouldDirty: true })
        }
        currentSemanticId={semanticId ?? undefined}
        elementType={schema.modelType}
        valueType={schema.valueType}
        defaultKind="property"
      />
    </div>
  );
};

export default MultiLangField;
