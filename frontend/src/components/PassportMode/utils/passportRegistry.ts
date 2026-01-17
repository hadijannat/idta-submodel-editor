/**
 * Passport Registry - Template detection for card type routing.
 *
 * Uses a registry pattern to detect which passport card to render
 * based on semanticId, template name, or idShort patterns.
 */

import type { SubmodelUISchema } from '../../../types/ui-schema';

/**
 * Supported passport card types.
 */
export type PassportCardType = 'nameplate' | 'pcf' | 'generic';

/**
 * Detection patterns for each card type.
 * Order matters - first match wins.
 */
interface CardPattern {
  type: PassportCardType;
  semanticIdPatterns: RegExp[];
  templateNamePatterns: RegExp[];
  idShortPatterns: RegExp[];
}

const CARD_PATTERNS: CardPattern[] = [
  {
    type: 'nameplate',
    semanticIdPatterns: [
      /02006/i, // IDTA number
      /nameplate/i,
      /idta\/nameplate/i,
      /0173-1#01-AGZ672#001/i, // ECLASS semantic ID for Nameplate
    ],
    templateNamePatterns: [/nameplate/i, /02006/i],
    idShortPatterns: [/^nameplate$/i],
  },
  {
    type: 'pcf',
    semanticIdPatterns: [
      /02023/i, // IDTA number
      /CarbonFootprint/i,
      /ProductCarbonFootprint/i,
      /0173-1#01-AHE712#001/i, // ECLASS semantic ID for PCF
      /PCF/i,
    ],
    templateNamePatterns: [/carbon/i, /footprint/i, /pcf/i, /02023/i],
    idShortPatterns: [/^CarbonFootprint$/i, /^ProductCarbonFootprint$/i, /^PCF$/i],
  },
];

/**
 * Detect the appropriate passport card type for a schema.
 *
 * Detection priority:
 * 1. semanticId patterns
 * 2. templateName patterns
 * 3. idShort patterns
 * 4. Falls back to 'generic'
 */
export function detectPassportType(schema: SubmodelUISchema | null): PassportCardType {
  if (!schema) {
    return 'generic';
  }

  for (const pattern of CARD_PATTERNS) {
    // Check semanticId
    if (schema.semanticId) {
      for (const regex of pattern.semanticIdPatterns) {
        if (regex.test(schema.semanticId)) {
          return pattern.type;
        }
      }
    }

    // Check templateName
    if (schema.templateName) {
      for (const regex of pattern.templateNamePatterns) {
        if (regex.test(schema.templateName)) {
          return pattern.type;
        }
      }
    }

    // Check idShort
    if (schema.idShort) {
      for (const regex of pattern.idShortPatterns) {
        if (regex.test(schema.idShort)) {
          return pattern.type;
        }
      }
    }
  }

  return 'generic';
}

/**
 * Human-readable label for card types.
 */
export function getCardTypeLabel(type: PassportCardType): string {
  switch (type) {
    case 'nameplate':
      return 'Digital Nameplate';
    case 'pcf':
      return 'Product Carbon Footprint';
    case 'generic':
      return 'Digital Passport';
  }
}
