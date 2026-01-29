/**
 * Test data factory for generating form data for E2E tests.
 *
 * Provides functions to generate valid and invalid test data
 * for various template types.
 */

// ============================================================================
// Types
// ============================================================================

export interface NameplateFormData {
  URIOfTheProduct?: string;
  ManufacturerName?: Record<string, string>;
  ManufacturerProductDesignation?: Record<string, string>;
  ContactInformation?: {
    NationalCode?: Record<string, string>;
    CityTown?: Record<string, string>;
    Street?: Record<string, string>;
    Zipcode?: Record<string, string>;
    Phone?: { CountryCode?: string; AreaCode?: string; Number?: string };
    Email?: { EmailAddress?: string };
  };
  ManufacturerProductFamily?: Record<string, string>;
  SerialNumber?: string;
  YearOfConstruction?: string;
  DateOfManufacture?: string;
  [key: string]: unknown;
}

export interface PCFFormData {
  PCFIdentifier?: string;
  PCFDeclaredUnit?: string;
  PCFQuantityOfDeclaredUnit?: string;
  PCFCO2eq?: string;
  PCFBiogenicCarbonContent?: string;
  PCFProductDescription?: Record<string, string>;
  PCFLifecyclePhases?: string;
  PCFGeographicScope?: string;
  PCFReferenceYear?: string;
  [key: string]: unknown;
}

export interface CarbonFootprintFormData {
  PCFCalculationMethod?: string;
  PCFCO2eqDistribution?: {
    PCFGoodsAddressHandover?: {
      PCFStreet?: string;
      PCFCity?: string;
      PCFCountry?: string;
    };
  };
  [key: string]: unknown;
}

// ============================================================================
// Digital Nameplate Data
// ============================================================================

/**
 * Generate valid Digital Nameplate form data.
 */
export function createNameplateFormData(
  overrides?: Partial<NameplateFormData>
): NameplateFormData {
  const baseData: NameplateFormData = {
    URIOfTheProduct: 'https://example.com/products/test-product-001',
    ManufacturerName: {
      en: 'Test Manufacturer Inc.',
      de: 'Test Hersteller GmbH',
    },
    ManufacturerProductDesignation: {
      en: 'Test Product Model X1',
      de: 'Testprodukt Modell X1',
    },
    ContactInformation: {
      NationalCode: { en: 'DE' },
      CityTown: { en: 'Berlin' },
      Street: { en: 'Test Street 123' },
      Zipcode: { en: '10115' },
      Phone: {
        CountryCode: '+49',
        AreaCode: '30',
        Number: '12345678',
      },
      Email: {
        EmailAddress: 'contact@test-manufacturer.com',
      },
    },
    ManufacturerProductFamily: {
      en: 'Industrial Sensors',
    },
    SerialNumber: 'SN-2024-001-TEST',
    YearOfConstruction: '2024',
    DateOfManufacture: '2024-01-15',
  };

  return { ...baseData, ...overrides };
}

/**
 * Generate minimal valid Digital Nameplate data (only required fields).
 */
export function createMinimalNameplateFormData(): NameplateFormData {
  return {
    URIOfTheProduct: 'https://example.com/products/minimal-001',
    ManufacturerName: { en: 'Minimal Manufacturer' },
  };
}

/**
 * Generate invalid Digital Nameplate data for validation testing.
 */
export function createInvalidNameplateFormData(
  invalidationType: 'missing-required' | 'invalid-uri' | 'invalid-date' | 'invalid-type'
): NameplateFormData {
  switch (invalidationType) {
    case 'missing-required':
      return {
        // Missing URIOfTheProduct and ManufacturerName
        SerialNumber: 'SN-001',
      };
    case 'invalid-uri':
      return {
        URIOfTheProduct: 'not-a-valid-uri',
        ManufacturerName: { en: 'Test' },
      };
    case 'invalid-date':
      return {
        URIOfTheProduct: 'https://example.com/products/001',
        ManufacturerName: { en: 'Test' },
        DateOfManufacture: 'invalid-date-format',
      };
    case 'invalid-type':
      return {
        URIOfTheProduct: 'https://example.com/products/001',
        ManufacturerName: 'should-be-object-not-string' as unknown as Record<string, string>,
      };
  }
}

// ============================================================================
// PCF / Carbon Footprint Data
// ============================================================================

/**
 * Generate valid PCF form data.
 */
export function createPCFFormData(overrides?: Partial<PCFFormData>): PCFFormData {
  const baseData: PCFFormData = {
    PCFIdentifier: 'PCF-2024-TEST-001',
    PCFDeclaredUnit: 'piece',
    PCFQuantityOfDeclaredUnit: '1',
    PCFCO2eq: '12.5',
    PCFBiogenicCarbonContent: '0.5',
    PCFProductDescription: {
      en: 'Test product carbon footprint declaration',
      de: 'CO2-Fußabdruck-Erklärung für Testprodukt',
    },
    PCFLifecyclePhases: 'A1-A3',
    PCFGeographicScope: 'DE',
    PCFReferenceYear: '2024',
  };

  return { ...baseData, ...overrides };
}

/**
 * Generate valid Carbon Footprint form data (IDTA 02023).
 */
export function createCarbonFootprintFormData(
  overrides?: Partial<CarbonFootprintFormData>
): CarbonFootprintFormData {
  const baseData: CarbonFootprintFormData = {
    PCFCalculationMethod: 'GHG Protocol',
    PCFCO2eqDistribution: {
      PCFGoodsAddressHandover: {
        PCFStreet: 'Industrial Way 42',
        PCFCity: 'Stuttgart',
        PCFCountry: 'DE',
      },
    },
    ...createPCFFormData(),
  };

  return { ...baseData, ...overrides };
}

/**
 * Generate invalid PCF data for validation testing.
 */
export function createInvalidPCFFormData(
  invalidationType: 'missing-required' | 'negative-co2' | 'invalid-lifecycle'
): PCFFormData {
  switch (invalidationType) {
    case 'missing-required':
      return {
        // Missing PCFIdentifier and PCFCO2eq
        PCFDeclaredUnit: 'piece',
      };
    case 'negative-co2':
      return {
        ...createPCFFormData(),
        PCFCO2eq: '-5.0', // Negative CO2 should be invalid
      };
    case 'invalid-lifecycle':
      return {
        ...createPCFFormData(),
        PCFLifecyclePhases: 'INVALID-PHASE',
      };
  }
}

// ============================================================================
// Generic Element Data
// ============================================================================

/**
 * Generate a string property value.
 */
export function createStringValue(prefix: string = 'Test'): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).substring(7)}`;
}

/**
 * Generate a multi-language property value.
 */
export function createMultiLangValue(
  value: string,
  languages: string[] = ['en', 'de']
): Record<string, string> {
  const result: Record<string, string> = {};
  for (const lang of languages) {
    result[lang] = `${value} (${lang.toUpperCase()})`;
  }
  return result;
}

/**
 * Generate a file property value.
 */
export function createFileValue(
  filename: string = 'document.pdf',
  contentType: string = 'application/pdf'
): { path: string; contentType: string } {
  return {
    path: `https://example.com/files/${filename}`,
    contentType,
  };
}

/**
 * Generate a range property value.
 */
export function createRangeValue(
  min: number = 0,
  max: number = 100
): { min: string; max: string } {
  return {
    min: min.toString(),
    max: max.toString(),
  };
}

/**
 * Generate a reference element value.
 */
export function createReferenceValue(
  uri: string = 'https://example.com/reference'
): { keys: { type: string; value: string }[] } {
  return {
    keys: [{ type: 'GlobalReference', value: uri }],
  };
}

/**
 * Generate a date value in ISO format.
 */
export function createDateValue(daysFromNow: number = 0): string {
  const date = new Date();
  date.setDate(date.getDate() + daysFromNow);
  return date.toISOString().split('T')[0];
}

/**
 * Generate a datetime value in ISO format.
 */
export function createDateTimeValue(hoursFromNow: number = 0): string {
  const date = new Date();
  date.setHours(date.getHours() + hoursFromNow);
  return date.toISOString();
}

// ============================================================================
// Smart Mapper Test Data
// ============================================================================

/**
 * Generate CSV content for Smart Mapper testing.
 */
export function createMapperCSV(options?: {
  columns?: string[];
  rowCount?: number;
  includeHeader?: boolean;
}): string {
  const columns = options?.columns ?? [
    'ProductName',
    'SerialNumber',
    'Manufacturer',
    'ManufactureDate',
  ];
  const rowCount = options?.rowCount ?? 5;
  const includeHeader = options?.includeHeader ?? true;

  const lines: string[] = [];

  if (includeHeader) {
    lines.push(columns.join(','));
  }

  for (let i = 0; i < rowCount; i++) {
    const row = columns.map((col) => {
      if (col.toLowerCase().includes('date')) {
        return createDateValue(-i);
      }
      if (col.toLowerCase().includes('serial')) {
        return `SN-${1000 + i}`;
      }
      return `${col}-Value-${i + 1}`;
    });
    lines.push(row.join(','));
  }

  return lines.join('\n');
}

// ============================================================================
// Dataspace / Policy Test Data
// ============================================================================

/**
 * Generate policy configuration for testing.
 */
export function createPolicyConfig(
  accessLevel: 'public' | 'membership' | 'restricted',
  options?: {
    allowedBPNs?: string[];
    contractDuration?: string;
  }
): object {
  const base = {
    access_level: accessLevel,
  };

  if (accessLevel === 'restricted' && options?.allowedBPNs) {
    return {
      ...base,
      allowed_bpns: options.allowedBPNs,
    };
  }

  if (options?.contractDuration) {
    return {
      ...base,
      contract_duration: options.contractDuration,
    };
  }

  return base;
}

/**
 * Generate a BPN (Business Partner Number) for testing.
 */
export function createTestBPN(index: number = 1): string {
  return `BPNL00000000${String(index).padStart(4, '0')}`;
}

// ============================================================================
// Collection / List Test Data
// ============================================================================

/**
 * Generate a collection element with nested data.
 */
export function createCollectionData(
  elements: Record<string, unknown>
): Record<string, unknown> {
  return elements;
}

/**
 * Generate a list element with multiple items.
 */
export function createListData<T>(
  itemCount: number,
  itemFactory: (index: number) => T
): T[] {
  return Array.from({ length: itemCount }, (_, i) => itemFactory(i));
}

// ============================================================================
// Form State Snapshots
// ============================================================================

/**
 * Create a complete form state snapshot for comparison.
 */
export function createFormStateSnapshot(
  templateName: string,
  formData: Record<string, unknown>,
  metadata?: {
    validationState?: 'valid' | 'invalid' | 'pending';
    dirtyFields?: string[];
  }
): {
  templateName: string;
  formData: Record<string, unknown>;
  timestamp: string;
  metadata?: object;
} {
  return {
    templateName,
    formData,
    timestamp: new Date().toISOString(),
    metadata,
  };
}
