import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { FormProvider, useForm } from 'react-hook-form';
import { afterEach, describe, expect, it, vi } from 'vitest';

import AASRenderer from '../index';
import { ListField } from '../ListField';
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

const blobTemplate: UIElementSchema = {
  idShort: '',
  modelType: 'Blob',
  semanticId: null,
  semanticLabel: null,
  description: null,
  qualifiers: [],
  cardinality: '[1]',
  category: null,
  contentType: 'application/octet-stream',
  value: 'base64:AA==',
  valueEncoding: 'base64',
};

const listSchema: UIElementSchema = {
  idShort: 'BlobList',
  modelType: 'SubmodelElementList',
  semanticId: null,
  semanticLabel: null,
  description: null,
  qualifiers: [],
  cardinality: '[0..*]',
  category: null,
  itemTemplate: blobTemplate,
  items: [],
  orderRelevant: true,
  semanticIdListElement: null,
};

const renderList = () => {
  const TestHarness = () => {
    const form = useForm({
      defaultValues: {
        elements: {
          BlobList: {
            items: [],
            semanticIdListElement: null,
          },
        },
      },
    });

    return (
      <FormProvider {...form}>
        <ListField
          path="elements.BlobList"
          schema={listSchema}
          depth={0}
          renderItem={(itemPath, _index, itemSchema) => (
            <AASRenderer schema={itemSchema} path={itemPath} />
          )}
        />
      </FormProvider>
    );
  };

  render(<TestHarness />);
};

describe('ListField', () => {
  it('adds blob list items with the template shape', async () => {
    renderList();

    fireEvent.click(screen.getByRole('button', { name: 'Add item' }));

    expect(await screen.findByLabelText('Upload Binary Payload')).toBeInTheDocument();
    expect(screen.getByLabelText('Content Type')).toHaveValue(
      'application/octet-stream'
    );
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Blob payload text or base64:...')).toHaveValue(
        'base64:AA=='
      );
    });
  });
});
