/**
 * NameplateCard - IDTA 02006 Digital Nameplate visualization.
 *
 * Renders a metal sticker-style nameplate card with manufacturer info,
 * product details, serial numbers, and other identification data.
 */

import type { SubmodelUISchema } from '../../../types/ui-schema';
import type { SubmodelFormData } from '../../../types/aas-elements';
import {
  extractLangStringValue,
  extractPrimitiveValue,
  formatValue,
  isProvided,
} from '../utils/valueExtractors';
import {
  findMatchingElements,
  resolveSchemaElements,
} from '../utils/schemaIndex';

interface NameplateCardProps {
  schema: SubmodelUISchema; // Used for type consistency with other cards
  formData: SubmodelFormData | undefined;
}

// Note: schema is passed for API consistency but nameplate data is extracted from formData

/**
 * Field configuration for nameplate display.
 */
interface NameplateField {
  key: string;
  label: string;
  semanticIdPatterns?: RegExp[];
  idShortPatterns?: RegExp[];
  fullWidth?: boolean;
  isSerial?: boolean;
}

const NAMEPLATE_FIELDS: NameplateField[] = [
  {
    key: 'serial',
    label: 'Serial Number',
    semanticIdPatterns: [/0112\/2\/\/\/61987#ABA951#009/i],
    idShortPatterns: [/SerialNumber/i],
    fullWidth: true,
    isSerial: true,
  },
  {
    key: 'productType',
    label: 'Manufacturer Product Type',
    semanticIdPatterns: [/0112\/2\/\/\/61987#ABA300#008/i],
    idShortPatterns: [/ManufacturerProductType/i],
  },
  {
    key: 'year',
    label: 'Year of Construction',
    semanticIdPatterns: [/0112\/2\/\/\/61987#ABP000#002/i],
    idShortPatterns: [/YearOfConstruction/i],
  },
  {
    key: 'country',
    label: 'Country of Origin',
    semanticIdPatterns: [/0112\/2\/\/\/61987#ABP462#001/i],
    idShortPatterns: [/CountryOfOrigin/i],
  },
  {
    key: 'orderCode',
    label: 'Order Code',
    semanticIdPatterns: [/0112\/2\/\/\/61987#ABA950#008/i],
    idShortPatterns: [/OrderCodeOfManufacturer/i, /OrderCode/i],
  },
  {
    key: 'batch',
    label: 'Batch Number',
    idShortPatterns: [/BatchNumber/i],
  },
  {
    key: 'articleNumber',
    label: 'Product Article Number',
    semanticIdPatterns: [/0112\/2\/\/\/61987#ABA581#007/i],
    idShortPatterns: [/ProductArticleNumberOfManufacturer/i, /ProductArticleNumber/i],
  },
  {
    key: 'hardware',
    label: 'Hardware Version',
    semanticIdPatterns: [/0112\/2\/\/\/61987#ABA926#008/i],
    idShortPatterns: [/HardwareVersion/i],
  },
  {
    key: 'firmware',
    label: 'Firmware Version',
    semanticIdPatterns: [/0112\/2\/\/\/61987#ABA302#006/i],
    idShortPatterns: [/FirmwareVersion/i],
  },
  {
    key: 'software',
    label: 'Software Version',
    semanticIdPatterns: [/0112\/2\/\/\/61987#ABA601#008/i],
    idShortPatterns: [/SoftwareVersion/i],
  },
];

const MANUFACTURER_MATCH = {
  semanticIdPatterns: [/0112\/2\/\/\/61987#ABA565#009/i],
  idShortPatterns: [/ManufacturerName/i, /^Manufacturer$/i],
};

const PRODUCT_MATCH = {
  semanticIdPatterns: [/0112\/2\/\/\/61987#ABA567#009/i],
  idShortPatterns: [/ManufacturerProductDesignation/i, /ProductDesignation/i],
};

function getDisplayValue(
  element: ReturnType<typeof resolveSchemaElements>[number],
  preferredLangs: string[]
): string | undefined {
  if (!element.data) return undefined;
  switch (element.schema.modelType) {
    case 'MultiLanguageProperty': {
      const val = extractLangStringValue(element.data.value ?? element.data, preferredLangs);
      return isProvided(val) ? val : undefined;
    }
    case 'Property':
    case 'Range':
    case 'ReferenceElement':
    case 'File': {
      const primitive = extractPrimitiveValue(element.data);
      if (!isProvided(primitive)) return undefined;
      return formatValue(primitive);
    }
    default: {
      const primitive = extractPrimitiveValue(element.data);
      if (!isProvided(primitive)) return undefined;
      return formatValue(primitive);
    }
  }
}

function findFirstValue(
  elements: ReturnType<typeof resolveSchemaElements>,
  matcher: { semanticIdPatterns?: RegExp[]; idShortPatterns?: RegExp[] },
  preferredLangs: string[]
): string | undefined {
  const matches = findMatchingElements(elements, matcher);
  for (const match of matches) {
    const value = getDisplayValue(match, preferredLangs);
    if (isProvided(value)) {
      return value;
    }
  }
  return undefined;
}

function fnv1aHash(input: string): number {
  let hash = 0x811c9dc5;
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
}

function buildMarkerGradient(seed: string): string {
  const hash = fnv1aHash(seed);
  const bits = hash.toString(2).padStart(32, '0');
  const step = 100 / bits.length;
  const parts: string[] = [];

  bits.split('').forEach((bit, index) => {
    const start = index * step;
    const end = (index + 1) * step;
    const color = bit === '1' ? '#1f2937' : '#d1d5db';
    parts.push(`${color} ${start}% ${end}%`);
  });

  return `linear-gradient(90deg, ${parts.join(', ')})`;
}

/**
 * NameplateCard component.
 */
export default function NameplateCard({ schema, formData }: NameplateCardProps) {
  const resolvedElements = resolveSchemaElements(schema, formData);
  const preferredLangs = ['en', 'de'];

  const manufacturer = findFirstValue(resolvedElements, MANUFACTURER_MATCH, preferredLangs);
  const product = findFirstValue(resolvedElements, PRODUCT_MATCH, preferredLangs);

  const fields = NAMEPLATE_FIELDS.map((field) => ({
    ...field,
    value: findFirstValue(
      resolvedElements,
      {
        semanticIdPatterns: field.semanticIdPatterns,
        idShortPatterns: field.idShortPatterns,
      },
      preferredLangs
    ),
  })).filter((f) => isProvided(f.value));

  const serial = fields.find((field) => field.key === 'serial')?.value;
  const orderCode = fields.find((field) => field.key === 'orderCode')?.value;
  const articleNumber = fields.find((field) => field.key === 'articleNumber')?.value;
  const markerSeed = serial ?? orderCode ?? articleNumber;
  const markerPattern = markerSeed ? buildMarkerGradient(markerSeed) : undefined;

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

      {markerPattern && (
        <div className="nameplate-marker" aria-label="Identifier marker">
          <div className="nameplate-marker-bar" style={{ backgroundImage: markerPattern }} />
          <span className="nameplate-marker-label">Identifier marker</span>
        </div>
      )}

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
