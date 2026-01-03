/**
 * MultiLangField component for rendering MultiLanguageProperty elements.
 *
 * Provides a tabbed interface for entering translations in multiple languages.
 */

import React, { useState } from 'react';
import { useFormContext, Controller } from 'react-hook-form';
import type { UIElementSchema } from '../../types/ui-schema';
import { SUPPORTED_LANGUAGES } from '../../types/aas-elements';

interface MultiLangFieldProps {
  /** Form path for the value object */
  path: string;
  /** Element schema */
  schema: UIElementSchema;
  /** Display label */
  label: string;
  /** Whether at least one translation is required */
  required: boolean;
}

/**
 * Language labels for display.
 */
const LANGUAGE_LABELS: Record<string, string> = {
  en: 'English',
  de: 'Deutsch',
  fr: 'Français',
  es: 'Español',
  it: 'Italiano',
  zh: '中文',
  ja: '日本語',
  ko: '한국어',
  pt: 'Português',
};

/**
 * Renders a tabbed interface for multi-language text input.
 */
export const MultiLangField: React.FC<MultiLangFieldProps> = ({
  path,
  schema,
  label,
  required,
}) => {
  const { control, watch } = useFormContext();
  const languages = schema.supportedLanguages || ['en', 'de'];
  const [activeTab, setActiveTab] = useState(0);

  // Watch all language values to show indicators
  const values = watch(path) as Record<string, string> | undefined;

  const hasValue = (lang: string) => {
    return values?.[lang] && values[lang].trim().length > 0;
  };

  const filledCount = languages.filter(hasValue).length;

  return (
    <div className="aas-field aas-field-multilang">
      <div className="aas-multilang-header">
        <label className="aas-label">
          {label}
          {required && <span className="aas-required">*</span>}
        </label>
        <span className="aas-multilang-count">
          {filledCount}/{languages.length} translations
        </span>
      </div>

      {schema.description?.en && (
        <p className="aas-description">{schema.description.en}</p>
      )}

      <div className="aas-multilang-tabs" role="tablist">
        {languages.map((lang, index) => (
          <button
            key={lang}
            type="button"
            role="tab"
            aria-selected={activeTab === index}
            aria-controls={`${path}-panel-${lang}`}
            className={`aas-tab ${activeTab === index ? 'active' : ''} ${hasValue(lang) ? 'has-value' : ''}`}
            onClick={() => setActiveTab(index)}
          >
            {LANGUAGE_LABELS[lang] || lang}
            {hasValue(lang) && <span className="aas-tab-indicator">●</span>}
          </button>
        ))}
      </div>

      <div className="aas-multilang-panels">
        {languages.map((lang, index) => (
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
                  required && lang === 'en'
                    ? `${label} (English) is required`
                    : false,
              }}
              render={({ field, fieldState }) => (
                <>
                  <textarea
                    {...field}
                    rows={3}
                    placeholder={`Enter ${label} in ${LANGUAGE_LABELS[lang] || lang}`}
                    className={`aas-input aas-textarea ${fieldState.error ? 'aas-input-error' : ''}`}
                    aria-label={`${label} in ${LANGUAGE_LABELS[lang] || lang}`}
                  />
                  {fieldState.error && (
                    <span className="aas-error-message">
                      {fieldState.error.message}
                    </span>
                  )}
                </>
              )}
            />
          </div>
        ))}
      </div>
    </div>
  );
};

export default MultiLangField;
