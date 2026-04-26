import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { FormProvider, useForm } from 'react-hook-form';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ReferenceField } from '../ReferenceField';
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

const schema: UIElementSchema = {
  idShort: 'Reference',
  modelType: 'ReferenceElement',
  semanticId: null,
  semanticLabel: null,
  description: null,
  qualifiers: [],
  cardinality: '[1]',
  category: null,
  value: '',
};

const renderField = () => {
  const TestHarness = () => {
    const form = useForm({
      defaultValues: {
        elements: {
          Reference: {
            value: '',
            semanticId: null,
          },
        },
      },
      mode: 'onSubmit',
    });

    return (
      <FormProvider {...form}>
        <form onSubmit={form.handleSubmit(() => undefined)}>
          <ReferenceField
            path="elements.Reference.value"
            schema={schema}
            label="Reference"
            required
          />
          <button type="submit">Validate</button>
        </form>
      </FormProvider>
    );
  };

  render(<TestHarness />);
};

describe('ReferenceField', () => {
  it('accepts URN references to match backend validation', async () => {
    renderField();

    fireEvent.change(screen.getByRole('textbox', { name: /reference/i }), {
      target: { value: 'urn:asset:123' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Validate' }));

    await waitFor(() => {
      expect(screen.queryByText('Please enter a valid URI/IRI or IRDI')).not.toBeInTheDocument();
    });
  });

  it('rejects values without a URI scheme or IRDI shape', async () => {
    renderField();

    fireEvent.change(screen.getByRole('textbox', { name: /reference/i }), {
      target: { value: 'not-a-reference' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Validate' }));

    expect(await screen.findByText('Please enter a valid URI/IRI or IRDI')).toBeInTheDocument();
  });
});
