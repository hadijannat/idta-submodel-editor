import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import type { SubmodelUISchema, UIElementSchema } from '../../../types/ui-schema';
import type { SubmodelFormData } from '../../../types/aas-elements';
import { PassportView } from '../index';

const STORAGE_KEY = 'passport-mode-preference';

const createStorageMock = (): Storage => {
  const store = new Map<string, string>();

  return {
    getItem: (key: string) => store.get(String(key)) ?? null,
    setItem: (key: string, value: string) => {
      store.set(String(key), String(value));
    },
    removeItem: (key: string) => {
      store.delete(String(key));
    },
    clear: () => {
      store.clear();
    },
    key: (index: number) => Array.from(store.keys())[index] ?? null,
    get length() {
      return store.size;
    },
  };
};

const getTestLocalStorage = (): Storage => {
  const localStorageCandidate = window.localStorage as Partial<Storage> | undefined;
  if (
    localStorageCandidate &&
    typeof localStorageCandidate.getItem === 'function' &&
    typeof localStorageCandidate.setItem === 'function' &&
    typeof localStorageCandidate.clear === 'function'
  ) {
    return window.localStorage;
  }

  const storageMock = createStorageMock();
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: storageMock,
    writable: true,
  });
  return storageMock;
};

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
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    getTestLocalStorage().clear();
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

  it('restores initial mode from jsdom localStorage', () => {
    const storage = getTestLocalStorage();
    storage.setItem(STORAGE_KEY, 'passport');
    const schema = makeSchema([baseElement({ idShort: 'SerialNumber', modelType: 'Property' })]);

    render(
      <PassportView schema={schema} formData={makeFormData('123')}>
        <div data-testid="editor">Editor content</div>
      </PassportView>
    );

    expect(screen.getByRole('button', { name: /passport view/i })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText('123')).toBeInTheDocument();
    expect(screen.getByTestId('editor')).not.toBeVisible();
  });

  it('persists mode changes to jsdom localStorage', async () => {
    const user = userEvent.setup();
    const storage = getTestLocalStorage();
    const schema = makeSchema([baseElement({ idShort: 'SerialNumber', modelType: 'Property' })]);

    render(
      <PassportView schema={schema} formData={makeFormData('123')}>
        <div data-testid="editor">Editor content</div>
      </PassportView>
    );

    await waitFor(() => {
      expect(storage.getItem(STORAGE_KEY)).toBe('editor');
    });

    await user.click(screen.getByRole('button', { name: /passport view/i }));
    await waitFor(() => {
      expect(storage.getItem(STORAGE_KEY)).toBe('passport');
    });

    await user.click(screen.getByRole('button', { name: /editor/i }));
    await waitFor(() => {
      expect(storage.getItem(STORAGE_KEY)).toBe('editor');
    });
  });
});
