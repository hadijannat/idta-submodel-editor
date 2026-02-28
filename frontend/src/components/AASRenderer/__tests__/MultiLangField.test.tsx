import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { FormProvider, useForm } from 'react-hook-form';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { MultiLangField } from '../MultiLangField';
import type { UIElementSchema } from '../../../types/ui-schema';

vi.mock('../../semantic/SemanticLookupModal', () => ({
  default: () => null,
}));

vi.mock('../../semantic/SemanticChip', () => ({
  default: ({ onOpen }: { onOpen: () => void }) => (
    <button type="button" onClick={onOpen}>
      Open semantic lookup
    </button>
  ),
}));

afterEach(() => {
  cleanup();
});

const makeSchema = (overrides: Partial<UIElementSchema> = {}): UIElementSchema => ({
  idShort: 'Name',
  modelType: 'MultiLanguageProperty',
  semanticId: null,
  semanticLabel: null,
  description: null,
  qualifiers: [],
  cardinality: '[1]',
  category: null,
  supportedLanguages: ['en', 'de'],
  value: {},
  ...overrides,
});

interface RenderFieldOptions {
  schema?: UIElementSchema;
  required?: boolean;
  requiredLanguages?: string[];
}

interface TestFormValues {
  elements: {
    Name: {
      value: Record<string, string>;
      semanticId: string | null;
    };
  };
}

const renderField = ({
  schema = makeSchema(),
  required = true,
  requiredLanguages = ['en'],
}: RenderFieldOptions = {}) => {
  const TestHarness = () => {
    const form = useForm<TestFormValues>({
      defaultValues: {
        elements: {
          Name: {
            value: {
              en: '',
              de: '',
              ar: '',
            },
            semanticId: null,
          },
        },
      },
    });

    return (
      <FormProvider {...form}>
        <MultiLangField
          path="elements.Name.value"
          schema={schema}
          label="Name"
          required={required}
          requiredLanguages={requiredLanguages}
        />
      </FormProvider>
    );
  };

  render(<TestHarness />);
};

describe('MultiLangField', () => {
  it('links tabs and tab panels with deterministic ids', () => {
    renderField({
      schema: makeSchema({ supportedLanguages: ['en', 'de'] }),
    });

    expect(screen.getByRole('tab', { name: /english/i })).toHaveAttribute(
      'id',
      'elements.Name.value-tab-en'
    );
    expect(screen.getByRole('tab', { name: /deutsch/i })).toHaveAttribute(
      'id',
      'elements.Name.value-tab-de'
    );

    const englishPanel = document.getElementById('elements.Name.value-panel-en');
    const germanPanel = document.getElementById('elements.Name.value-panel-de');

    if (!englishPanel || !germanPanel) {
      throw new Error('Expected language panels to be rendered for all supported languages');
    }

    expect(englishPanel).toHaveAttribute('aria-labelledby', 'elements.Name.value-tab-en');
    expect(germanPanel).toHaveAttribute('aria-labelledby', 'elements.Name.value-tab-de');
  });

  it('sanitizes problematic unicode input before persisting value', async () => {
    renderField({
      schema: makeSchema({ supportedLanguages: ['en'] }),
    });

    const input = screen.getByLabelText('Name in English') as HTMLTextAreaElement;

    fireEvent.change(input, {
      target: { value: '\uFEFF  Motor  ' },
    });

    await waitFor(() => {
      expect(input.value).toBe('Motor');
    });
  });

  it('updates translation gap indicators when required languages are filled', async () => {
    renderField({
      schema: makeSchema({ supportedLanguages: ['en', 'de'] }),
      requiredLanguages: ['en', 'de'],
    });

    expect(screen.getByText(/\(missing: en, de\)/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Name in English'), {
      target: { value: 'Motor' },
    });

    await waitFor(() => {
      expect(screen.getByText(/\(missing: de\)/i)).toBeInTheDocument();
    });

    expect(screen.getByText('1/2 translations')).toBeInTheDocument();
  });
});
