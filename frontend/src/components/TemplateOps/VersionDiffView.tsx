/**
 * VersionDiffView - Visual diff between two template versions.
 *
 * Shows added, removed, and modified elements with color coding.
 */

import { useState, useCallback, useEffect } from 'react';
import type {
  TemplateDiffResult,
  TemplateDiffRequest,
  ElementChange,
  CardinalityChange,
  SemanticChange,
} from '../../services/templateOpsApi';
import { getTemplateDiff } from '../../services/templateOpsApi';
import './TemplateOps.css';

interface VersionDiffViewProps {
  sourceTemplate: string;
  sourceVersion?: string | null;
  sourceStatus?: 'published' | 'deprecated' | 'local';
  targetTemplate: string;
  targetVersion?: string | null;
  targetStatus?: 'published' | 'deprecated' | 'local';
  onDiffComputed?: (diff: TemplateDiffResult) => void;
}

export default function VersionDiffView({
  sourceTemplate,
  sourceVersion,
  sourceStatus = 'published',
  targetTemplate,
  targetVersion,
  targetStatus = 'published',
  onDiffComputed,
}: VersionDiffViewProps) {
  const [diff, setDiff] = useState<TemplateDiffResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedSection, setExpandedSection] = useState<string | null>('added');

  const computeDiff = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const request: TemplateDiffRequest = {
        source_template: sourceTemplate,
        source_version: sourceVersion,
        source_status: sourceStatus,
        target_template: targetTemplate,
        target_version: targetVersion,
        target_status: targetStatus,
        include_semantic_changes: true,
      };
      const result = await getTemplateDiff(request);
      setDiff(result);
      onDiffComputed?.(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to compute diff');
    } finally {
      setLoading(false);
    }
  }, [
    sourceTemplate,
    sourceVersion,
    sourceStatus,
    targetTemplate,
    targetVersion,
    targetStatus,
    onDiffComputed,
  ]);

  useEffect(() => {
    computeDiff();
  }, [computeDiff]);

  const toggleSection = useCallback((section: string) => {
    setExpandedSection((prev) => (prev === section ? null : section));
  }, []);

  if (loading) {
    return (
      <div className="diff-view diff-view--loading">
        <div className="diff-view__spinner" />
        <p>Computing diff...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="diff-view diff-view--error">
        <p className="diff-view__error">{error}</p>
        <button type="button" className="btn btn--secondary" onClick={computeDiff}>
          Retry
        </button>
      </div>
    );
  }

  if (!diff) {
    return null;
  }

  const hasChanges =
    diff.elements_added.length > 0 ||
    diff.elements_removed.length > 0 ||
    diff.elements_modified.length > 0 ||
    diff.cardinality_changes.length > 0 ||
    diff.semantic_changes.length > 0;

  return (
    <div className="diff-view">
      <div className="diff-view__header">
        <div className="diff-view__templates">
          <span className="diff-view__template diff-view__template--source">
            {sourceTemplate}
            {sourceVersion && <span className="diff-view__version">v{sourceVersion}</span>}
          </span>
          <span className="diff-view__arrow">→</span>
          <span className="diff-view__template diff-view__template--target">
            {targetTemplate}
            {targetVersion && <span className="diff-view__version">v{targetVersion}</span>}
          </span>
        </div>
        <div className="diff-view__summary">
          <span className={`diff-view__badge ${diff.is_breaking ? 'diff-view__badge--breaking' : 'diff-view__badge--safe'}`}>
            {diff.is_breaking ? '⚠️ Breaking Changes' : '✓ Non-breaking'}
          </span>
        </div>
      </div>

      {!hasChanges ? (
        <div className="diff-view__empty">
          <p>No changes detected between these versions.</p>
        </div>
      ) : (
        <div className="diff-view__sections">
          {/* Added Elements */}
          {diff.elements_added.length > 0 && (
            <DiffSection
              title="Added Elements"
              count={diff.elements_added.length}
              type="added"
              expanded={expandedSection === 'added'}
              onToggle={() => toggleSection('added')}
            >
              <ul className="diff-view__list">
                {diff.elements_added.map((path) => (
                  <li key={path} className="diff-view__item diff-view__item--added">
                    <code>+ {path}</code>
                  </li>
                ))}
              </ul>
            </DiffSection>
          )}

          {/* Removed Elements */}
          {diff.elements_removed.length > 0 && (
            <DiffSection
              title="Removed Elements"
              count={diff.elements_removed.length}
              type="removed"
              expanded={expandedSection === 'removed'}
              onToggle={() => toggleSection('removed')}
            >
              <ul className="diff-view__list">
                {diff.elements_removed.map((path) => (
                  <li key={path} className="diff-view__item diff-view__item--removed">
                    <code>- {path}</code>
                  </li>
                ))}
              </ul>
            </DiffSection>
          )}

          {/* Modified Elements */}
          {diff.elements_modified.length > 0 && (
            <DiffSection
              title="Modified Elements"
              count={diff.elements_modified.length}
              type="modified"
              expanded={expandedSection === 'modified'}
              onToggle={() => toggleSection('modified')}
            >
              <ul className="diff-view__list">
                {diff.elements_modified.map((change: ElementChange) => (
                  <li key={change.path} className="diff-view__item diff-view__item--modified">
                    <code>~ {change.path}</code>
                    <div className="diff-view__change-detail">
                      <span className="diff-view__old">{change.old_value}</span>
                      <span className="diff-view__arrow">→</span>
                      <span className="diff-view__new">{change.new_value}</span>
                    </div>
                  </li>
                ))}
              </ul>
            </DiffSection>
          )}

          {/* Cardinality Changes */}
          {diff.cardinality_changes.length > 0 && (
            <DiffSection
              title="Cardinality Changes"
              count={diff.cardinality_changes.length}
              type="cardinality"
              expanded={expandedSection === 'cardinality'}
              onToggle={() => toggleSection('cardinality')}
            >
              <ul className="diff-view__list">
                {diff.cardinality_changes.map((change: CardinalityChange) => (
                  <li
                    key={change.path}
                    className={`diff-view__item diff-view__item--cardinality ${
                      change.breaking ? 'diff-view__item--breaking' : ''
                    }`}
                  >
                    <code>{change.path}</code>
                    <div className="diff-view__change-detail">
                      <span className="diff-view__old">{change.old_cardinality}</span>
                      <span className="diff-view__arrow">→</span>
                      <span className="diff-view__new">{change.new_cardinality}</span>
                      {change.breaking && (
                        <span className="diff-view__breaking-tag">Breaking</span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </DiffSection>
          )}

          {/* Semantic Changes */}
          {diff.semantic_changes.length > 0 && (
            <DiffSection
              title="Semantic ID Changes"
              count={diff.semantic_changes.length}
              type="semantic"
              expanded={expandedSection === 'semantic'}
              onToggle={() => toggleSection('semantic')}
            >
              <ul className="diff-view__list">
                {diff.semantic_changes.map((change: SemanticChange) => (
                  <li key={change.path} className="diff-view__item diff-view__item--semantic">
                    <code>{change.path}</code>
                    <div className="diff-view__change-detail">
                      <span className="diff-view__old" title={change.old_semantic_id || 'None'}>
                        {truncateSemanticId(change.old_semantic_id)}
                      </span>
                      <span className="diff-view__arrow">→</span>
                      <span className="diff-view__new" title={change.new_semantic_id || 'None'}>
                        {truncateSemanticId(change.new_semantic_id)}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </DiffSection>
          )}
        </div>
      )}

      <div className="diff-view__footer">
        <p className="diff-view__summary-text">{diff.summary}</p>
      </div>
    </div>
  );
}

interface DiffSectionProps {
  title: string;
  count: number;
  type: 'added' | 'removed' | 'modified' | 'cardinality' | 'semantic';
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}

function DiffSection({ title, count, type, expanded, onToggle, children }: DiffSectionProps) {
  return (
    <div className={`diff-section diff-section--${type}`}>
      <button
        type="button"
        className="diff-section__header"
        onClick={onToggle}
        aria-expanded={expanded}
      >
        <span className="diff-section__toggle">{expanded ? '▼' : '▶'}</span>
        <span className="diff-section__title">{title}</span>
        <span className="diff-section__count">{count}</span>
      </button>
      {expanded && <div className="diff-section__content">{children}</div>}
    </div>
  );
}

function truncateSemanticId(id: string | null): string {
  if (!id) return 'None';
  if (id.length <= 40) return id;
  return `...${id.slice(-37)}`;
}
