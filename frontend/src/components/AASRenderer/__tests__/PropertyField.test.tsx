import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { FormProvider, useForm } from 'react-hook-form';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { PropertyField } from '../PropertyField';
import { FormOptionsContext } from '../FormOptionsContext';
import type { UIElementSchema } from '../../../types/ui-schema';

vi.mock('../../semantic/SemanticLookupModal', () => ({
  default: () => null,
}));

vi.mock('../../semantic/SemanticChip', () => ({
  default: () => <button type="button">Semantic chip</button>,
}));

afterEach(() => {
  cleanup();
});

const baseSchema: UIElementSchema = {
  idShort: 'CountryOfOrigin',
  modelType: 'Property',
  semanticId: '0112/2///61987#ABP462#001',
  semanticLabel: 'CountryOfOrigin',
  label: 'Country Of Origin',
  description: {
    en: 'Note: Country codes defined accord. to DIN EN ISO 3166-1 alpha-2 codes',
  },
  definition: { en: 'country where the product was manufactured' },
  qualifiers: [],
  cardinality: '[0..1]',
  category: null,
  valueType: 'xs:string',
  inputType: 'text',
  value: 'DE',
  exampleValues: ['DE'],
  standards: ['DIN EN ISO 3166-1'],
  formatHint: {
    id: 'iso3166-1-alpha2',
    label: 'ISO 3166-1 alpha-2',
    description: 'Two-letter country code according to ISO 3166-1 alpha-2.',
    pattern: '^[A-Z]{2}$',
    example: 'DE',
    options: 'country',
    transform: 'uppercase',
  },
};

const renderField = (
  schema: UIElementSchema,
  options: { showSemantic?: boolean; value?: unknown } = {}
) => {
  const Harness = () => {
    const form = useForm({
      defaultValues: {
        elements: {
          [schema.idShort]: { value: options.value ?? schema.value ?? '', semanticId: null },
        },
      },
    });
    return (
      <FormProvider {...form}>
        <FormOptionsContext.Provider
          value={{
            showSemantic: options.showSemantic ?? false,
            specNotes: {
              [schema.idShort]: {
                idShort: schema.idShort,
                notes: ['Note from the specification PDF'],
                page: 10,
                cardinality: '[1]',
                templateCardinality: '[0..1]',
              },
            },
            specificationUrl: 'http://localhost/spec.pdf',
          }}
        >
          <PropertyField
            path={`elements.${schema.idShort}.value`}
            schema={schema}
            label={schema.label ?? schema.idShort}
            required={false}
          />
        </FormOptionsContext.Provider>
      </FormProvider>
    );
  };
  return render(<Harness />);
};

describe('PropertyField', () => {
  it('shows the readable label together with the idShort', () => {
    renderField(baseSchema);

    const label = screen.getByText('Country Of Origin').closest('label');
    expect(label).not.toBeNull();
    expect(label?.textContent).toContain('CountryOfOrigin');
    expect(label?.textContent).toContain('optional');
  });

  it('explains definition, notes, standard and specification page', () => {
    renderField(baseSchema);

    expect(screen.getByText('country where the product was manufactured')).toBeTruthy();
    expect(
      screen.getByText('Country codes defined accord. to DIN EN ISO 3166-1 alpha-2 codes')
    ).toBeTruthy();
    expect(screen.getByText('ISO 3166-1 alpha-2')).toBeTruthy();
    const link = screen.getByText('Specification, p. 10') as HTMLAnchorElement;
    expect(link.getAttribute('href')).toBe('http://localhost/spec.pdf#page=10');
    // The package already carries a note, so the PDF note is not repeated.
    expect(screen.queryByText('Note from the specification PDF')).toBeNull();
    expect(
      screen.getByText(/specification PDF states cardinality \[1\]; the template package declares \[0\.\.1\]/)
    ).toBeTruthy();
  });

  it('flags an unchanged template example and can clear it', () => {
    renderField(baseSchema);

    const input = screen.getByRole('combobox') as HTMLInputElement;
    expect(input.value).toBe('DE');
    expect(screen.getByText(/Example value from the template/)).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Clear' }));

    expect(input.value).toBe('');
    expect(screen.queryByText(/Example value from the template/)).toBeNull();
    expect(input.getAttribute('placeholder')).toBe('e.g. DE');
  });

  it('warns about values that do not follow the format and normalises case', () => {
    renderField(baseSchema, { value: '' });
    const input = screen.getByRole('combobox') as HTMLInputElement;

    fireEvent.change(input, { target: { value: 'Germany' } });
    expect(screen.getByText(/Does not look like ISO 3166-1 alpha-2/)).toBeTruthy();

    fireEvent.change(input, { target: { value: 'fr' } });
    fireEvent.blur(input);
    expect(input.value).toBe('FR');
    expect(screen.queryByText(/Does not look like/)).toBeNull();
  });

  it('offers the ISO country list as suggestions', () => {
    const { container } = renderField(baseSchema);

    const options = container.querySelectorAll('datalist option');
    expect(options.length).toBeGreaterThan(200);
  });

  it('renders a strict enumeration as a select', () => {
    renderField(
      {
        ...baseSchema,
        idShort: 'Conformity',
        label: 'Conformity',
        formatHint: null,
        standards: null,
        exampleValues: null,
        value: '',
        allowedValues: [{ value: 'pass' }, { value: 'fail' }],
        allowedValuesStrict: true,
      },
      { value: '' }
    );

    const select = screen.getByRole('combobox') as HTMLSelectElement;
    expect(select.tagName).toBe('SELECT');
    expect(Array.from(select.options).map((option) => option.value)).toEqual([
      '',
      'pass',
      'fail',
    ]);
  });

  it('uses typed inputs with the bounds declared by the template', () => {
    renderField(
      {
        ...baseSchema,
        idShort: 'Offset',
        label: 'Offset',
        valueType: 'xs:unsignedByte',
        inputType: 'number',
        step: '1',
        formatHint: null,
        exampleValues: null,
        value: null,
        constraints: { min: 0, max: 255 },
        allowedRange: { min: 0, max: 63 },
      },
      { value: '' }
    );

    const input = screen.getByRole('spinbutton') as HTMLInputElement;
    expect(input.getAttribute('min')).toBe('0');
    expect(input.getAttribute('max')).toBe('63');
    expect(screen.getByText('Allowed range: 0 to 63')).toBeTruthy();
  });

  it('hides semantic controls unless they are switched on', () => {
    renderField(baseSchema);
    expect(screen.queryByText('Semantic chip')).toBeNull();

    cleanup();
    renderField(baseSchema, { showSemantic: true });
    expect(screen.getByText('Semantic chip')).toBeTruthy();
  });
});
