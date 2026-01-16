import { API_BASE_URL, ApiError } from './api';
import type { DatasetProfile, MapperRunRequest, MapperRunResponse } from '../types/mapper';

export async function profileMapperFile(
  file: File,
  options: { sheet?: string; headerRow?: number; sampleRows?: number } = {}
): Promise<DatasetProfile> {
  const form = new FormData();
  form.append('file', file);
  if (options.sheet) form.append('sheet', options.sheet);
  if (options.headerRow) form.append('header_row', String(options.headerRow));
  if (options.sampleRows) form.append('sample_rows', String(options.sampleRows));

  const response = await fetch(`${API_BASE_URL}/api/mapper/profile`, {
    method: 'POST',
    body: form,
  });

  if (!response.ok) {
    let details: unknown;
    try {
      details = await response.json();
    } catch {
      details = await response.text();
    }
    throw new ApiError('Profile failed', response.status, details);
  }

  return response.json();
}

export async function runMapper(
  payload: MapperRunRequest
): Promise<MapperRunResponse> {
  const response = await fetch(`${API_BASE_URL}/api/mapper/run`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let details: unknown;
    try {
      details = await response.json();
    } catch {
      details = await response.text();
    }
    throw new ApiError('Mapper run failed', response.status, details);
  }

  return response.json();
}
