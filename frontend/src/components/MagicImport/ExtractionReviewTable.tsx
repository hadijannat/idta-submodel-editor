/**
 * ExtractionReviewTable - Table showing extracted fields with values and confidence.
 *
 * Supports batch selection and approval operations.
 */

import { useState, useCallback } from 'react';
import type {
  FieldExtraction,
  UnmappedFinding,
  ExtractionStatus,
} from '../../services/magicImportApi';
import ConfidenceBadge from './ConfidenceBadge.tsx';
import SemanticRecommendations from './SemanticRecommendations.tsx';
import type { SemanticRecommendation } from '../../services/magicImportApi';
import './MagicImport.css';

/** Represents a batch action that can be undone */
interface BatchAction {
  type: 'approve' | 'unapprove';
  paths: string[];
  timestamp: number;
}

interface ExtractionReviewTableProps {
  extractions: FieldExtraction[];
  unmappedFindings?: UnmappedFinding[];
  selectedPath: string | null;
  onSelect: (path: string | null) => void;
  onUpdate: (path: string, value: string) => void;
  onApprove: (path: string) => void;
  onApproveAll: () => void;
  onApproveMany?: (paths: string[]) => void;
  /** Callback to unapprove multiple extractions (for undo) */
  onUnapproveMany?: (paths: string[]) => void;
  /** Highlight selected row when PDF evidence is focused */
  highlightSelectedRow?: boolean;
  /** Callback when a semantic ID recommendation is accepted */
  onSemanticIdAccept?: (path: string, recommendation: SemanticRecommendation) => void;
}

export default function ExtractionReviewTable({
  extractions,
  unmappedFindings = [],
  selectedPath,
  onSelect,
  onUpdate,
  onApprove,
  onApproveAll,
  onApproveMany,
  onUnapproveMany,
  highlightSelectedRow = false,
  onSemanticIdAccept,
}: ExtractionReviewTableProps) {
  const [editingPath, setEditingPath] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');
  const [filter, setFilter] = useState<'all' | 'review' | 'approved'>('all');
  const [query, setQuery] = useState('');
  const [sortBy, setSortBy] = useState<'confidence_desc' | 'confidence_asc' | 'path_asc'>(
    'confidence_desc'
  );
  const [evidenceOnly, setEvidenceOnly] = useState(false);
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(new Set());
  const [showApproveDropdown, setShowApproveDropdown] = useState(false);
  const [lastClickedIndex, setLastClickedIndex] = useState<number | null>(null);

  // Batch approval threshold (default 85%)
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.85);

  // Undo history stack (keeps last 5 batch actions)
  const [undoHistory, setUndoHistory] = useState<BatchAction[]>([]);
  const MAX_UNDO_HISTORY = 5;

  // Filter extractions
  const normalizedQuery = query.trim().toLowerCase();
  const filteredExtractions = extractions
    .filter((e) => {
      if (filter === 'review') return e.status === 'needs_review' || e.status === 'conflict';
      if (filter === 'approved') return e.user_approved || e.status === 'filled';
      return true;
    })
    .filter((e) => (evidenceOnly ? !!e.evidence : true))
    .filter((e) => {
      if (!normalizedQuery) return true;
      const haystack = [
        e.path,
        e.value_raw,
        e.evidence?.quote ?? '',
        e.value_type ?? '',
      ]
        .join(' ')
        .toLowerCase();
      return haystack.includes(normalizedQuery);
    })
    .sort((a, b) => {
      if (sortBy === 'path_asc') {
        return a.path.localeCompare(b.path);
      }
      if (sortBy === 'confidence_asc') {
        return a.confidence - b.confidence;
      }
      return b.confidence - a.confidence;
    });

  // Counts
  const needsReviewCount = extractions.filter(
    (e) => e.status === 'needs_review' || e.status === 'conflict'
  ).length;
  const approvedCount = extractions.filter(
    (e) => e.user_approved || e.status === 'filled'
  ).length;
  const evidenceCount = extractions.filter((e) => e.evidence).length;
  const avgConfidence =
    extractions.length > 0
      ? Math.round(
          (extractions.reduce((sum, e) => sum + e.confidence, 0) / extractions.length) *
            100
        )
      : 0;

  // Start editing
  const handleEdit = (extraction: FieldExtraction) => {
    setEditingPath(extraction.path);
    setEditValue(extraction.value_raw);
  };

  // Save edit
  const handleSave = (path: string) => {
    onUpdate(path, editValue);
    setEditingPath(null);
  };

  // Cancel edit
  const handleCancel = () => {
    setEditingPath(null);
    setEditValue('');
  };

  // Toggle checkbox selection
  const handleCheckboxChange = useCallback(
    (path: string, index: number, shiftKey: boolean) => {
      setSelectedPaths((prev) => {
        const next = new Set(prev);

        // Shift+click for range selection
        if (shiftKey && lastClickedIndex !== null) {
          const start = Math.min(lastClickedIndex, index);
          const end = Math.max(lastClickedIndex, index);
          for (let i = start; i <= end; i++) {
            next.add(filteredExtractions[i].path);
          }
        } else {
          // Toggle single selection
          if (next.has(path)) {
            next.delete(path);
          } else {
            next.add(path);
          }
        }

        return next;
      });
      setLastClickedIndex(index);
    },
    [filteredExtractions, lastClickedIndex]
  );

  // Select all visible
  const handleSelectAll = useCallback(() => {
    if (selectedPaths.size === filteredExtractions.length) {
      // Deselect all
      setSelectedPaths(new Set());
    } else {
      // Select all visible
      setSelectedPaths(new Set(filteredExtractions.map((e) => e.path)));
    }
  }, [filteredExtractions, selectedPaths.size]);

  // Clear selection
  const clearSelection = useCallback(() => {
    setSelectedPaths(new Set());
  }, []);

  // Approve selected
  const handleApproveSelected = useCallback(() => {
    if (onApproveMany) {
      onApproveMany(Array.from(selectedPaths));
    } else {
      // Fallback: approve one by one
      selectedPaths.forEach((path) => onApprove(path));
    }
    setSelectedPaths(new Set());
  }, [selectedPaths, onApproveMany, onApprove]);

  // Add action to undo history
  const pushToUndoHistory = useCallback((action: BatchAction) => {
    setUndoHistory((prev) => {
      const newHistory = [action, ...prev].slice(0, MAX_UNDO_HISTORY);
      return newHistory;
    });
  }, [MAX_UNDO_HISTORY]);

  // Undo last batch action
  const handleUndo = useCallback(() => {
    if (undoHistory.length === 0 || !onUnapproveMany) return;

    const lastAction = undoHistory[0];
    if (lastAction.type === 'approve') {
      // Undo approval by unapproving
      onUnapproveMany(lastAction.paths);
    }
    // Remove from history
    setUndoHistory((prev) => prev.slice(1));
  }, [undoHistory, onUnapproveMany]);

  // Approve all above threshold
  const handleApproveAboveThreshold = useCallback(
    (threshold: number) => {
      const pathsAboveThreshold = filteredExtractions
        .filter(
          (e) =>
            e.confidence >= threshold &&
            (e.status === 'needs_review' || e.status === 'conflict') &&
            !e.user_approved
        )
        .map((e) => e.path);

      if (pathsAboveThreshold.length === 0) {
        setShowApproveDropdown(false);
        return;
      }

      // Record for undo
      pushToUndoHistory({
        type: 'approve',
        paths: pathsAboveThreshold,
        timestamp: Date.now(),
      });

      if (onApproveMany) {
        onApproveMany(pathsAboveThreshold);
      } else {
        pathsAboveThreshold.forEach((path) => onApprove(path));
      }
      setShowApproveDropdown(false);
    },
    [filteredExtractions, onApproveMany, onApprove, pushToUndoHistory]
  );

  // Approve all extractions (with undo support)
  const handleApproveAllWithUndo = useCallback(() => {
    const pathsToApprove = extractions
      .filter(
        (e) =>
          (e.status === 'needs_review' || e.status === 'conflict') &&
          !e.user_approved
      )
      .map((e) => e.path);

    if (pathsToApprove.length > 0) {
      pushToUndoHistory({
        type: 'approve',
        paths: pathsToApprove,
        timestamp: Date.now(),
      });
    }

    onApproveAll();
    setShowApproveDropdown(false);
  }, [extractions, onApproveAll, pushToUndoHistory]);

  // Counts for threshold options
  const countAboveThreshold = (threshold: number) =>
    filteredExtractions.filter(
      (e) =>
        e.confidence >= threshold &&
        (e.status === 'needs_review' || e.status === 'conflict') &&
        !e.user_approved
    ).length;

  return (
    <div className="extraction-table">
      {/* Filter tabs */}
      <div className="extraction-table__filters">
        <div className="extraction-table__filter-group">
          <button
            type="button"
            className={`extraction-table__filter ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            All ({extractions.length})
          </button>
          <button
            type="button"
            className={`extraction-table__filter ${filter === 'review' ? 'active' : ''}`}
            onClick={() => setFilter('review')}
          >
            Needs Review ({needsReviewCount})
          </button>
          <button
            type="button"
            className={`extraction-table__filter ${filter === 'approved' ? 'active' : ''}`}
            onClick={() => setFilter('approved')}
          >
            Ready ({approvedCount})
          </button>
        </div>

        <div className="extraction-table__search">
          <input
            type="text"
            placeholder="Search fields, values, evidence..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        <div className="extraction-table__sort">
          <label>
            Sort
            <select
              value={sortBy}
              onChange={(e) =>
                setSortBy(e.target.value as 'confidence_desc' | 'confidence_asc' | 'path_asc')
              }
            >
              <option value="confidence_desc">Confidence (high → low)</option>
              <option value="confidence_asc">Confidence (low → high)</option>
              <option value="path_asc">Path (A → Z)</option>
            </select>
          </label>
        </div>

        <label className="extraction-table__toggle">
          <input
            type="checkbox"
            checked={evidenceOnly}
            onChange={(e) => setEvidenceOnly(e.target.checked)}
          />
          Evidence only
        </label>

        {/* Batch Approval Controls */}
        {needsReviewCount > 0 && (
          <div className="extraction-table__batch-approve">
            {/* Threshold slider */}
            <div className="extraction-table__threshold-control">
              <label className="extraction-table__threshold-label">
                Threshold:
                <input
                  type="range"
                  min="0.5"
                  max="1"
                  step="0.05"
                  value={confidenceThreshold}
                  onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))}
                  className="extraction-table__threshold-slider"
                />
                <span className="extraction-table__threshold-value">
                  {Math.round(confidenceThreshold * 100)}%
                </span>
              </label>
            </div>

            {/* Approve dropdown */}
            <div className="extraction-table__approve-dropdown">
              <button
                type="button"
                className="extraction-table__dropdown-btn"
                onClick={() => setShowApproveDropdown(!showApproveDropdown)}
              >
                Approve ▼
              </button>
              {showApproveDropdown && (
                <div className="extraction-table__dropdown-menu">
                  <button
                    type="button"
                    className="extraction-table__dropdown-item"
                    onClick={handleApproveAllWithUndo}
                  >
                    All ({needsReviewCount})
                  </button>
                  <button
                    type="button"
                    className="extraction-table__dropdown-item extraction-table__dropdown-item--primary"
                    onClick={() => handleApproveAboveThreshold(confidenceThreshold)}
                  >
                    ≥{Math.round(confidenceThreshold * 100)}% confidence ({countAboveThreshold(confidenceThreshold)})
                  </button>
                  <hr className="extraction-table__dropdown-divider" />
                  <button
                    type="button"
                    className="extraction-table__dropdown-item"
                    onClick={() => handleApproveAboveThreshold(0.9)}
                  >
                    ≥90% ({countAboveThreshold(0.9)})
                  </button>
                  <button
                    type="button"
                    className="extraction-table__dropdown-item"
                    onClick={() => handleApproveAboveThreshold(0.8)}
                  >
                    ≥80% ({countAboveThreshold(0.8)})
                  </button>
                </div>
              )}
            </div>

            {/* Undo button */}
            {undoHistory.length > 0 && onUnapproveMany && (
              <button
                type="button"
                className="extraction-table__undo-btn"
                onClick={handleUndo}
                title={`Undo: approved ${undoHistory[0]?.paths.length} items`}
              >
                ↩ Undo
              </button>
            )}
          </div>
        )}
      </div>

      <div className="extraction-table__summary">
        <span className="extraction-table__chip">
          Avg confidence: {avgConfidence}%
        </span>
        <span className="extraction-table__chip">
          Evidence: {evidenceCount}/{extractions.length}
        </span>
        <span className="extraction-table__chip">
          Needs review: {needsReviewCount}
        </span>
      </div>

      {/* Batch selection bar */}
      {selectedPaths.size > 0 && (
        <div className="extraction-table__batch-bar">
          <span className="extraction-table__batch-count">
            {selectedPaths.size} selected
          </span>
          <div className="extraction-table__batch-actions">
            <button
              type="button"
              className="extraction-table__btn extraction-table__btn--approve"
              onClick={handleApproveSelected}
            >
              Approve Selected
            </button>
            <button
              type="button"
              className="extraction-table__btn"
              onClick={clearSelection}
            >
              Clear Selection
            </button>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="extraction-table__container">
        <table className="extraction-table__table">
          <thead>
            <tr>
              <th className="extraction-table__checkbox-col">
                <input
                  type="checkbox"
                  checked={
                    filteredExtractions.length > 0 &&
                    selectedPaths.size === filteredExtractions.length
                  }
                  onChange={handleSelectAll}
                  title="Select all"
                />
              </th>
              <th>Field</th>
              <th>Status</th>
              <th>Value</th>
              <th>Confidence</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredExtractions.map((extraction, index) => {
              const evidence = extraction.evidence;
              const evidenceBoxCount = evidence?.boxes.length ?? 0;

              return (
                <tr
                  key={extraction.path}
                  className={`extraction-table__row ${
                    selectedPath === extraction.path ? 'selected' : ''
                  } ${extraction.needs_review ? 'needs-review' : ''} ${
                    selectedPaths.has(extraction.path) ? 'batch-selected' : ''
                  } ${
                    highlightSelectedRow && selectedPath === extraction.path
                      ? 'highlighted-from-pdf'
                      : ''
                  }`}
                  onClick={() => onSelect(extraction.path)}
                >
                  <td className="extraction-table__checkbox-col">
                    <input
                      type="checkbox"
                      checked={selectedPaths.has(extraction.path)}
                      onChange={() => {
                        // onChange is needed for React controlled input
                      }}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleCheckboxChange(extraction.path, index, e.shiftKey);
                      }}
                    />
                  </td>
                  <td className="extraction-table__field">
                    <span className="extraction-table__path">{formatPath(extraction.path)}</span>
                    {extraction.value_type && (
                      <span className="extraction-table__meta">
                        Type: {extraction.value_type}
                      </span>
                    )}
                  </td>
                  <td className="extraction-table__status">
                    <StatusBadge status={extraction.status} />
                  </td>
                  <td className="extraction-table__value">
                    {editingPath === extraction.path ? (
                      <input
                        type="text"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleSave(extraction.path);
                          if (e.key === 'Escape') handleCancel();
                        }}
                        autoFocus
                        className="extraction-table__input"
                        onClick={(e) => e.stopPropagation()}
                      />
                    ) : (
                      <div className="extraction-table__value-stack">
                        <span className="extraction-table__text">
                          {extraction.value_raw || '—'}
                        </span>
                        {evidence?.quote ? (
                          <span className="extraction-table__evidence-quote">
                            <span
                              className="extraction-table__evidence-box-indicator"
                              title={`${evidenceBoxCount} evidence box${
                                evidenceBoxCount === 1 ? '' : 'es'
                              }`}
                            >
                              {evidenceBoxCount}
                            </span>
                            "{evidence.quote.slice(0, 80)}
                            {evidence.quote.length > 80 ? '…' : ''}"
                          </span>
                        ) : (
                          <span className="extraction-table__evidence-missing">
                            No evidence located
                          </span>
                        )}
                      </div>
                    )}
                  </td>
                  <td className="extraction-table__confidence">
                    <div className="extraction-table__confidence-stack">
                      <div className="extraction-table__confidence-row">
                        <ConfidenceBadge
                          confidence={extraction.confidence}
                          needsReview={extraction.needs_review}
                          userApproved={extraction.user_approved}
                          userEdited={extraction.user_edited}
                          confidenceBreakdown={extraction.confidence_breakdown}
                          confidenceReasons={extraction.confidence_reasons}
                          size="sm"
                        />
                        {evidence && (
                          <span
                            className="extraction-table__evidence-source"
                            title={`Source: ${evidence.method}${
                              evidence.locator_score >= 0.9 ? ' (verified)' : ''
                            }`}
                          >
                            {evidence.method === 'OCR' ? '🔍' : '📝'}
                            {evidence.locator_score >= 0.9 && (
                              <span className="extraction-table__evidence-verified">✓</span>
                            )}
                          </span>
                        )}
                      </div>
                      {extraction.confidence_reasons?.length > 0 && (
                        <span className="extraction-table__reason-subtitle">
                          {extraction.confidence_reasons[0].message.slice(0, 40)}
                          {extraction.confidence_reasons[0].message.length > 40 ? '…' : ''}
                        </span>
                      )}
                      {/* Semantic ID Recommendations */}
                      <div
                        className="extraction-table__semantic-rec"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <SemanticRecommendations
                          extraction={extraction}
                          onAccept={
                            onSemanticIdAccept
                              ? (rec) => onSemanticIdAccept(extraction.path, rec)
                              : undefined
                          }
                        />
                      </div>
                    </div>
                  </td>
                  <td className="extraction-table__actions">
                    {editingPath === extraction.path ? (
                      <>
                        <button
                          type="button"
                          className="extraction-table__btn extraction-table__btn--save"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleSave(extraction.path);
                          }}
                        >
                          Save
                        </button>
                        <button
                          type="button"
                          className="extraction-table__btn extraction-table__btn--cancel"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleCancel();
                          }}
                        >
                          Cancel
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          type="button"
                          className="extraction-table__btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            handleEdit(extraction);
                          }}
                        >
                          Edit
                        </button>
                        {extraction.needs_review && !extraction.user_approved && (
                          <button
                            type="button"
                            className="extraction-table__btn extraction-table__btn--approve"
                            onClick={(e) => {
                              e.stopPropagation();
                              onApprove(extraction.path);
                            }}
                          >
                            Approve
                          </button>
                        )}
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {filteredExtractions.length === 0 && (
        <div className="extraction-table__empty">
          {filter === 'review'
            ? 'No extractions need review'
            : filter === 'approved'
            ? 'No approved extractions yet'
            : 'No extractions available'}
        </div>
      )}

      {/* Unmapped Findings Section */}
      {unmappedFindings.length > 0 && (
        <div className="unmapped-findings">
          <h4 className="unmapped-findings__header">
            Unmapped Values ({unmappedFindings.length})
            <span className="unmapped-findings__subtitle">
              Values found in document that don't match template fields
            </span>
          </h4>
          <div className="unmapped-findings__list">
            {unmappedFindings.map((finding, index) => (
              <div key={index} className="unmapped-findings__item">
                <div className="unmapped-findings__value">
                  <span className="unmapped-findings__source-badge">
                    {finding.source}
                  </span>
                  <span className="unmapped-findings__text">{finding.value}</span>
                </div>
                {finding.evidence?.quote && (
                  <div className="unmapped-findings__evidence">
                    <span className="unmapped-findings__page">
                      Page {finding.evidence.page + 1}
                    </span>
                    "{finding.evidence.quote.slice(0, 100)}
                    {finding.evidence.quote.length > 100 ? '…' : ''}"
                  </div>
                )}
                {finding.suggested_paths.length > 0 && (
                  <div className="unmapped-findings__suggestions">
                    <span className="unmapped-findings__suggestions-label">
                      Suggested fields:
                    </span>
                    {finding.suggested_paths.slice(0, 3).map((path) => (
                      <span key={path} className="unmapped-findings__suggestion">
                        {formatPath(path)}
                      </span>
                    ))}
                  </div>
                )}
                <div className="unmapped-findings__confidence">
                  <ConfidenceBadge
                    confidence={finding.confidence}
                    needsReview={false}
                    userApproved={false}
                    userEdited={false}
                    size="sm"
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Format path for display.
 */
function formatPath(path: string): string {
  // Split by dots and format each segment
  return path
    .split('.')
    .map((segment) => {
      // Remove [] suffix for lists
      if (segment.endsWith('[]')) {
        return segment.slice(0, -2);
      }
      // Add spaces before capital letters (camelCase to Title Case)
      return segment.replace(/([A-Z])/g, ' $1').trim();
    })
    .join(' > ');
}

/**
 * Status badge showing extraction status.
 */
function StatusBadge({ status }: { status: ExtractionStatus }) {
  const config: Record<ExtractionStatus, { label: string; className: string; title: string }> = {
    filled: {
      label: 'Filled',
      className: 'status-badge--filled',
      title: 'Value extracted with document evidence',
    },
    empty: {
      label: 'Empty',
      className: 'status-badge--empty',
      title: 'Value not found in document',
    },
    needs_review: {
      label: 'Review',
      className: 'status-badge--review',
      title: 'Low confidence or missing evidence - needs manual review',
    },
    conflict: {
      label: 'Conflict',
      className: 'status-badge--conflict',
      title: 'Multiple conflicting values found in document',
    },
  };

  const { label, className, title } = config[status] || config.needs_review;

  return (
    <span className={`status-badge ${className}`} title={title}>
      {label}
    </span>
  );
}
