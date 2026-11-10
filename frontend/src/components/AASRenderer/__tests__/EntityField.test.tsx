import { cleanup, render, screen } from '@testing-library/react';
import { FormProvider, useForm } from 'react-hook-form';
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

const entity = (overrides: Partial<UIElementSchema>): UIElementSchema => ({
  idShort: 'EntryNode',
  modelType: 'Entity',
  semanticId: null,
  semanticLabel: null,
  description: null,
  qualifiers: [],
  cardinality: '[1]',
  category: null,
  entityType: 'EntityType.SELF_MANAGED_ENTITY',
  globalAssetId: null,
  specificAssetIds: [],
  statements: [],
  ...overrides,
});

const renderEntity = (schema: UIElementSchema) => {
  const TestHarness = () => {
    const form = useForm({
      defaultValues: { elements: { EntryNode: { globalAssetId: '', statements: {} } } },
    });
    return (
      <FormProvider {...form}>
        <AASRenderer schema={schema} path="elements.EntryNode" />
      </FormProvider>
    );
  };
  return render(<TestHarness />);
};

const assetIdLabel = () => screen.getByText('Global Asset ID').closest('label');

describe('Entity asset ID', () => {
  it('is required for a self-managed entity', () => {
    renderEntity(entity({}));

    expect(assetIdLabel()?.textContent).toContain('*');
  });

  it('is optional for a co-managed entity', () => {
    renderEntity(entity({ entityType: 'EntityType.CO_MANAGED_ENTITY' }));

    expect(assetIdLabel()?.textContent).not.toContain('*');
  });

  it('is optional while the entity itself is optional', () => {
    renderEntity(entity({ cardinality: '[0..1]' }));

    expect(assetIdLabel()?.textContent).not.toContain('*');
  });
});
