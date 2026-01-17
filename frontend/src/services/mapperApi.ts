import { API_BASE_URL, ApiError } from './api';
import type {
  DatasetProfile,
  MapperAutoSuggestRequest,
  MapperAutoSuggestResponse,
  MapperRecipe,
  MapperRunRequest,
  MapperRunResponse,
} from '../types/mapper';

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

export async function listMapperRecipes(): Promise<MapperRecipe[]> {
  const response = await fetch(`${API_BASE_URL}/api/mapper/recipes`);

  if (!response.ok) {
    let details: unknown;
    try {
      details = await response.json();
    } catch {
      details = await response.text();
    }
    throw new ApiError('Load recipes failed', response.status, details);
  }

  const data = (await response.json()) as { recipes?: MapperRecipe[] };
  return data.recipes ?? [];
}

export async function saveMapperRecipe(recipe: MapperRecipe): Promise<MapperRecipe> {
  const response = await fetch(`${API_BASE_URL}/api/mapper/recipes`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(recipe),
  });

  if (!response.ok) {
    let details: unknown;
    try {
      details = await response.json();
    } catch {
      details = await response.text();
    }
    throw new ApiError('Save recipe failed', response.status, details);
  }

  return response.json();
}

export async function deleteMapperRecipe(name: string): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/mapper/recipes/${encodeURIComponent(name)}`,
    {
      method: 'DELETE',
    }
  );

  if (!response.ok) {
    let details: unknown;
    try {
      details = await response.json();
    } catch {
      details = await response.text();
    }
    throw new ApiError('Delete recipe failed', response.status, details);
  }
}

export async function autoSuggestMappings(
  payload: MapperAutoSuggestRequest
): Promise<MapperAutoSuggestResponse> {
  const response = await fetch(`${API_BASE_URL}/api/mapper/auto-suggest`, {
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
    throw new ApiError('Auto-suggest failed', response.status, details);
  }

  return response.json();
}
