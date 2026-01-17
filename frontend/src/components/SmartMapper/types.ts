/**
 * Smart Mapper shared types
 */

export interface TargetField {
  idShortPath: string;
  label: string;
  elementType: string;
  valueType?: string | null;
  required: boolean;
  semanticLabel?: string | null;
  languages?: string[];
}

export interface PreviewEntry {
  path: string;
  value: string;
  type: string;
}
