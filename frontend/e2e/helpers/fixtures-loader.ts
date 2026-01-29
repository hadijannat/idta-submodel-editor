/**
 * Fixture loading utilities for E2E tests.
 *
 * Loads test fixtures from:
 * - backend/tests/fixtures/ (AASX, JSON, CSV files from backend tests)
 * - e2e-fixtures/ (E2E-specific test data)
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

// ESM-compatible __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ============================================================================
// Types
// ============================================================================

export interface FormDataFixture {
  templateName: string;
  values: Record<string, unknown>;
  description?: string;
}

export interface CSVFixture {
  filename: string;
  content: string;
  expectedProfile?: {
    columns: string[];
    rowCount: number;
  };
}

export interface AASXFixture {
  filename: string;
  content: Buffer;
  templateName?: string;
}

export interface PDFFixture {
  filename: string;
  content: Buffer;
  expectedExtractions?: {
    fieldPath: string;
    expectedValue?: string;
    minConfidence?: number;
  }[];
}

export interface PolicyFixture {
  name: string;
  config: Record<string, unknown>;
  expectedOdrl: Record<string, unknown>;
}

// ============================================================================
// Path Resolution
// ============================================================================

const PROJECT_ROOT = path.resolve(__dirname, '../../../..');
const BACKEND_FIXTURES = path.join(PROJECT_ROOT, 'backend/tests/fixtures');
const E2E_FIXTURES = path.join(PROJECT_ROOT, 'e2e-fixtures');

/**
 * Resolves a fixture path, checking both e2e-fixtures and backend fixtures.
 */
export function resolveFixturePath(relativePath: string): string {
  // First check e2e-fixtures
  const e2ePath = path.join(E2E_FIXTURES, relativePath);
  if (fs.existsSync(e2ePath)) {
    return e2ePath;
  }

  // Then check backend fixtures
  const backendPath = path.join(BACKEND_FIXTURES, relativePath);
  if (fs.existsSync(backendPath)) {
    return backendPath;
  }

  throw new Error(
    `Fixture not found: ${relativePath}\n` +
      `Searched in:\n  - ${e2ePath}\n  - ${backendPath}`
  );
}

// ============================================================================
// Loaders
// ============================================================================

/**
 * Load a JSON fixture file.
 */
export function loadJsonFixture<T = unknown>(relativePath: string): T {
  const fullPath = resolveFixturePath(relativePath);
  const content = fs.readFileSync(fullPath, 'utf-8');
  return JSON.parse(content) as T;
}

/**
 * Load form data fixture by name.
 */
export function loadFormDataFixture(name: string): FormDataFixture {
  return loadJsonFixture<FormDataFixture>(`json/${name}.json`);
}

/**
 * Load a CSV fixture.
 */
export function loadCsvFixture(filename: string): CSVFixture {
  const fullPath = resolveFixturePath(`csv/${filename}`);
  const content = fs.readFileSync(fullPath, 'utf-8');

  // Parse basic profile info
  const lines = content.trim().split('\n');
  const columns = lines[0].split(',').map((col) => col.trim().replace(/^"|"$/g, ''));

  return {
    filename,
    content,
    expectedProfile: {
      columns,
      rowCount: lines.length - 1, // Exclude header
    },
  };
}

/**
 * Load a CSV fixture as a Buffer (for file uploads).
 */
export function loadCsvBuffer(filename: string): Buffer {
  const fullPath = resolveFixturePath(`csv/${filename}`);
  return fs.readFileSync(fullPath);
}

/**
 * Load an XLSX fixture as a Buffer.
 */
export function loadXlsxBuffer(filename: string): Buffer {
  const fullPath = resolveFixturePath(`xlsx/${filename}`);
  return fs.readFileSync(fullPath);
}

/**
 * Load an AASX fixture.
 */
export function loadAasxFixture(filename: string): AASXFixture {
  const fullPath = resolveFixturePath(`aasx/${filename}`);
  const content = fs.readFileSync(fullPath);

  // Extract template name from filename if not provided
  const templateName = filename.replace('.aasx', '').replace(/-/g, ' ');

  return {
    filename,
    content,
    templateName,
  };
}

/**
 * Load a PDF fixture.
 */
export function loadPdfFixture(filename: string): PDFFixture {
  const fullPath = resolveFixturePath(`pdf/${filename}`);
  const content = fs.readFileSync(fullPath);

  // Try to load expected extractions if they exist
  let expectedExtractions: PDFFixture['expectedExtractions'];
  try {
    const expectationsPath = fullPath.replace('.pdf', '_expected.json');
    if (fs.existsSync(expectationsPath)) {
      expectedExtractions = JSON.parse(fs.readFileSync(expectationsPath, 'utf-8'));
    }
  } catch {
    // No expected extractions file
  }

  return {
    filename,
    content,
    expectedExtractions,
  };
}

/**
 * Load a policy fixture.
 */
export function loadPolicyFixture(name: string): PolicyFixture {
  return loadJsonFixture<PolicyFixture>(`json/policies/${name}.json`);
}

// ============================================================================
// Fixture Discovery
// ============================================================================

/**
 * List all available fixtures of a given type.
 */
export function listFixtures(type: 'aasx' | 'json' | 'csv' | 'xlsx' | 'pdf'): string[] {
  const results: string[] = [];

  // Check e2e-fixtures
  const e2eDir = path.join(E2E_FIXTURES, type);
  if (fs.existsSync(e2eDir)) {
    results.push(
      ...fs
        .readdirSync(e2eDir)
        .filter((f) => !f.startsWith('.'))
        .map((f) => path.join(type, f))
    );
  }

  // Check backend fixtures
  const backendDir = path.join(BACKEND_FIXTURES, type);
  if (fs.existsSync(backendDir)) {
    results.push(
      ...fs
        .readdirSync(backendDir)
        .filter((f) => !f.startsWith('.') && !results.includes(path.join(type, f)))
        .map((f) => path.join(type, f))
    );
  }

  return results;
}

// ============================================================================
// Test Data Generation
// ============================================================================

/**
 * Generate minimal valid form data for a template schema.
 * Fills only required fields with placeholder values.
 */
export function generateMinimalFormData(
  schema: { elements: { idShort: string; modelType: string; cardinality?: string; valueType?: string; elements?: unknown[] }[] }
): Record<string, unknown> {
  const result: Record<string, unknown> = {};

  for (const element of schema.elements) {
    const isRequired = !element.cardinality?.startsWith('[0');

    if (!isRequired) continue;

    switch (element.modelType) {
      case 'Property':
        result[element.idShort] = generatePlaceholderValue(element.valueType);
        break;
      case 'MultiLanguageProperty':
        result[element.idShort] = { en: 'Test Value' };
        break;
      case 'File':
        result[element.idShort] = { path: 'https://example.com/file.pdf', contentType: 'application/pdf' };
        break;
      case 'Range':
        result[element.idShort] = { min: '0', max: '100' };
        break;
      case 'SubmodelElementCollection':
        if (element.elements) {
          result[element.idShort] = generateMinimalFormData({
            elements: element.elements as typeof schema.elements,
          });
        }
        break;
      case 'SubmodelElementList':
        // Lists typically need at least one item if required
        result[element.idShort] = [];
        break;
    }
  }

  return result;
}

/**
 * Generate a placeholder value based on AAS value type.
 */
function generatePlaceholderValue(valueType?: string): string {
  switch (valueType) {
    case 'xs:string':
      return 'Test String';
    case 'xs:integer':
    case 'xs:int':
    case 'xs:long':
      return '42';
    case 'xs:decimal':
    case 'xs:double':
    case 'xs:float':
      return '3.14';
    case 'xs:boolean':
      return 'true';
    case 'xs:date':
      return '2024-01-15';
    case 'xs:dateTime':
      return '2024-01-15T12:00:00Z';
    case 'xs:anyURI':
      return 'https://example.com';
    default:
      return 'Test Value';
  }
}

/**
 * Generate complete valid form data for testing exports.
 * Fills all fields with realistic test values.
 */
export function generateCompleteFormData(
  schema: { elements: { idShort: string; modelType: string; valueType?: string; elements?: unknown[] }[] },
  overrides?: Record<string, unknown>
): Record<string, unknown> {
  const result: Record<string, unknown> = {};

  for (const element of schema.elements) {
    switch (element.modelType) {
      case 'Property':
        result[element.idShort] = generatePlaceholderValue(element.valueType);
        break;
      case 'MultiLanguageProperty':
        result[element.idShort] = {
          en: `${element.idShort} (English)`,
          de: `${element.idShort} (German)`,
        };
        break;
      case 'File':
        result[element.idShort] = {
          path: `https://example.com/${element.idShort.toLowerCase()}.pdf`,
          contentType: 'application/pdf',
        };
        break;
      case 'Range':
        result[element.idShort] = { min: '0', max: '100' };
        break;
      case 'SubmodelElementCollection':
        if (element.elements) {
          result[element.idShort] = generateCompleteFormData({
            elements: element.elements as typeof schema.elements,
          });
        }
        break;
      case 'SubmodelElementList':
        result[element.idShort] = [];
        break;
      case 'ReferenceElement':
        result[element.idShort] = {
          keys: [{ type: 'GlobalReference', value: 'https://example.com/reference' }],
        };
        break;
    }
  }

  // Apply overrides
  if (overrides) {
    Object.assign(result, overrides);
  }

  return result;
}

// ============================================================================
// Fixture Validation
// ============================================================================

/**
 * Check if all expected fixtures exist.
 * Useful for test setup validation.
 */
export function validateFixturesExist(fixtures: string[]): { valid: boolean; missing: string[] } {
  const missing: string[] = [];

  for (const fixture of fixtures) {
    try {
      resolveFixturePath(fixture);
    } catch {
      missing.push(fixture);
    }
  }

  return {
    valid: missing.length === 0,
    missing,
  };
}
