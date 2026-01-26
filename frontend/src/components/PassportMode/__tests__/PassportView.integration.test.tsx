import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach } from 'vitest';
import type { SubmodelUISchema, UIElementSchema } from '../../../types/ui-schema';
import type { SubmodelFormData } from '../../../types/aas-elements';
import { PassportView } from '../index';

const baseElement = (overrides: Partial<UIElementSchema>): UIElementSchema => ({
  idShort: 'Element',
  modelType: 'Property',
  semanticId: null,
  semanticLabel: null,
  description: null,
  qualifiers: [],
  cardinality: '[0..1]',
  category: null,
  ...overrides,
});

const makeSchema = (elements: UIElementSchema[]): SubmodelUISchema => ({
  templateName: 'Test',
  templatePath: null,
  submodelId: 'urn:test',
  idShort: 'Test',
  semanticId: null,
  description: null,
  administration: null,
  elements,
  supplementaryFiles: [],
});

const makeFormData = (value: string): SubmodelFormData => ({
  elements: {
    SerialNumber: { value },
  },
});

describe('PassportView integration', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('toggles views and reflects live updates', async () => {
    const user = userEvent.setup();
    const schema = makeSchema([
      baseElement({ idShort: 'SerialNumber', modelType: 'Property' }),
    ]);

    const { rerender } = render(
      <PassportView schema={schema} formData={makeFormData('123')}>
        <div data-testid="editor">Editor content</div>
      </PassportView>
    );

    const editor = screen.getByTestId('editor');
    expect(editor).toBeVisible();
    expect(screen.queryByText('123')).toBeNull();

    await user.click(screen.getByRole('button', { name: /passport view/i }));

    expect(editor).toBeInTheDocument();
    await waitFor(() => {
      expect(editor).not.toBeVisible();
    }, { timeout: 500 });

    // Wait for skeleton to disappear and content to show (150ms delay + useTransition)
    await waitFor(() => {
      expect(screen.getByText('123')).toBeInTheDocument();
    }, { timeout: 500 });

    rerender(
      <PassportView schema={schema} formData={makeFormData('456')}>
        <div data-testid="editor">Editor content</div>
      </PassportView>
    );

    await waitFor(() => {
      expect(screen.getByText('456')).toBeInTheDocument();
    }, { timeout: 500 });
  });
});
