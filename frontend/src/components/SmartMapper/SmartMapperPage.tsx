import { useCallback, useEffect, useMemo, useState } from 'react';
import type { UseFormReturn } from 'react-hook-form';
import localforage from 'localforage';
import type { SubmodelUISchema, UIElementSchema } from '../../types/ui-schema';
import type { SubmodelFormData } from '../../types/aas-elements';
import type {
  DatasetProfile,
  MappingItem,
  MapperDiagnostic,
  MapperModeType,
  MapperRecipe,
  MapperRunRequest,
} from '../../types/mapper';
import { profileMapperFile, runMapper } from '../../services/mapperApi';
import { isRequired } from '../../types/aas-elements';

interface SmartMapperPageProps {
  schema: SubmodelUISchema | null;
  templateName: string | null;
  templateStatus: 'published' | 'deprecated';
  templateVersion: string | null;
  form: UseFormReturn<SubmodelFormData>;
  onContinue: () => void;
}

interface TargetField {
  idShortPath: string;
  label: string;
  elementType: string;
  valueType?: string | null;
  required: boolean;
  semanticLabel?: string | null;
  languages?: string[];
}

const recipeStore = localforage.createInstance({
  name: 'idta-submodel-editor',
  storeName: 'smart-mapper-recipes',
});

function normalize(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

function tokenize(text: string): string[] {
  if (!text) return [];
  return normalize(text).split(/\s+/).filter(Boolean);
}

function scoreMatch(source: string, target: TargetField): number {
  const sourceTokens = new Set(tokenize(source));
  if (!sourceTokens.size) return 0;
  const targetTokens = new Set(
    tokenize(`${target.idShortPath} ${target.label} ${target.semanticLabel ?? ''}`)
  );
  let intersection = 0;
  sourceTokens.forEach((token) => {
    if (targetTokens.has(token)) intersection += 1;
  });
  const union = new Set([...sourceTokens, ...targetTokens]).size;
  return union ? intersection / union : 0;
}

function flattenTargets(elements: UIElementSchema[], path: string[] = []): TargetField[] {
  const targets: TargetField[] = [];
  for (const element of elements) {
    const nextPath = [...path, element.idShort];
    if (
      element.modelType === 'Property' ||
      element.modelType === 'MultiLanguageProperty' ||
      element.modelType === 'Range' ||
      element.modelType === 'File' ||
      element.modelType === 'ReferenceElement'
    ) {
      targets.push({
        idShortPath: nextPath.join('.'),
        label: element.idShort,
        elementType: element.modelType,
        valueType: element.valueType ?? null,
        required: isRequired(element.cardinality),
        semanticLabel: element.semanticLabel ?? null,
        languages: element.supportedLanguages ?? undefined,
      });
    }

    if (element.elements && element.elements.length) {
      targets.push(...flattenTargets(element.elements, nextPath));
    }
    if (element.statements && element.statements.length) {
      targets.push(...flattenTargets(element.statements, nextPath));
    }
  }
  return targets;
}

function mergeElements(
  base: Record<string, unknown>,
  patch: Record<string, unknown>
): Record<string, unknown> {
  const result: Record<string, unknown> = { ...base };
  Object.entries(patch).forEach(([key, value]) => {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      const nextBase = (base[key] as Record<string, unknown>) ?? {};
      result[key] = mergeElements(nextBase, value as Record<string, unknown>);
    } else {
      result[key] = value;
    }
  });
  return result;
}

export default function SmartMapperPage({
  schema,
  templateName,
  templateStatus,
  templateVersion,
  form,
  onContinue,
}: SmartMapperPageProps) {
  const [file, setFile] = useState<File | null>(null);
  const [profile, setProfile] = useState<DatasetProfile | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [loadingProfile, setLoadingProfile] = useState(false);
  const [mappings, setMappings] = useState<MappingItem[]>([]);
  const [autoMapped, setAutoMapped] = useState(false);
  const [mode, setMode] = useState<MapperModeType>('single');
  const [rowIndex, setRowIndex] = useState(1);
  const [diagnostics, setDiagnostics] = useState<MapperDiagnostic[]>([]);
  const [mappedFormData, setMappedFormData] = useState<Record<string, unknown> | null>(
    null
  );
  const [recipes, setRecipes] = useState<MapperRecipe[]>([]);
  const [recipeName, setRecipeName] = useState('');
  const [selectedRecipe, setSelectedRecipe] = useState<string>('');
  const [running, setRunning] = useState(false);

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

  useEffect(() => {
    recipeStore.getItem<MapperRecipe[]>('recipes').then((saved) => {
      setRecipes(saved ?? []);
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

  const handleAutoMap = useCallback(() => {
    if (!profile) return;
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
  }, [profile, targetFields]);

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
        group_by: [],
      },
      mappings,
    };
  }, [profile, templateName, templateVersion, templateStatus, recipeName, mode, mappings]);

  const handleSaveRecipe = useCallback(async () => {
    const recipe = buildRecipe();
    if (!recipe) return;
    const updated = [recipe, ...recipes.filter((r) => r.name !== recipe.name)];
    await recipeStore.setItem('recipes', updated);
    setRecipes(updated);
    setRecipeName('');
    setSelectedRecipe(recipe.name);
  }, [buildRecipe, recipes]);

  const handleApplyRecipe = useCallback(() => {
    const recipe = recipes.find((r) => r.name === selectedRecipe);
    if (!recipe || !profile) return;
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
  }, [recipes, selectedRecipe, profile]);

  const handleRun = useCallback(async () => {
    if (!profile || !templateName) return;
    const recipe = buildRecipe();
    if (!recipe) return;
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
  }, [profile, templateName, templateStatus, templateVersion, buildRecipe, rowIndex]);

  const handleApplyToForm = useCallback(() => {
    if (!mappedFormData) return;
    const current = form.getValues();
    const mergedElements = mergeElements(
      current.elements as Record<string, unknown>,
      (mappedFormData.elements as Record<string, unknown>) || {}
    );
    const nextValues = { ...current, elements: mergedElements } as SubmodelFormData;
    form.reset(nextValues);
    onContinue();
  }, [mappedFormData, form, onContinue]);

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
              {recipes.map((recipe) => (
                <option key={recipe.name} value={recipe.name}>
                  {recipe.name}
                </option>
              ))}
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
            <button
              type="button"
              className="btn btn-outline"
              onClick={handleSaveRecipe}
              disabled={!profile || mappings.length === 0}
            >
              Save recipe
            </button>
          </div>
        </div>
      </div>

      {profile && (
        <div className="smart-mapper-layout">
          <div className="smart-mapper-panel">
            <div className="smart-mapper-panel-header">
              <h3>Source Columns</h3>
              <button type="button" className="btn btn-outline" onClick={handleAutoMap}>
                Auto-map
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
                  <div key={column.index} className="smart-mapper-column">
                    <div>
                      <strong>{column.name_original}</strong>
                      <span className="smart-mapper-column-meta">
                        {column.inferred_type} · {column.examples.join(', ')}
                      </span>
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
              <h3>Target Fields</h3>
              <span>{targetFields.length} fields</span>
            </div>
            <div className="smart-mapper-target-list">
              {targetFields.map((field) => (
                <div
                  key={field.idShortPath}
                  className={`smart-mapper-target ${
                    mappedTargets.has(field.idShortPath) ? 'mapped' : ''
                  }`}
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
                <p className="smart-mapper-hint">Auto-map applied; review before running.</p>
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
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleRun}
                disabled={running || mappings.length === 0}
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
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleApplyToForm}
              >
                Apply to form
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
