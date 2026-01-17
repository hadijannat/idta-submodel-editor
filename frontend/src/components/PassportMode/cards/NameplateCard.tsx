/**
 * NameplateCard - IDTA 02006 Digital Nameplate visualization.
 *
 * Renders a metal sticker-style nameplate card with manufacturer info,
 * product details, serial numbers, and other identification data.
 */

import type { SubmodelUISchema } from '../../../types/ui-schema';
import type { SubmodelFormData } from '../../../types/aas-elements';
import {
  extractLangString,
  extractPrimitive,
  isProvided,
  formatValue,
} from '../utils/valueExtractors';

interface NameplateCardProps {
  schema: SubmodelUISchema; // Used for type consistency with other cards
  formData: SubmodelFormData | undefined;
}

// Note: schema is passed for API consistency but nameplate data is extracted from formData

/**
 * Field configuration for nameplate display.
 */
interface NameplateField {
  label: string;
  path: string;
  type: 'primitive' | 'langstring';
  fullWidth?: boolean;
  isSerial?: boolean;
}

/**
 * Key fields to extract from the Nameplate template.
 * These paths match the IDTA 02006 structure.
 */
const NAMEPLATE_FIELDS: NameplateField[] = [
  { label: 'Serial Number', path: 'elements.SerialNumber', type: 'primitive', fullWidth: true, isSerial: true },
  { label: 'Manufacturer Product Type', path: 'elements.ManufacturerProductType', type: 'primitive' },
  { label: 'Year of Construction', path: 'elements.YearOfConstruction', type: 'primitive' },
  { label: 'Country of Origin', path: 'elements.CountryOfOrigin', type: 'primitive' },
  { label: 'Order Code', path: 'elements.OrderCodeOfManufacturer', type: 'primitive' },
  { label: 'Batch Number', path: 'elements.BatchNumber', type: 'primitive' },
  { label: 'Product Article Number', path: 'elements.ProductArticleNumberOfManufacturer', type: 'primitive' },
  { label: 'Hardware Version', path: 'elements.HardwareVersion.value', type: 'primitive' },
  { label: 'Firmware Version', path: 'elements.FirmwareVersion.value', type: 'primitive' },
  { label: 'Software Version', path: 'elements.SoftwareVersion.value', type: 'primitive' },
];

/**
 * Extract the manufacturer name from various possible paths.
 */
function extractManufacturer(formData: SubmodelFormData | undefined): string | undefined {
  // Try different paths for manufacturer name
  const paths = [
    'elements.ManufacturerName',
    'elements.ManufacturerName.value',
    'elements.Manufacturer',
    'elements.Manufacturer.ManufacturerName',
  ];

  for (const path of paths) {
    const val = extractLangString(formData, path) ?? extractPrimitive(formData, path);
    if (isProvided(val)) {
      return String(val);
    }
  }

  return undefined;
}

/**
 * Extract the product designation from various possible paths.
 */
function extractProductDesignation(formData: SubmodelFormData | undefined): string | undefined {
  const paths = [
    'elements.ManufacturerProductDesignation',
    'elements.ManufacturerProductDesignation.value',
    'elements.ProductDesignation',
  ];

  for (const path of paths) {
    const val = extractLangString(formData, path) ?? extractPrimitive(formData, path);
    if (isProvided(val)) {
      return String(val);
    }
  }

  return undefined;
}

/**
 * Extract a field value based on its configuration.
 */
function extractFieldValue(
  field: NameplateField,
  formData: SubmodelFormData | undefined
): string | undefined {
  if (field.type === 'langstring') {
    return extractLangString(formData, field.path);
  }

  const val = extractPrimitive(formData, field.path) ?? extractPrimitive(formData, `${field.path}.value`);
  if (!isProvided(val)) return undefined;
  return formatValue(val);
}

/**
 * NameplateCard component.
 */
export default function NameplateCard({ schema: _schema, formData }: NameplateCardProps) {
  // _schema is available for future extensions (e.g., accessing semanticId)
  void _schema;
  const manufacturer = extractManufacturer(formData);
  const product = extractProductDesignation(formData);

  // Extract all configured fields
  const fields = NAMEPLATE_FIELDS.map((field) => ({
    ...field,
    value: extractFieldValue(field, formData),
  })).filter((f) => f.value !== undefined);

  const hasHeader = manufacturer || product;
  const hasFields = fields.length > 0;

  if (!hasHeader && !hasFields) {
    return (
      <div className="nameplate-card">
        <div className="nameplate-empty">
          <p>No nameplate data entered yet.</p>
          <p>Switch to Editor mode to fill in manufacturer and product information.</p>
        </div>
        <div className="nameplate-rivets-bottom" />
      </div>
    );
  }

  return (
    <div className="nameplate-card">
      {/* Header with manufacturer and product */}
      <div className="nameplate-header">
        {manufacturer && <h2 className="nameplate-manufacturer">{manufacturer}</h2>}
        {product && <p className="nameplate-product">{product}</p>}
      </div>

      {/* Fields grid */}
      {hasFields && (
        <div className="nameplate-grid">
          {fields.map((field, index) => (
            <div
              key={index}
              className={`nameplate-field ${field.fullWidth ? 'full-width' : ''}`}
            >
              <span className="nameplate-label">{field.label}</span>
              <span className={`nameplate-value ${field.isSerial ? 'nameplate-serial' : ''}`}>
                {field.value}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Footer rivets */}
      <div className="nameplate-rivets-bottom" />
    </div>
  );
}
