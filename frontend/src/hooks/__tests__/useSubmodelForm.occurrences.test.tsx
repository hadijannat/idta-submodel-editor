import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { useSubmodelForm } from '../useSubmodelForm';
import type { SubmodelFormData } from '../../types/aas-elements';
import type { SubmodelUISchema, UIElementSchema } from '../../types/ui-schema';

const requiredText = (idShort: string): UIElementSchema => ({
  idShort,
  modelType: 'Property',
  semanticId: null,
  semanticLabel: null,
  description: null,
  qualifiers: [],
  cardinality: '[1]',
  category: null,
  valueType: 'xs:string',
  inputType: 'text',
});

const contact: UIElementSchema = {
  idShort: 'Contact',
  modelType: 'SubmodelElementCollection',
  semanticId: null,
  semanticLabel: null,
  description: null,
  qualifiers: [],
  cardinality: '[1..*]',
  category: null,
  repeatable: true,
  elements: [requiredText('Name')],
};

const schema: SubmodelUISchema = {
  submodelId: 'urn:test:template',
  idShort: 'Contacts',
  semanticId: null,
  description: null,
  administration: null,
  elements: [contact],
  supplementaryFiles: [],
};

const contactData = (name: string) => ({ elements: { Name: { value: name } } });

const validate = async (elements: SubmodelFormData['elements']) => {
  const { result } = renderHook(() => useSubmodelForm({ initialSchema: schema }));
  await act(async () => {
    result.current.form.setValue('elements', elements);
  });
  let isValid = false;
  await act(async () => {
    isValid = await result.current.form.trigger();
  });
  return { isValid, form: result.current.form };
};

describe('useSubmodelForm with repeatable elements', () => {
  it('accepts a form without further occurrences', async () => {
    const { isValid } = await validate({ Contact: contactData('Ada') });
    expect(isValid).toBe(true);
  });

  it('accepts complete further occurrences and keeps them in the form data', async () => {
    const { isValid, form } = await validate({
      Contact: { ...contactData('Ada'), occurrences: [contactData('Grace')] },
    });

    expect(isValid).toBe(true);
    expect(form.getValues().elements.Contact.occurrences).toEqual([contactData('Grace')]);
  });

  it('applies the element rules to each further occurrence', async () => {
    const { isValid, form } = await validate({
      Contact: { ...contactData('Ada'), occurrences: [contactData('')] },
    });

    expect(isValid).toBe(false);
    expect(
      form.getFieldState('elements.Contact.occurrences.0.elements.Name.value').error
    ).toBeTruthy();
    expect(form.getFieldState('elements.Contact.elements.Name.value').error).toBeUndefined();
  });
});
