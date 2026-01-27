/**
 * Tests for MigrationWizard component.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MigrationWizard from '../MigrationWizard';
import * as templateOpsApi from '../../../services/templateOpsApi';

// Mock the templateOps API
vi.mock('../../../services/templateOpsApi', () => ({
  migrateRecipe: vi.fn(),
  migrateFormData: vi.fn(),
}));

const mockRecipes = [
  {
    name: 'Test Recipe',
    template: { name: 'Digital Nameplate', version: '1.0', status: 'published' as const },
  },
  {
    name: 'Another Recipe',
    template: { name: 'Digital Nameplate', version: '1.0', status: 'published' as const },
  },
  {
    name: 'Different Template Recipe',
    template: { name: 'Handover Doc', version: '1.0', status: 'published' as const },
  },
];

const mockVersions = [
  { version: '1.0', status: 'published' },
  { version: '2.0', status: 'published' },
];

const mockMigrationResult: templateOpsApi.RecipeMigrationResult = {
  migrated_recipe: {
    name: 'Test Recipe',
    schema_version: '1.0.0',
    template: { name: 'Digital Nameplate', version: '2.0', status: 'published' },
    source_profile: { format: 'csv', header_row: 1 },
    mode: { type: 'single', group_by: [] },
    mappings: [],
  },
  mapping_migrations: [
    {
      original_path: 'Manufacturer',
      migrated_path: 'ManufacturerName',
      confidence: 0.95,
      match_reason: 'semantic_id' as const,
      breaking_change: false,
    },
    {
      original_path: 'SerialNumber',
      migrated_path: 'SerialNumber',
      confidence: 1.0,
      match_reason: 'exact_path' as const,
      breaking_change: false,
    },
    {
      original_path: 'OldField',
      migrated_path: null,
      confidence: 0.0,
      match_reason: 'unmapped' as const,
      breaking_change: true,
    },
  ],
  breaking_changes: ['OldField: Field removed in new schema'],
  migration_coverage: 0.67,
  warnings: ['Some mappings have low confidence'],
};

const mockFormMigrationResult: templateOpsApi.FormDataMigrationResult = {
  migrated_form_data: { elements: { ManufacturerName: { value: 'Test' } } },
  value_migrations: [
    {
      original_path: 'Manufacturer',
      migrated_path: 'ManufacturerName',
      original_value: 'Test',
      migrated_value: 'Test',
      confidence: 0.95,
      match_reason: 'semantic_id' as const,
    },
  ],
  migration_coverage: 1.0,
  warnings: [],
};

describe('MigrationWizard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(templateOpsApi.migrateRecipe).mockResolvedValue(mockMigrationResult);
    vi.mocked(templateOpsApi.migrateFormData).mockResolvedValue(mockFormMigrationResult);
  });

  afterEach(() => {
    cleanup();
  });

  describe('Step 1: Artifact Selection', () => {
    it('should render wizard header', () => {
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
        />
      );

      expect(screen.getByText('Migration Wizard')).toBeInTheDocument();
    });

    it('should render step indicator', () => {
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
        />
      );

      expect(screen.getByText('1. Select')).toBeInTheDocument();
      expect(screen.getByText('2. Target')).toBeInTheDocument();
      expect(screen.getByText('3. Preview')).toBeInTheDocument();
      expect(screen.getByText('4. Review')).toBeInTheDocument();
      expect(screen.getByText('5. Done')).toBeInTheDocument();
    });

    it('should display "Select what to migrate" heading', () => {
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
        />
      );

      expect(screen.getByText('Select what to migrate')).toBeInTheDocument();
    });

    it('should display recipes filtered for current template', () => {
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
        />
      );

      // Should show recipes for Digital Nameplate
      expect(screen.getByText('Test Recipe')).toBeInTheDocument();
      expect(screen.getByText('Another Recipe')).toBeInTheDocument();
      // Should NOT show recipe for different template
      expect(screen.queryByText('Different Template Recipe')).not.toBeInTheDocument();
    });

    it('should display Current Form Data option when form data is provided', () => {
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
          currentFormData={{ elements: { Manufacturer: { value: 'Test' } } }}
        />
      );

      expect(screen.getByText('Current Form Data')).toBeInTheDocument();
    });

    it('should not display Current Form Data option when no form data', () => {
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
        />
      );

      expect(screen.queryByText('Current Form Data')).not.toBeInTheDocument();
    });

    it('should show empty state when no artifacts available', () => {
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={[]}
        />
      );

      expect(screen.getByText(/No form data or recipes available/i)).toBeInTheDocument();
    });

    it('should navigate to target selection when recipe is clicked', async () => {
      const user = userEvent.setup();
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
        />
      );

      await user.click(screen.getByText('Test Recipe'));

      await waitFor(() => {
        expect(screen.getByText('Select target version')).toBeInTheDocument();
      });
    });

    it('should navigate to target selection when form data is clicked', async () => {
      const user = userEvent.setup();
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
          currentFormData={{ elements: {} }}
        />
      );

      await user.click(screen.getByText('Current Form Data'));

      await waitFor(() => {
        expect(screen.getByText('Select target version')).toBeInTheDocument();
      });
    });
  });

  describe('Step 2: Target Selection', () => {
    it('should display available versions', async () => {
      const user = userEvent.setup();
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
        />
      );

      // Navigate to step 2
      await user.click(screen.getByText('Test Recipe'));

      await waitFor(() => {
        expect(screen.getByText('v1.0')).toBeInTheDocument();
        expect(screen.getByText('v2.0')).toBeInTheDocument();
      });
    });

    it('should show current version indicator', async () => {
      const user = userEvent.setup();
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
        />
      );

      await user.click(screen.getByText('Test Recipe'));

      await waitFor(() => {
        expect(screen.getByText('Current')).toBeInTheDocument();
      });
    });

    it('should disable current version button', async () => {
      const user = userEvent.setup();
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
        />
      );

      await user.click(screen.getByText('Test Recipe'));

      await waitFor(() => {
        const currentVersionButton = screen.getByText('v1.0').closest('button');
        expect(currentVersionButton).toBeDisabled();
      });
    });

    it('should navigate to preview step when version is selected', async () => {
      const user = userEvent.setup();
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
        />
      );

      await user.click(screen.getByText('Test Recipe'));
      await waitFor(() => screen.getByText('Select target version'));

      await user.click(screen.getByText('v2.0'));

      await waitFor(() => {
        expect(screen.getByText('Preview Migration')).toBeInTheDocument();
      });
    });

    it('should allow navigating back to artifact selection', async () => {
      const user = userEvent.setup();
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
        />
      );

      await user.click(screen.getByText('Test Recipe'));
      await waitFor(() => screen.getByText('Select target version'));

      await user.click(screen.getByText('Back'));

      await waitFor(() => {
        expect(screen.getByText('Select what to migrate')).toBeInTheDocument();
      });
    });
  });

  describe('Step 3: Preview', () => {
    it('should show Compute Migration button', async () => {
      const user = userEvent.setup();
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
        />
      );

      await user.click(screen.getByText('Test Recipe'));
      await waitFor(() => screen.getByText('Select target version'));
      await user.click(screen.getByText('v2.0'));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Compute Migration' })).toBeInTheDocument();
      });
    });

    it('should call migrateRecipe when computing migration for recipe', async () => {
      const user = userEvent.setup();
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
        />
      );

      await user.click(screen.getByText('Test Recipe'));
      await waitFor(() => screen.getByText('Select target version'));
      await user.click(screen.getByText('v2.0'));
      await waitFor(() => screen.getByText('Preview Migration'));

      await user.click(screen.getByRole('button', { name: 'Compute Migration' }));

      await waitFor(() => {
        expect(templateOpsApi.migrateRecipe).toHaveBeenCalled();
      });
    });

    it('should call migrateFormData when computing migration for form data', async () => {
      const user = userEvent.setup();
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
          currentFormData={{ elements: { Manufacturer: { value: 'Test' } } }}
        />
      );

      await user.click(screen.getByText('Current Form Data'));
      await waitFor(() => screen.getByText('Select target version'));
      await user.click(screen.getByText('v2.0'));
      await waitFor(() => screen.getByText('Preview Migration'));

      await user.click(screen.getByRole('button', { name: 'Compute Migration' }));

      await waitFor(() => {
        expect(templateOpsApi.migrateFormData).toHaveBeenCalled();
      });
    });

    it('should navigate to review step after computing migration', async () => {
      const user = userEvent.setup();
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
        />
      );

      await user.click(screen.getByText('Test Recipe'));
      await waitFor(() => screen.getByText('Select target version'));
      await user.click(screen.getByText('v2.0'));
      await waitFor(() => screen.getByText('Preview Migration'));

      await user.click(screen.getByRole('button', { name: 'Compute Migration' }));

      await waitFor(() => {
        expect(screen.getByText('Review Migration')).toBeInTheDocument();
      });
    });
  });

  describe('Step 4: Review', () => {
    it('should display migration coverage percentage', async () => {
      const user = userEvent.setup();
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
        />
      );

      await user.click(screen.getByText('Test Recipe'));
      await waitFor(() => screen.getByText('Select target version'));
      await user.click(screen.getByText('v2.0'));
      await waitFor(() => screen.getByText('Preview Migration'));
      await user.click(screen.getByRole('button', { name: 'Compute Migration' }));

      await waitFor(() => {
        // 67% coverage from mock
        expect(screen.getByText('67%')).toBeInTheDocument();
      });
    });

    it('should display breaking changes count when present', async () => {
      const user = userEvent.setup();
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
        />
      );

      await user.click(screen.getByText('Test Recipe'));
      await waitFor(() => screen.getByText('Select target version'));
      await user.click(screen.getByText('v2.0'));
      await waitFor(() => screen.getByText('Preview Migration'));
      await user.click(screen.getByRole('button', { name: 'Compute Migration' }));

      await waitFor(() => {
        expect(screen.getByText('Breaking Changes')).toBeInTheDocument();
      });
    });

    it('should display warnings when present', async () => {
      const user = userEvent.setup();
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
        />
      );

      await user.click(screen.getByText('Test Recipe'));
      await waitFor(() => screen.getByText('Select target version'));
      await user.click(screen.getByText('v2.0'));
      await waitFor(() => screen.getByText('Preview Migration'));
      await user.click(screen.getByRole('button', { name: 'Compute Migration' }));

      await waitFor(() => {
        expect(screen.getByText('Warnings')).toBeInTheDocument();
        expect(screen.getByText('Some mappings have low confidence')).toBeInTheDocument();
      });
    });

    it('should show Apply Migration button', async () => {
      const user = userEvent.setup();
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
        />
      );

      await user.click(screen.getByText('Test Recipe'));
      await waitFor(() => screen.getByText('Select target version'));
      await user.click(screen.getByText('v2.0'));
      await waitFor(() => screen.getByText('Preview Migration'));
      await user.click(screen.getByRole('button', { name: 'Compute Migration' }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Apply Migration' })).toBeInTheDocument();
      });
    });
  });

  describe('Step 5: Complete', () => {
    it('should show completion message after applying migration', async () => {
      const user = userEvent.setup();
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
        />
      );

      await user.click(screen.getByText('Test Recipe'));
      await waitFor(() => screen.getByText('Select target version'));
      await user.click(screen.getByText('v2.0'));
      await waitFor(() => screen.getByText('Preview Migration'));
      await user.click(screen.getByRole('button', { name: 'Compute Migration' }));
      await waitFor(() => screen.getByText('Review Migration'));
      await user.click(screen.getByRole('button', { name: 'Apply Migration' }));

      await waitFor(() => {
        expect(screen.getByText('Migration Complete')).toBeInTheDocument();
      });
    });

    it('should call onMigrationComplete callback', async () => {
      const onMigrationComplete = vi.fn();
      const user = userEvent.setup();

      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
          onMigrationComplete={onMigrationComplete}
        />
      );

      await user.click(screen.getByText('Test Recipe'));
      await waitFor(() => screen.getByText('Select target version'));
      await user.click(screen.getByText('v2.0'));
      await waitFor(() => screen.getByText('Preview Migration'));
      await user.click(screen.getByRole('button', { name: 'Compute Migration' }));
      await waitFor(() => screen.getByText('Review Migration'));
      await user.click(screen.getByRole('button', { name: 'Apply Migration' }));

      expect(onMigrationComplete).toHaveBeenCalledWith(mockMigrationResult);
    });
  });

  describe('Close functionality', () => {
    it('should show close button when onClose is provided', () => {
      const onClose = vi.fn();
      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
          onClose={onClose}
        />
      );

      expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument();
    });

    it('should call onClose when close button is clicked', async () => {
      const onClose = vi.fn();
      const user = userEvent.setup();

      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
          onClose={onClose}
        />
      );

      await user.click(screen.getByRole('button', { name: 'Close' }));

      expect(onClose).toHaveBeenCalled();
    });

    it('should show Done button in complete step', async () => {
      const onClose = vi.fn();
      const user = userEvent.setup();

      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
          onClose={onClose}
        />
      );

      await user.click(screen.getByText('Test Recipe'));
      await waitFor(() => screen.getByText('Select target version'));
      await user.click(screen.getByText('v2.0'));
      await waitFor(() => screen.getByText('Preview Migration'));
      await user.click(screen.getByRole('button', { name: 'Compute Migration' }));
      await waitFor(() => screen.getByText('Review Migration'));
      await user.click(screen.getByRole('button', { name: 'Apply Migration' }));
      await waitFor(() => screen.getByText('Migration Complete'));

      expect(screen.getByRole('button', { name: 'Done' })).toBeInTheDocument();
    });
  });

  describe('Error handling', () => {
    it('should display error message when migration fails', async () => {
      vi.mocked(templateOpsApi.migrateRecipe).mockRejectedValue(
        new Error('Server error')
      );

      const user = userEvent.setup();

      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
        />
      );

      await user.click(screen.getByText('Test Recipe'));
      await waitFor(() => screen.getByText('Select target version'));
      await user.click(screen.getByText('v2.0'));
      await waitFor(() => screen.getByText('Preview Migration'));
      await user.click(screen.getByRole('button', { name: 'Compute Migration' }));

      await waitFor(() => {
        expect(screen.getByText('Server error')).toBeInTheDocument();
      });
    });

    it('should allow dismissing error message', async () => {
      vi.mocked(templateOpsApi.migrateRecipe).mockRejectedValue(
        new Error('Server error')
      );

      const user = userEvent.setup();

      render(
        <MigrationWizard
          templateName="Digital Nameplate"
          templateVersion="1.0"
          availableVersions={mockVersions}
          recipes={mockRecipes}
        />
      );

      await user.click(screen.getByText('Test Recipe'));
      await waitFor(() => screen.getByText('Select target version'));
      await user.click(screen.getByText('v2.0'));
      await waitFor(() => screen.getByText('Preview Migration'));
      await user.click(screen.getByRole('button', { name: 'Compute Migration' }));

      await waitFor(() => {
        expect(screen.getByText('Server error')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: 'Dismiss' }));

      expect(screen.queryByText('Server error')).not.toBeInTheDocument();
    });
  });
});
