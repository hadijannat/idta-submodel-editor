/**
 * MappingTable - Displays migration mappings with review/override capability.
 */

import { useState, useCallback } from 'react';
import type { MappingMigrationItem } from '../../services/templateOpsApi';
import MigrationConfidenceBadge from './MigrationConfidenceBadge';
import './TemplateOps.css';

interface MappingTableProps {
  mappings: MappingMigrationItem[];
  availableTargets?: string[];
  onOverride?: (originalPath: string, newTargetPath: string | null) => void;
  readonly?: boolean;
}

export default function MappingTable({
  mappings,
  availableTargets = [],
  onOverride,
  readonly = false,
}: MappingTableProps) {
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [overrideValues, setOverrideValues] = useState<Record<string, string>>({});

  const handleToggleRow = useCallback((path: string) => {
    setExpandedRow((prev) => (prev === path ? null : path));
  }, []);

  const handleOverrideChange = useCallback(
    (originalPath: string, newValue: string) => {
      setOverrideValues((prev) => ({ ...prev, [originalPath]: newValue }));
    },
    []
  );

  const handleApplyOverride = useCallback(
    (originalPath: string) => {
      const newTarget = overrideValues[originalPath];
      if (onOverride) {
        onOverride(originalPath, newTarget === '' ? null : newTarget);
      }
    },
    [overrideValues, onOverride]
  );

  // Sort mappings: unmapped first, then by confidence ascending
  const sortedMappings = [...mappings].sort((a, b) => {
    if (a.match_reason === 'unmapped' && b.match_reason !== 'unmapped') return -1;
    if (a.match_reason !== 'unmapped' && b.match_reason === 'unmapped') return 1;
    return a.confidence - b.confidence;
  });

  const unmappedCount = mappings.filter((m) => m.match_reason === 'unmapped').length;
  const breakingCount = mappings.filter((m) => m.breaking_change).length;

  return (
    <div className="mapping-table-container">
      <div className="mapping-table-summary">
        <span className="mapping-table-summary__stat">
          {mappings.length} mapping{mappings.length !== 1 ? 's' : ''}
        </span>
        {unmappedCount > 0 && (
          <span className="mapping-table-summary__stat mapping-table-summary__stat--warning">
            {unmappedCount} unmapped
          </span>
        )}
        {breakingCount > 0 && (
          <span className="mapping-table-summary__stat mapping-table-summary__stat--error">
            {breakingCount} breaking
          </span>
        )}
      </div>

      <table className="mapping-table">
        <thead>
          <tr>
            <th>Original Path</th>
            <th>Migrated Path</th>
            <th>Confidence</th>
            {!readonly && <th>Override</th>}
          </tr>
        </thead>
        <tbody>
          {sortedMappings.map((mapping) => {
            const isExpanded = expandedRow === mapping.original_path;
            const hasOverride = overrideValues[mapping.original_path] !== undefined;

            return (
              <tr
                key={mapping.original_path}
                className={`mapping-table__row ${
                  mapping.match_reason === 'unmapped'
                    ? 'mapping-table__row--unmapped'
                    : mapping.breaking_change
                      ? 'mapping-table__row--breaking'
                      : ''
                }`}
              >
                <td className="mapping-table__cell mapping-table__cell--path">
                  <button
                    type="button"
                    className="mapping-table__toggle"
                    onClick={() => handleToggleRow(mapping.original_path)}
                    aria-expanded={isExpanded}
                  >
                    {isExpanded ? '▼' : '▶'}
                  </button>
                  <code>{mapping.original_path}</code>
                  {isExpanded && mapping.details && (
                    <div className="mapping-table__details">
                      <pre>{JSON.stringify(mapping.details, null, 2)}</pre>
                    </div>
                  )}
                </td>
                <td className="mapping-table__cell mapping-table__cell--path">
                  {mapping.migrated_path ? (
                    <code>{mapping.migrated_path}</code>
                  ) : (
                    <span className="mapping-table__no-match">No match found</span>
                  )}
                </td>
                <td className="mapping-table__cell mapping-table__cell--confidence">
                  <MigrationConfidenceBadge
                    confidence={mapping.confidence}
                    matchReason={mapping.match_reason}
                    breakingChange={mapping.breaking_change}
                    size="sm"
                  />
                </td>
                {!readonly && (
                  <td className="mapping-table__cell mapping-table__cell--override">
                    <select
                      className="mapping-table__select"
                      value={
                        hasOverride
                          ? overrideValues[mapping.original_path]
                          : mapping.migrated_path || ''
                      }
                      onChange={(e) =>
                        handleOverrideChange(mapping.original_path, e.target.value)
                      }
                    >
                      <option value="">— Unmapped —</option>
                      {availableTargets.map((target) => (
                        <option key={target} value={target}>
                          {target}
                        </option>
                      ))}
                    </select>
                    {hasOverride && (
                      <button
                        type="button"
                        className="mapping-table__apply-btn"
                        onClick={() => handleApplyOverride(mapping.original_path)}
                      >
                        Apply
                      </button>
                    )}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
