/**
 * IDTA templates ship with example values ("Muster AG", "DE", "2022-01-01").
 * These helpers find the fields of a form that still hold such examples so
 * the user can replace or clear them before exporting.
 */

import type { SubmodelUISchema, UIElementSchema } from '../types/ui-schema';
import type { ElementFormData, SubmodelFormData } from '../types/aas-elements';
import { isTemplateExample } from './fieldRequirements';

export interface ExampleField {
  /** Form path of the value (for MultiLanguageProperty: the language entry) */
  path: string;
  /** Element the value belongs to */
  idShort: string;
  /** Value to set when clearing the example */
  emptyValue: '' | null;
}

function collect(
  element: UIElementSchema,
  data: ElementFormData | undefined,
  path: string,
  found: ExampleField[]
): void {
  if (!data) return;

  switch (element.modelType) {
    case 'Property':
      if (isTemplateExample(element, data.value)) {
        found.push({ path: `${path}.value`, idShort: element.idShort, emptyValue: '' });
      }
      return;

    case 'MultiLanguageProperty': {
      const value = data.value as Record<string, string> | undefined;
      if (!value || typeof value !== 'object') return;
      for (const [lang, text] of Object.entries(value)) {
        if (isTemplateExample(element, text)) {
          found.push({
            path: `${path}.value.${lang}`,
            idShort: element.idShort,
            emptyValue: '',
          });
        }
      }
      return;
    }

    case 'SubmodelElementCollection':
      for (const child of element.elements ?? []) {
        collect(child, data.elements?.[child.idShort], `${path}.elements.${child.idShort}`, found);
      }
      return;

    case 'Entity':
      for (const child of element.statements ?? []) {
        collect(
          child,
          data.statements?.[child.idShort],
          `${path}.statements.${child.idShort}`,
          found
        );
      }
      return;

    case 'SubmodelElementList': {
      const items = data.items ?? [];
      items.forEach((item, index) => {
        const itemSchema = element.items?.[index] ?? element.itemTemplate;
        if (itemSchema) {
          collect(itemSchema, item, `${path}.items.${index}`, found);
        }
      });
      return;
    }

    default:
      return;
  }
}

/** List the fields that still contain the template's example values. */
export function findExampleFields(
  schema: SubmodelUISchema | null,
  values: SubmodelFormData | undefined
): ExampleField[] {
  if (!schema || !values?.elements) return [];
  const found: ExampleField[] = [];
  for (const element of schema.elements) {
    collect(element, values.elements[element.idShort], `elements.${element.idShort}`, found);
  }
  return found;
}
