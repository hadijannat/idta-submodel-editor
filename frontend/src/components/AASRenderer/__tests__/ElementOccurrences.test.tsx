import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { FormProvider, useForm, type FieldValues, type UseFormReturn } from 'react-hook-form';
import { afterEach, describe, expect, it, vi } from 'vitest';

import AASRenderer from '../index';
import type { UIElementSchema } from '../../../types/ui-schema';

vi.mock('../../semantic/SemanticLookupModal', () => ({
  default: () => null,
}));

vi.mock('../../semantic/SemanticChip', () => ({
  default: () => <button type="button">Semantic</button>,
}));

afterEach(() => {
  cleanup();
});

const property = (overrides: Partial<UIElementSchema>): UIElementSchema => ({
  idShort: 'Phone',
  modelType: 'Property',
  semanticId: null,
  semanticLabel: null,
  description: null,
  qualifiers: [],
  cardinality: '[0..*]',
  category: null,
  valueType: 'xs:string',
  inputType: 'text',
  repeatable: true,
  ...overrides,
});

const collection: UIElementSchema = {
  idShort: 'Contact',
  modelType: 'SubmodelElementCollection',
  semanticId: null,
  semanticLabel: null,
  description: null,
  qualifiers: [],
  cardinality: '[1..*]',
  category: null,
  repeatable: true,
  elements: [property({ idShort: 'Mail', cardinality: '[0..*]' })],
};

let form: UseFormReturn<FieldValues>;

const renderElement = (schema: UIElementSchema, defaults: Record<string, unknown>) => {
  const TestHarness = () => {
    form = useForm<FieldValues>({
      defaultValues: { elements: { [schema.idShort]: defaults } },
    });
    return (
      <FormProvider {...form}>
        <AASRenderer schema={schema} path={`elements.${schema.idShort}`} />
      </FormProvider>
    );
  };
  return render(<TestHarness />);
};

const occurrences = (idShort: string) =>
  form.getValues(`elements.${idShort}.occurrences`) as unknown[] | undefined;

describe('ElementOccurrences', () => {
  it('offers another occurrence for a repeatable element', () => {
    renderElement(property({}), { value: '' });

    expect(screen.getByRole('button', { name: '+ Add another Phone' })).toBeTruthy();
  });

  it('does not offer it for an element that occurs once', () => {
    renderElement(property({ repeatable: false, cardinality: '[0..1]' }), { value: '' });

    expect(screen.queryByRole('button', { name: /Add another/ })).toBeNull();
  });

  it('adds occurrences to the element and removes them again', async () => {
    renderElement(property({}), { value: 'first' });

    fireEvent.click(screen.getByRole('button', { name: '+ Add another Phone' }));
    fireEvent.click(screen.getByRole('button', { name: '+ Add another Phone' }));

    await waitFor(() => expect(occurrences('Phone')).toHaveLength(2));
    expect(screen.getByText('Phone 2')).toBeTruthy();
    expect(screen.getByText('Phone 3')).toBeTruthy();
    // The first occurrence keeps its place in the form data.
    expect(form.getValues('elements.Phone.value')).toBe('first');

    fireEvent.click(screen.getByRole('button', { name: 'Remove Phone 2' }));

    await waitFor(() => expect(occurrences('Phone')).toHaveLength(1));
    expect(screen.queryByText('Phone 3')).toBeNull();
  });

  it('stores what is typed into a further occurrence', async () => {
    renderElement(property({}), { value: 'first' });
    fireEvent.click(screen.getByRole('button', { name: '+ Add another Phone' }));
    await waitFor(() => expect(occurrences('Phone')).toHaveLength(1));

    const inputs = screen.getAllByRole('textbox');
    fireEvent.change(inputs[inputs.length - 1], { target: { value: 'second' } });

    await waitFor(() =>
      expect(form.getValues('elements.Phone.occurrences.0.value')).toBe('second')
    );
    expect(form.getValues('elements.Phone.value')).toBe('first');
  });

  it('stops at the upper bound of the template', async () => {
    renderElement(property({ cardinality: '[0..2]' }), { value: '' });
    const add = screen.getByRole('button', { name: '+ Add another Phone' }) as HTMLButtonElement;
    expect(add.disabled).toBe(false);

    fireEvent.click(add);

    await waitFor(() => expect(add.disabled).toBe(true));
  });

  it('lets repeatable children repeat inside each occurrence of their parent', async () => {
    renderElement(collection, { elements: { Mail: { value: '' } } });

    fireEvent.click(screen.getByRole('button', { name: '+ Add another Contact' }));
    await waitFor(() => expect(occurrences('Contact')).toHaveLength(1));

    // One "add Mail" control per Contact, and none to nest Contacts.
    expect(screen.getAllByRole('button', { name: '+ Add another Mail' })).toHaveLength(2);
    expect(screen.getAllByRole('button', { name: '+ Add another Contact' })).toHaveLength(1);

    const mailButtons = screen.getAllByRole('button', { name: '+ Add another Mail' });
    fireEvent.click(mailButtons[1]);

    await waitFor(() =>
      expect(
        form.getValues('elements.Contact.occurrences.0.elements.Mail.occurrences')
      ).toHaveLength(1)
    );
  });
});
