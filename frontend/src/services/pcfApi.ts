/**
 * API client for PCF (Product Carbon Footprint) Calculator & Validator.
 */

import { API_BASE_URL, ApiError } from './api';
import type {
  EmissionFactor,
  PCFCalculateRequest,
  PCFCalculateResponse,
  PCFValidateRequest,
  PCFValidateResponse,
  PCFHealthResponse,
} from '../types/pcf';

/**
 * Calculate CO2e emissions from activity data.
 */
export async function calculatePCF(
  request: PCFCalculateRequest
): Promise<PCFCalculateResponse> {
  const response = await fetch(`${API_BASE_URL}/api/pcf/calculate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    let details: unknown;
    try {
      details = await response.json();
    } catch {
      details = await response.text();
    }
    throw new ApiError('PCF calculation failed', response.status, details);
  }

  return response.json();
}

/**
 * Validate PCF form data against IDTA 02023 rules.
 */
export async function validatePCF(
  request: PCFValidateRequest
): Promise<PCFValidateResponse> {
  const response = await fetch(`${API_BASE_URL}/api/pcf/validate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    let details: unknown;
    try {
      details = await response.json();
    } catch {
      details = await response.text();
    }
    throw new ApiError('PCF validation failed', response.status, details);
  }

  return response.json();
}

/**
 * Check PCF service health status.
 */
export async function checkPCFHealth(): Promise<PCFHealthResponse> {
  const response = await fetch(`${API_BASE_URL}/api/pcf/health`);

  if (!response.ok) {
    throw new ApiError('PCF health check failed', response.status);
  }

  return response.json();
}

/**
 * Search emission factors by name, source, or region.
 */
export async function searchEmissionFactors(
  query: string = '',
  limit: number = 20
): Promise<EmissionFactor[]> {
  const params = new URLSearchParams();
  params.set('query', query);
  params.set('limit', limit.toString());

  const response = await fetch(
    `${API_BASE_URL}/api/pcf/factors/search?${params.toString()}`
  );

  if (!response.ok) {
    throw new ApiError('Emission factors search failed', response.status);
  }

  return response.json();
}

/**
 * Get an emission factor by its ID.
 */
export async function getEmissionFactorById(
  factorId: string
): Promise<EmissionFactor | null> {
  const response = await fetch(`${API_BASE_URL}/api/pcf/factors/${factorId}`);

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    throw new ApiError('Failed to get emission factor', response.status);
  }

  return response.json();
}
