import { useCallback, useEffect, useMemo, useState } from 'react';
import type { DragEvent } from 'react';
import type { UseFormReturn } from 'react-hook-form';
import type { SubmodelUISchema } from '../../types/ui-schema';
import type { SubmodelFormData } from '../../types/aas-elements';
import type {
  DatasetProfile,
  MappingItem,
  MapperDiagnostic,
  MapperModeType,
  MapperRecipe,
  MapperRunRequest,
  MapperTransform,
} from '../../types/mapper';
import {
  autoSuggestMappings,
  listMapperRecipes,
  profileMapperFile,
  runMapper,
  saveMapperRecipe,
} from '../../services/mapperApi';
import { checkVersionMismatch, type VersionMismatchCheck } from '../../services/templateOpsApi';
import type { TargetField } from './types';
import {
  flattenTargets,
  mergeElements,
  scoreMatch,
  extractPreviewEntries,
} from './mapperUtils';
import { recipeStore } from './recipeStore';
import PreviewPanel from './PreviewPanel';

interface SmartMapperPageProps {
  schema: SubmodelUISchema | null;
  templateName: string | null;
  templateStatus: 'published' | 'deprecated';
  templateVersion: string | null;
  form: UseFormReturn<SubmodelFormData>;
  onComplete?: () => void;
}

export default function SmartMapperPage({
  schema,
  templateName,
  templateStatus,
  templateVersion,
  form,
  onComplete,
}: SmartMapperPageProps) {
  const [file, setFile] = useState<File | null>(null);
  const [profile, setProfile] = useState<DatasetProfile | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [loadingProfile, setLoadingProfile] = useState(false);
  const [mappings, setMappings] = useState<MappingItem[]>([]);
  const [autoMapped, setAutoMapped] = useState(false);
  const [mode, setMode] = useState<MapperModeType>('single');
  const [groupBy, setGroupBy] = useState<string[]>([]);
  const [rowIndex, setRowIndex] = useState(1);
  const [diagnostics, setDiagnostics] = useState<MapperDiagnostic[]>([]);
  const [mappedFormData, setMappedFormData] = useState<Record<string, unknown> | null>(
    null
  );
  const [recipes, setRecipes] = useState<MapperRecipe[]>([]);
  const [serverRecipes, setServerRecipes] = useState<MapperRecipe[]>([]);
  const [serverRecipeError, setServerRecipeError] = useState<string | null>(null);
  const [recipeVersionWarning, setRecipeVersionWarning] = useState<string | null>(null);
  const [recipeName, setRecipeName] = useState('');
  const [selectedRecipe, setSelectedRecipe] = useState<string>('');
  const [draggingColumn, setDraggingColumn] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [showMigrationPrompt, setShowMigrationPrompt] = useState(false);
  const [mismatchDetails, setMismatchDetails] = useState<VersionMismatchCheck | null>(null);
  const [pendingRecipe, setPendingRecipe] = useState<MapperRecipe | null>(null);

  const targetFields = useMemo(
    () => (schema ? flattenTargets(schema.elements) : []),
    [schema]
  );

  const requiredTargets = useMemo(
    () => targetFields.filter((field) => field.required),
    [targetFields]
  );

  const mappedTargets = useMemo(
    () => new Set(mappings.map((mapping) => mapping.target.id_short_path)),
    [mappings]
  );

  const unmappedRequired = useMemo(
    () =>
      requiredTargets.filter((target) => !mappedTargets.has(target.idShortPath)),
    [requiredTargets, mappedTargets]
  );

  const canRun = mappings.length > 0 && (mode !== 'grouped' || groupBy.length > 0);

  // Extract preview entries from mapped form data for dry-run display
  const previewEntries = useMemo(
    () => extractPreviewEntries(mappedFormData),
    [mappedFormData]
  );

  useEffect(() => {
    recipeStore.getItem<MapperRecipe[]>('recipes').then((saved) => {
      setRecipes(saved ?? []);
    });
    listMapperRecipes()
      .then((saved) => {
        setServerRecipes(saved ?? []);
        setServerRecipeError(null);
      })
      .catch((err: unknown) => {
        const message =
          err instanceof Error ? err.message : 'Server recipes unavailable';
        setServerRecipeError(message);
      });
  }, []);

  const handleProfile = useCallback(async () => {
    if (!file) return;
    setLoadingProfile(true);
    setProfileError(null);
    setProfile(null);
    setMappings([]);
    setDiagnostics([]);
    setMappedFormData(null);
    setAutoMapped(false);
    setGroupBy([]);
    setRecipeVersionWarning(null);
    setSemanticStats(null);

    try {
      const result = await profileMapperFile(file, { sampleRows: 200 });
      setProfile(result);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to profile file';
      setProfileError(message);
    } finally {
      setLoadingProfile(false);
    }
  }, [file]);

  const handleMappingChange = useCallback(
    (columnName: string, columnIndex: number, targetId: string | null) => {
      setMappings((prev) => {
        const filtered = prev.filter(
          (mapping) => mapping.source.column_name !== columnName
        );
        if (!targetId) return filtered;
        const target = targetFields.find((field) => field.idShortPath === targetId);
        if (!target) return filtered;
        return [
          ...filtered,
          {
            source: { column_name: columnName, column_index: columnIndex },
            target: {
              id_short_path: target.idShortPath,
              element_type: target.elementType,
              value_type: target.valueType ?? null,
            },
            required: target.required,
          },
        ];
      });
    },
    [targetFields]
  );

  const handleTargetField = useCallback(
    (columnName: string, targetPatch: Partial<MappingItem['target']>) => {
      setMappings((prev) =>
        prev.map((mapping) =>
          mapping.source.column_name === columnName
            ? { ...mapping, target: { ...mapping.target, ...targetPatch } }
            : mapping
        )
      );
    },
    []
  );

  const toggleGroupBy = useCallback((columnName: string) => {
    setGroupBy((prev) =>
      prev.includes(columnName)
        ? prev.filter((name) => name !== columnName)
        : [...prev, columnName]
    );
  }, []);

  const handleDragStart = useCallback(
    (columnName: string, columnIndex: number) =>
      (event: DragEvent<HTMLDivElement>) => {
        event.dataTransfer.setData(
          'application/json',
          JSON.stringify({ columnName, columnIndex })
        );
        event.dataTransfer.effectAllowed = 'copy';
        setDraggingColumn(columnName);
      },
    []
  );

  const handleDragEnd = useCallback(() => {
    setDraggingColumn(null);
  }, []);

  const handleDropOnTarget = useCallback(
    (targetId: string) => (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      const payload = event.dataTransfer.getData('application/json');
      if (!payload) return;
      try {
        const { columnName, columnIndex } = JSON.parse(payload) as {
          columnName: string;
          columnIndex: number;
        };
        handleMappingChange(columnName, columnIndex, targetId);
      } catch {
        // Ignore malformed drag data.
      } finally {
        setDraggingColumn(null);
      }
    },
    [handleMappingChange]
  );

  const removeMapping = useCallback((columnName: string) => {
    setMappings((prev) =>
      prev.filter((mapping) => mapping.source.column_name !== columnName)
    );
  }, []);

  const [expandedTransform, setExpandedTransform] = useState<string | null>(null);

  const toggleTransformExpanded = useCallback((columnName: string) => {
    setExpandedTransform((prev) => (prev === columnName ? null : columnName));
  }, []);

  const handleTransformUpdate = useCallback(
    (columnName: string, transformPatch: Partial<MapperTransform>) => {
      setMappings((prev) =>
        prev.map((mapping) =>
          mapping.source.column_name === columnName
            ? {
                ...mapping,
                transform: { ...(mapping.transform ?? {}), ...transformPatch },
              }
            : mapping
        )
      );
    },
    []
  );

  const [autoMapLoading, setAutoMapLoading] = useState(false);
  const [semanticStats, setSemanticStats] = useState<{
    resolved: number;
    errors: number;
  } | null>(null);

  const handleAutoMap = useCallback(async () => {
    if (!profile || !templateName) return;
    setAutoMapLoading(true);
    setSemanticStats(null);

    try {
      // Use server-side semantic-aware auto-suggest
      const response = await autoSuggestMappings({
        template_name: templateName,
        status: templateStatus,
        version: templateVersion ?? undefined,
        profile_id: profile.profile_id,
        use_semantics: true,
        min_confidence: 0.3,
      });

      // Convert suggestions to mappings
      const newMappings: MappingItem[] = response.suggestions.map((suggestion) => {
        const targetInfo = response.target_fields.find(
          (f) => f.id_short_path === suggestion.target_path
        );
        return {
          source: {
            column_name: suggestion.source_column,
            column_index: suggestion.source_index,
          },
          target: {
            id_short_path: suggestion.target_path,
            element_type: suggestion.target_type,
            value_type: suggestion.target_value_type ?? null,
          },
          required: targetInfo?.required ?? false,
        };
      });

      setMappings(newMappings);
      setAutoMapped(true);
      setSemanticStats({
        resolved: response.semantic_resolved,
        errors: response.semantic_errors,
      });
    } catch (err) {
      // Fallback to client-side matching if server fails
      console.warn('Server auto-suggest failed, using client-side fallback:', err);
      const newMappings: MappingItem[] = [];
      profile.columns.forEach((column) => {
        let best: { score: number; target: TargetField | null } = {
          score: 0,
          target: null,
        };
        targetFields.forEach((target) => {
          const score = scoreMatch(column.name_original, target);
          if (score > best.score) {
            best = { score, target };
          }
        });
        if (best.target && best.score >= 0.45) {
          newMappings.push({
            source: { column_name: column.name_original, column_index: column.index },
            target: {
              id_short_path: best.target.idShortPath,
              element_type: best.target.elementType,
              value_type: best.target.valueType ?? null,
            },
            required: best.target.required,
          });
        }
      });
      setMappings(newMappings);
      setAutoMapped(true);
    } finally {
      setAutoMapLoading(false);
    }
  }, [profile, templateName, templateStatus, templateVersion, targetFields]);

  const buildRecipe = useCallback((): MapperRecipe | null => {
    if (!profile || !templateName) return null;
    const fingerprint = profile.columns.map((col) => col.name_normalized).join('|');
    return {
      name: recipeName || `Recipe ${new Date().toLocaleDateString()}`,
      schema_version: '1.0.0',
      template: {
        name: templateName,
        version: templateVersion ?? null,
        status: templateStatus,
      },
      source_profile: {
        format: profile.file.name.toLowerCase().endsWith('.xlsx') ? 'xlsx' : 'csv',
        sheet: profile.sheets?.[0]?.name ?? null,
        header_row: profile.header_row,
        header_fingerprint: fingerprint,
      },
      mode: {
        type: mode,
        group_by: mode === 'grouped' ? groupBy : [],
      },
      mappings,
    };
  }, [
    profile,
    templateName,
    templateVersion,
    templateStatus,
    recipeName,
    mode,
    groupBy,
    mappings,
  ]);

  const formatRecipeId = useCallback(
    (source: 'local' | 'server', name: string) => `${source}::${name}`,
    []
  );

  const parseRecipeId = useCallback((value: string) => {
    const [source, ...rest] = value.split('::');
    return { source, name: rest.join('::') };
  }, []);

  const handleSaveRecipe = useCallback(async () => {
    const recipe = buildRecipe();
    if (!recipe) return;
    const updated = [recipe, ...recipes.filter((r) => r.name !== recipe.name)];
    await recipeStore.setItem('recipes', updated);
    setRecipes(updated);
    setRecipeName('');
    setSelectedRecipe(formatRecipeId('local', recipe.name));
  }, [buildRecipe, recipes, formatRecipeId]);

  const handleSaveRecipeToServer = useCallback(async () => {
    const recipe = buildRecipe();
    if (!recipe) return;
    try {
      const saved = await saveMapperRecipe(recipe);
      setServerRecipes((prev) => [
        saved,
        ...prev.filter((r) => r.name !== saved.name),
      ]);
      setServerRecipeError(null);
      setRecipeName('');
      setSelectedRecipe(formatRecipeId('server', saved.name));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Save to server failed';
      setServerRecipeError(message);
    }
  }, [buildRecipe, formatRecipeId]);

  // Helper function to apply a recipe to the current mappings
  const applyRecipeToMappings = useCallback(
    (recipe: MapperRecipe) => {
      if (!profile) return;

      setMode(recipe.mode.type);
      setGroupBy(recipe.mode.group_by ?? []);
      const columnIndexByName = new Map(
        profile.columns.map((col) => [col.name_original, col.index])
      );
      const applied: MappingItem[] = recipe.mappings
        .map((mapping) => {
          const columnIndex = columnIndexByName.get(mapping.source.column_name);
          if (columnIndex === undefined) return null;
          return {
            ...mapping,
            source: {
              column_name: mapping.source.column_name,
              column_index: columnIndex,
            },
          };
        })
        .filter(Boolean) as MappingItem[];
      setMappings(applied);
    },
    [profile]
  );

  const handleApplyRecipe = useCallback(async () => {
    if (!selectedRecipe || !templateName) return;
    const parsed = parseRecipeId(selectedRecipe);
    const source = parsed.source === 'server' ? serverRecipes : recipes;
    const recipe = source.find((r) => r.name === parsed.name);
    if (!recipe || !profile) return;

    // Reset warnings
    setRecipeVersionWarning(null);
    setShowMigrationPrompt(false);
    setMismatchDetails(null);
    setPendingRecipe(null);

    // Check for schema digest mismatch (more precise than version check)
    if (recipe.template.schema_digest) {
      try {
        const check = await checkVersionMismatch({
          artifact_type: 'recipe',
          created_for_digest: recipe.template.schema_digest,
          template_name: templateName,
          template_version: templateVersion ?? undefined,
          template_status: templateStatus,
        });

        if (check.has_mismatch) {
          // Show migration prompt dialog
          setMismatchDetails(check);
          setPendingRecipe(recipe);
          setShowMigrationPrompt(true);
          return; // Don't apply yet - wait for user decision
        }
      } catch (err) {
        // If check fails, fall through to version-based warning
        console.warn('Schema digest check failed:', err);
      }
    }

    // Fallback: Check for template version mismatch (legacy behavior)
    if (recipe.template.version && templateVersion) {
      if (recipe.template.version !== templateVersion) {
        setRecipeVersionWarning(
          `Recipe was created for template version "${recipe.template.version}" ` +
            `but current version is "${templateVersion}". ` +
            `Field paths may have changed.`
        );
      }
    } else if (recipe.template.version && !templateVersion) {
      setRecipeVersionWarning(
        `Recipe was created for template version "${recipe.template.version}" ` +
          `but current template version is unknown.`
      );
    }

    applyRecipeToMappings(recipe);
  }, [
    recipes,
    serverRecipes,
    selectedRecipe,
    profile,
    parseRecipeId,
    templateName,
    templateVersion,
    templateStatus,
    applyRecipeToMappings,
  ]);

  // Handler for when user chooses to apply recipe anyway despite mismatch
  const handleApplyAnyway = useCallback(() => {
    if (pendingRecipe) {
      setRecipeVersionWarning(
        'Recipe was created for a different template schema. Some mappings may be invalid.'
      );
      applyRecipeToMappings(pendingRecipe);
    }
    setShowMigrationPrompt(false);
    setMismatchDetails(null);
    setPendingRecipe(null);
  }, [pendingRecipe, applyRecipeToMappings]);

  // Handler for when user dismisses the mismatch dialog
  const handleDismissMismatch = useCallback(() => {
    setShowMigrationPrompt(false);
    setMismatchDetails(null);
    setPendingRecipe(null);
  }, []);

  const handleRun = useCallback(async () => {
    if (!profile || !templateName) return;
    const recipe = buildRecipe();
    if (!recipe) return;
    if (mode === 'grouped' && groupBy.length === 0) {
      setDiagnostics([
        {
          severity: 'error',
          message: 'Select at least one group-by column before running.',
        },
      ] as MapperDiagnostic[]);
      return;
    }
    setRunning(true);
    setDiagnostics([]);
    setMappedFormData(null);
    try {
      const payload: MapperRunRequest = {
        template_name: templateName,
        status: templateStatus,
        version: templateVersion ?? null,
        profile_id: profile.profile_id,
        recipe,
        output_format: 'form',
        row_index: rowIndex,
      };
      const result = await runMapper(payload);
      setDiagnostics(result.diagnostics ?? []);
      if (result.form_data) {
        setMappedFormData(result.form_data as Record<string, unknown>);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Mapper run failed';
      setDiagnostics([
        {
          severity: 'error',
          message,
        },
      ] as MapperDiagnostic[]);
    } finally {
      setRunning(false);
    }
  }, [
    profile,
    templateName,
    templateStatus,
    templateVersion,
    buildRecipe,
    rowIndex,
    mode,
    groupBy,
  ]);

  const handleApplyToForm = useCallback(() => {
    if (!mappedFormData) return;
    const current = form.getValues();
    const mergedElements = mergeElements(
      current.elements as Record<string, unknown>,
      (mappedFormData.elements as Record<string, unknown>) || {}
    );
    const nextValues = { ...current, elements: mergedElements } as SubmodelFormData;
    form.reset(nextValues);
    onComplete?.();
  }, [mappedFormData, form, onComplete]);

  return (
    <div className="wizard-panel smart-mapper">
      <div className="wizard-panel-header">
        <h2>Smart Mapper</h2>
        <p>Import CSV/XLSX data, map columns to template fields, and apply in one pass.</p>
      </div>

      <div className="smart-mapper-upload">
        <div className="smart-mapper-upload-card">
          <label htmlFor="smart-mapper-file" className="smart-mapper-upload-label">
            Upload CSV/XLSX
          </label>
          <input
            id="smart-mapper-file"
            type="file"
            accept=".csv,.xlsx"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleProfile}
            disabled={!file || loadingProfile}
          >
            {loadingProfile ? 'Profiling…' : 'Profile file'}
          </button>
          {profileError && <p className="smart-mapper-error">{profileError}</p>}
          {profile && (
            <p className="smart-mapper-meta">
              {profile.file.name} · {profile.columns.length} columns ·{' '}
              {profile.sample_rows.length} sample rows
            </p>
          )}
        </div>

        <div className="smart-mapper-recipe-card">
          <div className="smart-mapper-recipe-header">
            <h3>Recipes</h3>
            <p>Save mappings for repeat imports.</p>
          </div>
          <div className="smart-mapper-recipe-controls">
            <select
              value={selectedRecipe}
              onChange={(event) => setSelectedRecipe(event.target.value)}
            >
              <option value="">Select saved recipe</option>
              {serverRecipes.length > 0 && (
                <optgroup label="Server recipes">
                  {serverRecipes.map((recipe) => (
                    <option
                      key={`server-${recipe.name}`}
                      value={formatRecipeId('server', recipe.name)}
                    >
                      {recipe.name}
                    </option>
                  ))}
                </optgroup>
              )}
              {recipes.length > 0 && (
                <optgroup label="Local recipes">
                  {recipes.map((recipe) => (
                    <option
                      key={`local-${recipe.name}`}
                      value={formatRecipeId('local', recipe.name)}
                    >
                      {recipe.name}
                    </option>
                  ))}
                </optgroup>
              )}
            </select>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleApplyRecipe}
              disabled={!selectedRecipe || !profile}
            >
              Apply recipe
            </button>
          </div>
          <div className="smart-mapper-recipe-save">
            <input
              type="text"
              placeholder="Recipe name"
              value={recipeName}
              onChange={(event) => setRecipeName(event.target.value)}
            />
            <div className="smart-mapper-recipe-actions">
              <button
                type="button"
                className="btn btn-outline"
                onClick={handleSaveRecipe}
                disabled={!profile || mappings.length === 0}
              >
                Save locally
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleSaveRecipeToServer}
                disabled={!profile || mappings.length === 0}
              >
                Save to server
              </button>
            </div>
            {serverRecipeError && (
              <p className="smart-mapper-hint">{serverRecipeError}</p>
            )}
            {recipeVersionWarning && (
              <div className="smart-mapper-warning">{recipeVersionWarning}</div>
            )}
          </div>
        </div>
      </div>

      {/* Schema Mismatch Warning Dialog */}
      {showMigrationPrompt && mismatchDetails && (
        <div className="smart-mapper-dialog-overlay">
          <div className="smart-mapper-dialog">
            <div className="smart-mapper-dialog-header">
              <h3>Template Schema Changed</h3>
            </div>
            <div className="smart-mapper-dialog-content">
              <p>
                This recipe was created for a different version of the template schema.
                Some field mappings may no longer be valid.
              </p>
              {mismatchDetails.breaking_changes_detected && (
                <div className="smart-mapper-warning">
                  <strong>Breaking changes detected.</strong> Some fields may have been
                  renamed, removed, or changed type.
                </div>
              )}
              {mismatchDetails.affected_paths.length > 0 && (
                <div className="smart-mapper-affected-paths">
                  <strong>Affected fields:</strong>
                  <ul>
                    {mismatchDetails.affected_paths.slice(0, 5).map((path) => (
                      <li key={path}>{path}</li>
                    ))}
                    {mismatchDetails.affected_paths.length > 5 && (
                      <li>...and {mismatchDetails.affected_paths.length - 5} more</li>
                    )}
                  </ul>
                </div>
              )}
              <p className="smart-mapper-hint">
                You can apply the recipe anyway, but some mappings may fail.
                Consider using the Template Operations tool to migrate the recipe
                to the new schema.
              </p>
            </div>
            <div className="smart-mapper-dialog-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleDismissMismatch}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleApplyAnyway}
              >
                Apply Anyway
              </button>
            </div>
          </div>
        </div>
      )}

      {profile && (
        <div className="smart-mapper-layout">
          <div className="smart-mapper-panel">
            <div className="smart-mapper-panel-header">
              <h3>Source Columns</h3>
              <button
                type="button"
                className="btn btn-outline"
                onClick={handleAutoMap}
                disabled={autoMapLoading}
              >
                {autoMapLoading ? 'Auto-mapping…' : 'Auto-map'}
              </button>
            </div>
            <div className="smart-mapper-column-list">
              {profile.columns.map((column) => {
                const selected = mappings.find(
                  (mapping) => mapping.source.column_name === column.name_original
                );
                const target = targetFields.find(
                  (field) => field.idShortPath === selected?.target.id_short_path
                );
                return (
                  <div
                    key={column.index}
                    className={`smart-mapper-column ${
                      draggingColumn === column.name_original ? 'dragging' : ''
                    }`}
                  >
                    <div
                      className="smart-mapper-column-header"
                      draggable
                      onDragStart={handleDragStart(column.name_original, column.index)}
                      onDragEnd={handleDragEnd}
                    >
                      <div className="smart-mapper-column-title">
                        <strong>{column.name_original}</strong>
                        <span className="smart-mapper-column-type">{column.inferred_type}</span>
                      </div>
                      <div className="smart-mapper-column-stats">
                        <span
                          className={`smart-mapper-stat ${column.null_rate > 0.2 ? 'warning' : ''}`}
                          title="Null/empty rate"
                        >
                          {(column.null_rate * 100).toFixed(0)}% empty
                        </span>
                        <span className="smart-mapper-stat" title="Distinct values">
                          {column.distinct_count} unique
                        </span>
                      </div>
                      <span className="smart-mapper-column-meta">
                        {column.examples.slice(0, 3).join(', ')}
                        {column.examples.length > 3 && '…'}
                      </span>
                      <span className="smart-mapper-column-hint">Drag to map</span>
                    </div>
                    <select
                      value={selected?.target.id_short_path ?? ''}
                      onChange={(event) =>
                        handleMappingChange(
                          column.name_original,
                          column.index,
                          event.target.value || null
                        )
                      }
                    >
                      <option value="">Unmapped</option>
                      {targetFields.map((field) => (
                        <option key={field.idShortPath} value={field.idShortPath}>
                          {field.idShortPath}
                        </option>
                      ))}
                    </select>
                    {target?.elementType === 'MultiLanguageProperty' && (
                      <select
                        value={selected?.target.language ?? 'en'}
                        onChange={(event) =>
                          handleTargetField(column.name_original, {
                            language: event.target.value,
                          })
                        }
                      >
                        {(target.languages ?? ['en']).map((lang) => (
                          <option key={lang} value={lang}>
                            {lang}
                          </option>
                        ))}
                      </select>
                    )}
                    {target?.elementType === 'Range' && (
                      <select
                        value={selected?.target.field ?? 'min'}
                        onChange={(event) =>
                          handleTargetField(column.name_original, {
                            field: event.target.value,
                          })
                        }
                      >
                        <option value="min">min</option>
                        <option value="max">max</option>
                      </select>
                    )}
                    {target?.elementType === 'File' && (
                      <select
                        value={selected?.target.field ?? 'value'}
                        onChange={(event) =>
                          handleTargetField(column.name_original, {
                            field: event.target.value,
                          })
                        }
                      >
                        <option value="value">File path / URL</option>
                        <option value="contentType">Content type</option>
                      </select>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="smart-mapper-panel">
            <div className="smart-mapper-panel-header">
              <h3>Mapping Canvas</h3>
              <span>{mappings.length} mappings</span>
            </div>
            <div className="smart-mapper-canvas">
              {mappings.length === 0 ? (
                <p className="smart-mapper-hint">
                  Drag a column onto a target to create a mapping.
                </p>
              ) : (
                <div className="smart-mapper-canvas-list">
                  {mappings.map((mapping) => {
                    const isExpanded =
                      expandedTransform === mapping.source.column_name;
                    const transform = mapping.transform ?? {};
                    const hasTransform =
                      transform.decimal ||
                      transform.thousands ||
                      transform.date_format ||
                      transform.default_value ||
                      transform.trim === false;

                    return (
                      <div
                        key={mapping.source.column_name}
                        className={`smart-mapper-canvas-row ${isExpanded ? 'expanded' : ''}`}
                      >
                        <div className="smart-mapper-canvas-row-header">
                          <span>
                            <strong>{mapping.source.column_name}</strong> →{' '}
                            {mapping.target.id_short_path}
                            {hasTransform && (
                              <span className="smart-mapper-transform-badge">⚙</span>
                            )}
                          </span>
                          <div className="smart-mapper-canvas-row-actions">
                            <button
                              type="button"
                              className="btn btn-sm btn-ghost"
                              onClick={() =>
                                toggleTransformExpanded(mapping.source.column_name)
                              }
                              title="Transform options"
                            >
                              {isExpanded ? '▼' : '▶'}
                            </button>
                            <button
                              type="button"
                              className="btn btn-outline"
                              onClick={() => removeMapping(mapping.source.column_name)}
                            >
                              Remove
                            </button>
                          </div>
                        </div>
                        {isExpanded && (
                          <div className="smart-mapper-transform-options">
                            <div className="smart-mapper-transform-row">
                              <label>
                                <input
                                  type="checkbox"
                                  checked={transform.trim !== false}
                                  onChange={(e) =>
                                    handleTransformUpdate(mapping.source.column_name, {
                                      trim: e.target.checked,
                                    })
                                  }
                                />
                                Trim whitespace
                              </label>
                            </div>
                            <div className="smart-mapper-transform-row">
                              <label>
                                Default value
                                <input
                                  type="text"
                                  placeholder="If empty..."
                                  value={transform.default_value ?? ''}
                                  onChange={(e) =>
                                    handleTransformUpdate(mapping.source.column_name, {
                                      default_value: e.target.value || null,
                                    })
                                  }
                                />
                              </label>
                            </div>
                            {(mapping.target.value_type?.includes('int') ||
                              mapping.target.value_type?.includes('float') ||
                              mapping.target.value_type?.includes('double') ||
                              mapping.target.value_type?.includes('decimal')) && (
                              <>
                                <div className="smart-mapper-transform-row">
                                  <label>
                                    Decimal separator
                                    <select
                                      value={transform.decimal ?? '.'}
                                      onChange={(e) =>
                                        handleTransformUpdate(
                                          mapping.source.column_name,
                                          { decimal: e.target.value }
                                        )
                                      }
                                    >
                                      <option value=".">. (period)</option>
                                      <option value=",">, (comma)</option>
                                    </select>
                                  </label>
                                </div>
                                <div className="smart-mapper-transform-row">
                                  <label>
                                    Thousands separator
                                    <select
                                      value={transform.thousands ?? ''}
                                      onChange={(e) =>
                                        handleTransformUpdate(
                                          mapping.source.column_name,
                                          { thousands: e.target.value || null }
                                        )
                                      }
                                    >
                                      <option value="">None</option>
                                      <option value=",">, (comma)</option>
                                      <option value=".">. (period)</option>
                                      <option value=" ">Space</option>
                                    </select>
                                  </label>
                                </div>
                              </>
                            )}
                            {mapping.target.value_type?.includes('date') && (
                              <div className="smart-mapper-transform-row">
                                <label>
                                  Date format
                                  <select
                                    value={transform.date_format ?? ''}
                                    onChange={(e) =>
                                      handleTransformUpdate(mapping.source.column_name, {
                                        date_format: e.target.value || null,
                                      })
                                    }
                                  >
                                    <option value="">Auto (ISO 8601)</option>
                                    <option value="%Y-%m-%d">YYYY-MM-DD</option>
                                    <option value="%d.%m.%Y">DD.MM.YYYY</option>
                                    <option value="%m/%d/%Y">MM/DD/YYYY</option>
                                    <option value="%d/%m/%Y">DD/MM/YYYY</option>
                                    <option value="%Y%m%d">YYYYMMDD</option>
                                  </select>
                                </label>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
            <div className="smart-mapper-panel-header">
              <h3>Target Fields</h3>
              <span>{targetFields.length} fields</span>
            </div>
            <div className="smart-mapper-target-list">
              {targetFields.map((field) => (
                <div
                  key={field.idShortPath}
                  className={`smart-mapper-target ${
                    mappedTargets.has(field.idShortPath) ? 'mapped' : ''
                  } ${draggingColumn ? 'droppable' : ''}`}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={handleDropOnTarget(field.idShortPath)}
                >
                  <div>
                    <strong>{field.idShortPath}</strong>
                    <span className="smart-mapper-column-meta">
                      {field.elementType}
                      {field.valueType ? ` · ${field.valueType}` : ''}
                    </span>
                  </div>
                  {field.required && <span className="badge">Required</span>}
                </div>
              ))}
            </div>
          </div>

          <div className="smart-mapper-panel">
            <div className="smart-mapper-panel-header">
              <h3>Validation</h3>
            </div>
            <div className="smart-mapper-validation">
              <div className="smart-mapper-validation-row">
                <span>Mapped fields</span>
                <strong>{mappings.length}</strong>
              </div>
              <div className="smart-mapper-validation-row">
                <span>Required fields unmapped</span>
                <strong>{unmappedRequired.length}</strong>
              </div>
              {autoMapped && (
                <p className="smart-mapper-hint">
                  Auto-map applied
                  {semanticStats && semanticStats.resolved > 0 && (
                    <> · {semanticStats.resolved} semantic IDs resolved</>
                  )}
                  ; review before running.
                </p>
              )}
              {unmappedRequired.length > 0 && (
                <div className="smart-mapper-warning">
                  Unmapped required fields: {unmappedRequired
                    .slice(0, 6)
                    .map((t) => t.label)
                    .join(', ')}
                  {unmappedRequired.length > 6 ? '…' : ''}
                </div>
              )}
            </div>

            <div className="smart-mapper-run">
              <div className="smart-mapper-run-controls">
                <label>
                  Import mode
                  <select
                    value={mode}
                    onChange={(e) => setMode(e.target.value as MapperModeType)}
                  >
                    <option value="single">Single instance</option>
                    <option value="row-per-submodel">Row-per-submodel</option>
                    <option value="grouped">Grouped rows (list items)</option>
                  </select>
                </label>
                {mode === 'single' && (
                  <label>
                    Row index
                    <input
                      type="number"
                      min={1}
                      value={rowIndex}
                      onChange={(e) => setRowIndex(Number(e.target.value))}
                    />
                  </label>
                )}
              </div>
              {mode === 'grouped' && (
                <div className="smart-mapper-groupby">
                  <span>Group by columns</span>
                  <div className="smart-mapper-groupby-list">
                    {profile.columns.map((column) => (
                      <label key={column.index}>
                        <input
                          type="checkbox"
                          checked={groupBy.includes(column.name_original)}
                          onChange={() => toggleGroupBy(column.name_original)}
                        />
                        {column.name_original}
                      </label>
                    ))}
                  </div>
                  {groupBy.length === 0 && (
                    <p className="smart-mapper-hint">
                      Select at least one column to group rows into list items.
                    </p>
                  )}
                </div>
              )}
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleRun}
                disabled={running || !canRun}
              >
                {running ? 'Running…' : 'Run mapping'}
              </button>
            </div>

            {diagnostics.length > 0 && (
              <div className="smart-mapper-diagnostics">
                {diagnostics.map((diag, idx) => (
                  <div key={`${diag.code}-${idx}`} className={`diag ${diag.severity}`}>
                    <strong>{diag.severity.toUpperCase()}</strong> {diag.message}
                    {diag.target_path ? ` · ${diag.target_path}` : ''}
                    {diag.row_index ? ` (row ${diag.row_index})` : ''}
                  </div>
                ))}
              </div>
            )}

            {mappedFormData && (
              <PreviewPanel entries={previewEntries} onApply={handleApplyToForm} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
