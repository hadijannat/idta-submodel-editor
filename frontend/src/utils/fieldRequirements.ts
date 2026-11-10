/**
 * Helpers that turn the requirements a template declares for an element
 * (enumerations, patterns, ranges, format standards, examples) into what the
 * form needs: option lists, placeholders and inline checks.
 */

import type {
  AllowedValueSchema,
  FormatHintSchema,
  UIElementSchema,
} from '../types/ui-schema';

/** Segments of a form path that are structure, not element names. */
const STRUCTURAL_SEGMENTS = new Set([
  'elements',
  'items',
  'statements',
  'annotations',
  'value',
  'min',
  'max',
  'first',
  'second',
]);

/**
 * Convert a react-hook-form path into the idShort path used by the backend
 * for specification notes: `elements.Markings.items.0.elements.MarkingName`
 * becomes `Markings.MarkingName`.
 */
export function toIdShortPath(formPath: string): string {
  return formPath
    .split('.')
    .filter((segment) => segment && !STRUCTURAL_SEGMENTS.has(segment) && !/^\d+$/.test(segment))
    .join('.');
}

/** Preferred display text of a multi-language string (English first). */
export function preferredText(
  text: Record<string, string> | null | undefined
): string | null {
  if (!text) return null;
  for (const lang of ['en', 'en-US', 'en-GB']) {
    if (text[lang]) return text[lang];
  }
  const first = Object.values(text).find((entry) => entry && entry.trim());
  return first ?? null;
}

/**
 * Split specification prose into the plain description and its "Note:" /
 * "Constraint:" sentences, which IDTA templates append to descriptions.
 */
export function splitNotes(text: string | null | undefined): {
  body: string;
  notes: string[];
} {
  if (!text) return { body: '', notes: [] };
  const parts = text.split(/\s*(?=\b(?:Note|Constraint|Recommendation)\s*\d*\s*:)/i);
  const notes: string[] = [];
  let body = '';
  for (const part of parts) {
    const trimmed = part.trim();
    if (!trimmed) continue;
    const match = /^(Note|Constraint|Recommendation)\s*\d*\s*:\s*(.*)$/is.exec(trimmed);
    if (match) {
      const content = match[2].trim();
      if (content) {
        notes.push(
          match[1].toLowerCase() === 'note' ? content : `${match[1]}: ${content}`
        );
      }
    } else {
      body = body ? `${body} ${trimmed}` : trimmed;
    }
  }
  return { body, notes };
}

/** Display label of an element. */
export function elementLabel(schema: UIElementSchema): string {
  return schema.label || schema.semanticLabel || schema.idShort;
}

function displayNames(type: 'region' | 'language' | 'currency') {
  try {
    return new Intl.DisplayNames(['en'], { type });
  } catch {
    return null;
  }
}

const COUNTRY_CODES =
  'AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW'.split(
    ' '
  );

const CURRENCY_CODES =
  'EUR USD GBP CHF JPY CNY AUD CAD SEK NOK DKK PLN CZK HUF RON BGN TRY INR KRW SGD HKD TWD THB MYR IDR PHP VND BRL MXN ARS CLP COP ZAR AED SAR ILS EGP NZD RUB UAH'.split(
    ' '
  );

const LANGUAGE_CODES =
  'en de fr es it pt nl sv da no fi pl cs sk hu ro bg el tr ru uk zh ja ko ar he hi th vi id'.split(
    ' '
  );

const optionCache = new Map<string, AllowedValueSchema[]>();

/** Options for the named code lists a format hint can refer to. */
export function codeListOptions(name: string | null | undefined): AllowedValueSchema[] {
  if (!name) return [];
  const cached = optionCache.get(name);
  if (cached) return cached;

  let options: AllowedValueSchema[] = [];
  if (name === 'country') {
    const names = displayNames('region');
    options = COUNTRY_CODES.map((code) => ({ value: code, label: names?.of(code) ?? code }));
  } else if (name === 'currency') {
    const names = displayNames('currency');
    options = CURRENCY_CODES.map((code) => ({ value: code, label: names?.of(code) ?? code }));
  } else if (name === 'language') {
    const names = displayNames('language');
    options = LANGUAGE_CODES.map((code) => ({ value: code, label: names?.of(code) ?? code }));
  }
  optionCache.set(name, options);
  return options;
}

/** Suggestions offered for a field: template enumeration or a code list. */
export function fieldOptions(schema: UIElementSchema): AllowedValueSchema[] {
  if (schema.allowedValues && schema.allowedValues.length > 0) {
    return schema.allowedValues;
  }
  return codeListOptions(schema.formatHint?.options);
}

/** Whether the value must come from the enumeration (render a select). */
export function isStrictEnumeration(schema: UIElementSchema): boolean {
  return Boolean(
    schema.allowedValuesStrict &&
      schema.allowedValues &&
      schema.allowedValues.length > 0
  );
}

/** First example value of an element, if the template provides one. */
export function exampleValue(schema: UIElementSchema): string | null {
  const example = schema.exampleValues?.find((entry) => entry && entry.trim());
  return example ?? schema.formatHint?.example ?? null;
}

/** Placeholder text for an input. */
export function fieldPlaceholder(schema: UIElementSchema, label: string): string {
  const example = exampleValue(schema);
  return example ? `e.g. ${example}` : `Enter ${label}`;
}

function safeRegExp(pattern: string | null | undefined): RegExp | null {
  if (!pattern) return null;
  try {
    // Always a full match: a pattern anchored only at the start ("^[A-Z]{2}")
    // would otherwise accept any suffix.
    return new RegExp(`^(?:${pattern})$`);
  } catch {
    return null;
  }
}

/**
 * Check a value against the format standard recognised for the field.
 * Returns a message when the value does not follow it. Advisory only.
 */
export function formatHintWarning(
  hint: FormatHintSchema | null | undefined,
  value: unknown
): string | null {
  if (!hint || value === null || value === undefined) return null;
  const text = String(value).trim();
  if (!text) return null;
  const regex = safeRegExp(hint.pattern);
  if (regex && !regex.test(text)) {
    return `Does not look like ${hint.label}${hint.example ? ` (e.g. ${hint.example})` : ''}`;
  }
  if (hint.options) {
    const options = codeListOptions(hint.options);
    if (
      hint.options === 'country' &&
      options.length > 0 &&
      !options.some((option) => option.value === text)
    ) {
      return `"${text}" is not an assigned ${hint.label} code`;
    }
  }
  return null;
}

/**
 * Check a value against the binding requirements of the template
 * (enumeration, pattern, range). Returns an error message or null.
 */
export function requirementError(schema: UIElementSchema, value: unknown): string | null {
  if (value === null || value === undefined || value === '') return null;
  const text = typeof value === 'boolean' ? String(value) : String(value).trim();
  if (!text) return null;

  if (isStrictEnumeration(schema)) {
    const allowed = (schema.allowedValues ?? []).map((option) => option.value);
    const matches =
      allowed.includes(text) ||
      (typeof value === 'boolean' &&
        allowed.some((option) => option.toLowerCase() === text));
    if (!matches) {
      return `Must be one of: ${allowed.slice(0, 8).join(', ')}${allowed.length > 8 ? ' …' : ''}`;
    }
  }

  const regex = safeRegExp(schema.pattern);
  if (regex && text.length <= 2000 && !regex.test(text)) {
    return `Does not match the pattern required by the template: ${schema.pattern}`;
  }

  const numeric = Number(text);
  if (!Number.isNaN(numeric)) {
    for (const bounds of [schema.allowedRange, schema.constraints]) {
      if (!bounds) continue;
      if (bounds.min !== null && bounds.min !== undefined && numeric < bounds.min) {
        return `Must be at least ${bounds.min}`;
      }
      if (bounds.max !== null && bounds.max !== undefined && numeric > bounds.max) {
        return `Must be at most ${bounds.max}`;
      }
    }
  }
  return null;
}

/** Whether a value is still the example the template ships with. */
export function isTemplateExample(schema: UIElementSchema, value: unknown): boolean {
  if (!schema.exampleValues || schema.exampleValues.length === 0) return false;
  if (value === null || value === undefined || typeof value === 'boolean') return false;
  if (schema.allowedValues && schema.allowedValues.length > 0) return false;
  const text = String(value).trim();
  if (!text || text === '0' || text === '1') return false;
  return schema.exampleValues.some((example) => example.trim() === text);
}
