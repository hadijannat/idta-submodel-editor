/**
 * Form-wide display options and specification notes shared by all fields.
 */

import { createContext, useContext } from 'react';
import type { SpecificationNote } from '../../types/ui-schema';

export interface FormOptions {
  /** Show semantic ID controls on every field (for AAS modellers). */
  showSemantic: boolean;
  /** Requirements read from the specification PDF, keyed by idShort path. */
  specNotes: Record<string, SpecificationNote>;
  /** URL of the specification PDF, if available. */
  specificationUrl: string | null;
}

export const DEFAULT_FORM_OPTIONS: FormOptions = {
  showSemantic: true,
  specNotes: {},
  specificationUrl: null,
};

export const FormOptionsContext = createContext<FormOptions>(DEFAULT_FORM_OPTIONS);

export function useFormOptions(): FormOptions {
  return useContext(FormOptionsContext);
}
