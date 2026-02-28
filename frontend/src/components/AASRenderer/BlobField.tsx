/**
 * BlobField component for rendering editable Blob elements.
 */

import React, { useState } from 'react';
import { Controller, useFormContext } from 'react-hook-form';
import type { UIElementSchema } from '../../types/ui-schema';
import DescriptionText from './DescriptionText';

interface BlobFieldProps {
  /** Form path for the blob element */
  path: string;
  /** Element schema */
  schema: UIElementSchema;
  /** Display label */
  label: string;
  /** Whether the field is required */
  required: boolean;
}

const MAX_BLOB_SIZE_BYTES = 5 * 1024 * 1024;

function decodeBlobValue(value: string): Uint8Array {
  if (value.startsWith('base64:')) {
    const payload = value.slice('base64:'.length);
    const binary = window.atob(payload);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return bytes;
  }
  return new TextEncoder().encode(value);
}

function isTextLikeMime(contentType: string | null | undefined): boolean {
  if (!contentType) return false;
  return (
    contentType.startsWith('text/') ||
    contentType.includes('json') ||
    contentType.includes('xml') ||
    contentType.includes('yaml')
  );
}

export const BlobField: React.FC<BlobFieldProps> = ({
  path,
  schema,
  label,
  required,
}) => {
  const { control, setValue, getValues } = useFormContext();
  const [uploadError, setUploadError] = useState<string | null>(null);

  const handleUpload = async (
    event: React.ChangeEvent<HTMLInputElement>
  ): Promise<void> => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (file.size > MAX_BLOB_SIZE_BYTES) {
      setUploadError('Blob file exceeds 5 MB limit.');
      event.target.value = '';
      return;
    }

    setUploadError(null);
    setValue(`${path}.contentType`, file.type || 'application/octet-stream', {
      shouldDirty: true,
    });

    const textMode = isTextLikeMime(file.type);
    const reader = new FileReader();
    const completed = new Promise<void>((resolve, reject) => {
      reader.onerror = () => reject(reader.error);
      reader.onload = () => {
        if (textMode) {
          setValue(`${path}.value`, String(reader.result ?? ''), { shouldDirty: true });
          setValue(`${path}.valueEncoding`, 'utf-8', { shouldDirty: true });
        } else {
          const dataUrl = String(reader.result ?? '');
          const base64 = dataUrl.includes(',') ? dataUrl.split(',')[1] : '';
          setValue(`${path}.value`, `base64:${base64}`, { shouldDirty: true });
          setValue(`${path}.valueEncoding`, 'base64', { shouldDirty: true });
        }
        resolve();
      };
    });

    if (textMode) {
      reader.readAsText(file);
    } else {
      reader.readAsDataURL(file);
    }

    try {
      await completed;
    } catch {
      setUploadError('Failed to read uploaded blob file.');
    } finally {
      event.target.value = '';
    }
  };

  const handleDownload = (): void => {
    const value = String(getValues(`${path}.value`) ?? '');
    if (!value) return;

    const contentType = String(getValues(`${path}.contentType`) || 'application/octet-stream');
    const bytes = decodeBlobValue(value);
    const normalizedBytes = Uint8Array.from(bytes);
    const blob = new Blob([normalizedBytes], { type: contentType });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${schema.idShort || 'blob'}.bin`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  };

  return (
    <div className="aas-field aas-field-blob">
      <label className="aas-label" htmlFor={`${path}.value`}>
        {label}
        {required && <span className="aas-required">*</span>}
      </label>
      <DescriptionText description={schema.description} />

      <div className="aas-file-fields">
        <div className="aas-file-content-type">
          <label className="aas-sublabel" htmlFor={`${path}.contentType`}>
            Content Type
          </label>
          <Controller
            name={`${path}.contentType`}
            control={control}
            defaultValue={schema.contentType ?? 'application/octet-stream'}
            render={({ field }) => (
              <input {...field} id={`${path}.contentType`} type="text" className="aas-input" />
            )}
          />
        </div>

        <div className="aas-file-path">
          <label className="aas-sublabel" htmlFor={`${path}.upload`}>
            Upload Binary Payload
          </label>
          <input
            id={`${path}.upload`}
            type="file"
            className="aas-input"
            onChange={(event) => {
              void handleUpload(event);
            }}
          />
        </div>
      </div>

      <Controller
        name={`${path}.value`}
        control={control}
        defaultValue={schema.value ?? ''}
        rules={{ required: required ? `${label} is required` : false }}
        render={({ field, fieldState }) => (
          <>
            <textarea
              {...field}
              id={`${path}.value`}
              rows={4}
              className={`aas-input aas-textarea ${fieldState.error ? 'aas-input-error' : ''}`}
              placeholder="Blob payload text or base64:..."
            />
            {fieldState.error && (
              <span className="aas-error-message">{fieldState.error.message}</span>
            )}
          </>
        )}
      />

      {uploadError && <span className="aas-error-message">{uploadError}</span>}

      <div className="aas-blob-actions">
        <button type="button" className="btn btn-secondary" onClick={handleDownload}>
          Download blob payload
        </button>
      </div>

      <p className="aas-help-text">
        Upload a file or paste blob payload text. Binary data should use the
        `base64:` prefix.
      </p>
    </div>
  );
};

export default BlobField;
