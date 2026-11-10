/**
 * TypeScript interfaces for UI schema.
 *
 * These interfaces match the backend Pydantic models and define
 * the structure of data exchanged between frontend and backend.
 */

/**
 * Supported SubmodelElement types.
 */
export type ElementModelType =
  | 'SubmodelElement'
  | 'Property'
  | 'SubmodelElementCollection'
  | 'SubmodelElementList'
  | 'MultiLanguageProperty'
  | 'File'
  | 'Blob'
  | 'Range'
  | 'ReferenceElement'
  | 'Entity'
  | 'RelationshipElement'
  | 'AnnotatedRelationshipElement'
  | 'Operation'
  | 'Capability'
  | 'BasicEventElement';

/**
 * Qualifier attached to an element.
 */
export interface QualifierSchema {
  type: string;
  value: string | null;
  valueType: string | null;
  semanticId: string | null;
  kind: string | null;
}

/**
 * Numeric constraints for Property elements.
 */
export interface ConstraintSchema {
  min: number | null;
  max: number | null;
}

/**
 * One entry of an enumeration the template defines for a value.
 */
export interface AllowedValueSchema {
  value: string;
  label?: string | null;
  valueId?: string | null;
}

/**
 * Format standard recognised in the specification text of an element,
 * e.g. an ISO 3166-1 alpha-2 country code. Advisory: mismatches are warnings.
 */
export interface FormatHintSchema {
  id: string;
  label: string;
  description: string;
  pattern?: string | null;
  example?: string | null;
  /** Named code list the UI can offer: country | currency | language */
  options?: string | null;
  transform?: 'uppercase' | 'lowercase' | null;
  source?: string;
}

/**
 * Schema for a single SubmodelElement.
 *
 * This is a recursive structure - collections and lists contain
 * nested ElementSchema objects.
 */
export interface UIElementSchema {
  // Common fields
  idShort: string;
  modelType: ElementModelType;
  semanticId: string | null;
  supplementalSemanticIds?: string[];
  semanticLabel: string | null;
  /** Human-readable label (displayName, preferred name or humanized idShort) */
  label?: string | null;
  description: Record<string, string> | null;
  /** Definition from the ConceptDescription (description then holds spec notes) */
  definition?: Record<string, string> | null;
  qualifiers: QualifierSchema[];
  cardinality: string;
  category: string | null;

  // Requirements declared by the template (qualifiers / IEC 61360)
  exampleValues?: string[] | null;
  defaultValue?: string | null;
  initialValue?: string | null;
  allowedValues?: AllowedValueSchema[] | null;
  allowedValuesStrict?: boolean | null;
  pattern?: string | null;
  allowedRange?: ConstraintSchema | null;
  requiredLanguages?: string[] | null;
  eitherOr?: string | null;
  allowedIdShort?: string | null;
  editIdShort?: boolean | null;
  accessMode?: string | null;
  readOnly?: boolean | null;
  formTitle?: string | null;
  formInfo?: string | null;
  formUrl?: string | null;
  notes?: string[] | null;
  valueFormat?: string | null;
  valueFormatDescription?: string | null;
  maxLength?: number | null;
  minLength?: number | null;
  sourceOfDefinition?: string | null;

  // Requirements recognised in the specification text
  formatHint?: FormatHintSchema | null;
  standards?: string[] | null;

  // Property-specific
  valueType?: string;
  value?: unknown;
  inputType?: string;
  step?: string | null;
  constraints?: ConstraintSchema | null;
  unit?: string | null;
  valueId?: string | null;

  // Collection-specific
  elements?: UIElementSchema[];

  // List-specific
  typeValueListElement?: string;
  orderRelevant?: boolean;
  valueTypeListElement?: string | null;
  semanticIdListElement?: string | null;
  itemTemplate?: UIElementSchema | null;
  items?: UIElementSchema[];

  // MultiLanguageProperty-specific
  supportedLanguages?: string[];

  // File-specific
  contentType?: string;
  valueEncoding?: string | null;

  // Range-specific
  min?: unknown;
  max?: unknown;

  // Entity-specific
  entityType?: string;
  globalAssetId?: string | null;
  specificAssetIds?: Array<{ name: string; value: string }>;
  statements?: UIElementSchema[];

  // Relationship-specific
  first?: string | null;
  second?: string | null;
  annotations?: UIElementSchema[];

  // Operation-specific
  inputVariables?: UIElementSchema[];
  outputVariables?: UIElementSchema[];
  inoutputVariables?: UIElementSchema[];

  // Event-specific
  observed?: string | null;
  direction?: string;
  state?: string;
  messageTopic?: string | null;
  messageBroker?: string | null;
  lastUpdate?: string | null;
  minInterval?: string | null;
  maxInterval?: string | null;
}

/**
 * Administrative information for the submodel.
 */
export interface AdministrationSchema {
  version: string | null;
  revision: string | null;
  creator: string | null;
  templateId: string | null;
}

/**
 * A file that belongs to a template release (AASX, JSON, PDF, README).
 */
export interface TemplateDocument {
  name: string;
  path?: string | null;
  url?: string | null;
  downloadUrl?: string | null;
  size?: number | null;
}

/**
 * Which template release a schema was generated from.
 */
export interface TemplateSource {
  name: string;
  title?: string | null;
  status?: string | null;
  idtaNumber?: string | null;
  group?: string | null;
  part?: string | null;
  version?: string | null;
  latestVersion?: string | null;
  isLatest?: boolean | null;
  source?: string | null;
  stale?: boolean | null;
  browseUrl?: string | null;
  documents?: {
    aasx?: TemplateDocument | null;
    json?: TemplateDocument | null;
    specification?: TemplateDocument | null;
    readme?: TemplateDocument | null;
  } | null;
  variants?: string[];
}

/**
 * Requirements read from the specification PDF for one element.
 */
export interface SpecificationNote {
  idShort: string;
  cardinality?: string | null;
  templateCardinality?: string | null;
  notes: string[];
  example?: string | null;
  description?: string | null;
  page?: number | null;
}

/**
 * Per-element requirements extracted from the specification PDF, keyed by
 * the idShort path of the element (list items share the path of their list).
 */
export interface SpecificationNotes {
  available: boolean;
  document?: TemplateDocument | null;
  pageCount?: number | null;
  matched?: number;
  total?: number;
  notes: Record<string, SpecificationNote>;
}

/**
 * Complete UI schema for a Submodel.
 */
export interface SubmodelUISchema {
  templateName?: string | null;
  templatePath?: string | null;
  template?: TemplateSource | null;
  kind?: string | null;
  formTitle?: string | null;
  formInfo?: string | null;
  formUrl?: string | null;
  submodelId: string;
  idShort: string;
  semanticId: string | null;
  description: Record<string, string> | null;
  administration: AdministrationSchema | null;
  elements: UIElementSchema[];
  supplementaryFiles: string[];
  pcfActivityListInjected?: boolean | null;
}

/**
 * Information about an available template.
 */
export interface TemplateInfo {
  name: string;
  path: string;
  url: string;
  idta_number: string | null;
  title: string | null;
  sha: string | null;
  status?: 'published' | 'deprecated';
  /** Multi-part templates list one entry per part; group is the parent. */
  group?: string | null;
  part?: string | null;
  latest_version?: string | null;
  versions?: string[];
  has_specification?: boolean | null;
}

/**
 * Template version information.
 */
export interface TemplateVersionInfo {
  version: string;
  path: string;
  sha: string | null;
  file?: string | null;
  latest?: boolean | null;
  has_specification?: boolean | null;
  sample_only?: boolean | null;
}

/**
 * Response from template listing endpoint.
 */
export interface TemplateListResponse {
  templates: TemplateInfo[];
  total: number;
  cached: boolean;
}

/**
 * Validation error detail.
 */
export interface ValidationError {
  field: string;
  message: string;
  code: string | null;
}

/**
 * Form validation result.
 */
export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationError[];
}
