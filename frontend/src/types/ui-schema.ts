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
  semanticLabel: string | null;
  description: Record<string, string> | null;
  qualifiers: QualifierSchema[];
  cardinality: string;
  category: string | null;

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
 * Complete UI schema for a Submodel.
 */
export interface SubmodelUISchema {
  templateName?: string | null;
  templatePath?: string | null;
  submodelId: string;
  idShort: string;
  semanticId: string | null;
  description: Record<string, string> | null;
  administration: AdministrationSchema | null;
  elements: UIElementSchema[];
  supplementaryFiles: string[];
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
}

/**
 * Template version information.
 */
export interface TemplateVersionInfo {
  version: string;
  path: string;
  sha: string | null;
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
