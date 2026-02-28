import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { useSubmodelForm } from '../useSubmodelForm';
import type { SubmodelUISchema, UIElementSchema } from '../../types/ui-schema';

const baseElement = (overrides: Partial<UIElementSchema>): UIElementSchema => ({
  idShort: 'Field',
  modelType: 'MultiLanguageProperty',
  semanticId: null,
  semanticLabel: null,
  description: null,
  qualifiers: [],
  cardinality: '[1]',
  category: null,
  supportedLanguages: ['en'],
  ...overrides,
});

const makeSchema = (elements: UIElementSchema[]): SubmodelUISchema => ({
  submodelId: 'urn:test:submodel',
  idShort: 'TestSubmodel',
  semanticId: null,
  description: null,
  administration: {
    version: null,
    revision: null,
    creator: null,
    templateId: null,
  },
  elements,
  supplementaryFiles: [],
});

describe('useSubmodelForm zod v4 compatibility', () => {
  it('initializes without schema and validates an empty form', async () => {
    const { result } = renderHook(() => useSubmodelForm());

    let isValid = false;
    await act(async () => {
      isValid = await result.current.form.trigger();
    });

    expect(isValid).toBe(true);
  });

  it('rejects empty required multi-language values', async () => {
    const nameValueField = 'elements.Name.value' as const;
    const schema = makeSchema([
      baseElement({
        idShort: 'Name',
        cardinality: '[1]',
      }),
    ]);
    const { result } = renderHook(() => useSubmodelForm({ initialSchema: schema }));

    let isValid = false;
    await act(async () => {
      isValid = await result.current.form.trigger();
    });

    expect(isValid).toBe(false);
    expect(result.current.form.getFieldState(nameValueField).error?.message).toBe(
      'At least one translation is required'
    );
  });

  it('accepts required multi-language values when one translation is non-empty', async () => {
    const nameValueField = 'elements.Name.value' as const;
    const schema = makeSchema([
      baseElement({
        idShort: 'Name',
        cardinality: '[1]',
      }),
    ]);
    const { result } = renderHook(() => useSubmodelForm({ initialSchema: schema }));

    await act(async () => {
      result.current.form.setValue(nameValueField, { en: 'Motor' });
    });

    let isValid = false;
    await act(async () => {
      isValid = await result.current.form.trigger();
    });

    expect(isValid).toBe(true);
  });

  it('allows undefined optional multi-language values', async () => {
    const descriptionValueField = 'elements.Description.value' as const;
    const schema = makeSchema([
      baseElement({
        idShort: 'Description',
        cardinality: '[0..1]',
      }),
    ]);
    const { result } = renderHook(() => useSubmodelForm({ initialSchema: schema }));

    await act(async () => {
      result.current.form.setValue(descriptionValueField, undefined);
    });

    let isValid = false;
    await act(async () => {
      isValid = await result.current.form.trigger();
    });

    expect(isValid).toBe(true);
  });
});
