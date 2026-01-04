/**
 * FileField component for rendering File elements.
 *
 * Allows users to specify file path/URL and content type.
 */

import React from 'react';
import { useFormContext, Controller } from 'react-hook-form';
import type { UIElementSchema } from '../../types/ui-schema';
import DescriptionText from './DescriptionText';

interface FileFieldProps {
  /** Form path for the file element */
  path: string;
  /** Element schema */
  schema: UIElementSchema;
  /** Display label */
  label: string;
  /** Whether the field is required */
  required: boolean;
}

/**
 * Common MIME types for suggestions.
 */
const COMMON_MIME_TYPES = [
  'application/pdf',
  'application/json',
  'application/xml',
  'image/png',
  'image/jpeg',
  'image/svg+xml',
  'text/plain',
  'text/csv',
  'application/octet-stream',
];

/**
 * Renders fields for File element (path/URL and content type).
 */
export const FileField: React.FC<FileFieldProps> = ({
  path,
  schema,
  label,
  required,
}) => {
  const { control } = useFormContext();

  return (
    <div className="aas-field aas-field-file">
      <label className="aas-label">
        {label}
        {required && <span className="aas-required">*</span>}
      </label>

      <DescriptionText description={schema.description} />

      <div className="aas-file-fields">
        <div className="aas-file-path">
          <label className="aas-sublabel" htmlFor={`${path}.value`}>
            File Path / URL
          </label>
          <Controller
            name={`${path}.value`}
            control={control}
            defaultValue={schema.value ?? ''}
            rules={{
              required: required ? 'File path is required' : false,
            }}
            render={({ field, fieldState }) => (
              <>
                <input
                  {...field}
                  id={`${path}.value`}
                  type="text"
                  placeholder="e.g., /files/document.pdf or https://..."
                  className={`aas-input ${fieldState.error ? 'aas-input-error' : ''}`}
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

        <div className="aas-file-content-type">
          <label className="aas-sublabel" htmlFor={`${path}.contentType`}>
            Content Type
          </label>
          <Controller
            name={`${path}.contentType`}
            control={control}
            defaultValue={schema.contentType ?? ''}
            render={({ field }) => (
              <>
                <input
                  {...field}
                  id={`${path}.contentType`}
                  type="text"
                  list={`${path}-mime-types`}
                  placeholder="e.g., application/pdf"
                  className="aas-input"
                />
                <datalist id={`${path}-mime-types`}>
                  {COMMON_MIME_TYPES.map((type) => (
                    <option key={type} value={type} />
                  ))}
                </datalist>
              </>
            )}
          />
        </div>
      </div>

      <p className="aas-help-text">
        Specify the path or URL to the file and its MIME content type.
      </p>
    </div>
  );
};

export default FileField;
