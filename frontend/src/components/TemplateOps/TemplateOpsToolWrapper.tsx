/**
 * TemplateOpsToolWrapper - Adapter for TemplateOpsPanel to fit ToolComponentProps.
 *
 * The ToolShell passes ToolComponentProps (templateName, form, schema, etc.)
 * but TemplateOpsPanel has a broader interface. This wrapper bridges the gap.
 */

import { useState, useEffect } from 'react';
import type { UseFormReturn } from 'react-hook-form';
import type { SubmodelFormData } from '../../types/aas-elements';
import type { SubmodelUISchema, TemplateInfo } from '../../types/ui-schema';
import { listTemplates, getTemplateVersions } from '../../services/api';
import { listMapperRecipes } from '../../services/mapperApi';
import TemplateOpsPanel from './TemplateOpsPanel';

interface TemplateOpsToolWrapperProps {
  templateName: string;
  templateStatus: 'published' | 'deprecated' | 'local';
  templateVersion: string | null;
  form: UseFormReturn<SubmodelFormData>;
  schema: SubmodelUISchema | null;
  onComplete?: () => void;
  onNavigate?: (step: number) => void;
}

export default function TemplateOpsToolWrapper({
  templateName,
  templateStatus,
  templateVersion,
  form,
  schema,
  onComplete,
}: TemplateOpsToolWrapperProps) {
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [recipes, setRecipes] = useState<
    Array<{ name: string; template: { name: string; version?: string | null } }>
  >([]);
  const [availableVersions, setAvailableVersions] = useState<
    Array<{ version: string; status: string }>
  >([]);
  const [loading, setLoading] = useState(true);

  // Suppress unused variable warning
  void schema;

  // Load templates, recipes, and versions on mount
  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        // Load templates list
        const templatesResp = await listTemplates();
        setTemplates(templatesResp.templates || []);

        // Load recipes
        try {
          const recipesResp = await listMapperRecipes();
          setRecipes(
            recipesResp.map((r) => ({
              name: r.name,
              template: {
                name: r.template.name,
                version: r.template.version,
              },
            }))
          );
        } catch {
          // Recipes API might fail if no recipes exist
          setRecipes([]);
        }

        // Load versions for current template
        if (templateName && templateStatus !== 'local') {
          try {
            const versions = await getTemplateVersions(templateName, templateStatus);
            setAvailableVersions(
              versions.map((v) => ({
                version: v.version,
                status: 'published', // TemplateVersionInfo doesn't have status
              }))
            );
          } catch {
            setAvailableVersions([]);
          }
        } else {
          setAvailableVersions([]);
        }
      } catch (err) {
        console.error('Failed to load template ops data:', err);
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [templateName, templateStatus]);

  if (loading) {
    return (
      <div className="template-ops-loading">
        <div className="template-ops-loading__spinner" />
        <p>Loading template operations...</p>
      </div>
    );
  }

  return (
    <TemplateOpsPanel
      templates={templates}
      selectedTemplate={templateName}
      selectedVersion={templateVersion ?? undefined}
      selectedStatus={templateStatus}
      availableVersions={availableVersions}
      recipes={recipes}
      currentFormData={form.getValues() as unknown as Record<string, unknown>}
      onRecipeMigrated={(result) => {
        console.log('Recipe migrated:', result);
        // Could save the migrated recipe or trigger a refresh
      }}
      onFormMigrated={(result) => {
        if (result.migrated_form_data) {
          // Apply migrated form data
          form.reset(result.migrated_form_data as unknown as SubmodelFormData);
        }
      }}
      onClose={onComplete}
    />
  );
}
