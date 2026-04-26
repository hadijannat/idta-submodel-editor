import React, { useEffect, useMemo, useState } from 'react';
import { SUPPORTED_LANGUAGES } from '../../types/aas-elements';
import type {
  SemanticApplyPreviewResponse,
  SemanticEntry,
  SemanticKind,
  SemanticProviderInfo,
} from '../../types/semantic';
import {
  applySemanticPreview,
  listSemanticProviders,
  resolveSemantic,
  searchSemantics,
} from '../../services/semanticApi';

interface SemanticLookupModalProps {
  isOpen: boolean;
  onClose: () => void;
  onApply: (semanticId: string) => void;
  currentSemanticId?: string | null;
  elementType?: string | null;
  valueType?: string | null;
  defaultKind?: SemanticKind;
}

const KINDS: SemanticKind[] = ['property', 'class', 'unit', 'value'];

export const SemanticLookupModal: React.FC<SemanticLookupModalProps> = ({
  isOpen,
  onClose,
  onApply,
  currentSemanticId,
  elementType,
  valueType,
  defaultKind = 'property',
}) => {
  const [providers, setProviders] = useState<SemanticProviderInfo[]>([]);
  const [providerFilter, setProviderFilter] = useState<string>('all');
  const [kindFilter, setKindFilter] = useState<SemanticKind>(defaultKind);
  const [language, setLanguage] = useState<string>('en');
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SemanticEntry[]>([]);
  const [selected, setSelected] = useState<SemanticEntry | null>(null);
  const [details, setDetails] = useState<SemanticEntry | null>(null);
  const [preview, setPreview] = useState<SemanticApplyPreviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const providerOptions = useMemo(() => {
    const readyProviders = providers.filter((p) => p.status === 'ready');
    return [{ id: 'all', label: 'All providers', status: 'ready' as const }, ...readyProviders];
  }, [providers]);
  const hasSearchQuery = query.trim().length >= 2;
  const visibleResults = hasSearchQuery ? results : [];
  const visibleError = hasSearchQuery ? error : null;
  const showSearchLoading = hasSearchQuery && loading;
  const activePreview = selected ? preview : null;

  useEffect(() => {
    if (!isOpen) return;
    let active = true;
    listSemanticProviders()
      .then((data) => {
        if (!active) return;
        setProviders(data);
      })
      .catch(() => {
        if (!active) return;
        setProviders([]);
      });
    return () => {
      active = false;
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen || !currentSemanticId) return;
    let active = true;
    setLoadingDetails(true);
    resolveSemantic(currentSemanticId)
      .then((res) => {
        if (!active) return;
        setSelected(res.entry);
        setDetails(res.entry);
      })
      .catch(() => {
        if (!active) return;
      })
      .finally(() => {
        if (!active) return;
        setLoadingDetails(false);
      });
    return () => {
      active = false;
    };
  }, [isOpen, currentSemanticId]);

  useEffect(() => {
    if (!isOpen) return;
    const trimmed = query.trim();
    if (trimmed.length < 2) return;

    let active = true;
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError(null);
      searchSemantics({
        q: trimmed,
        provider: providerFilter === 'all' ? undefined : providerFilter,
        kind: kindFilter,
        lang: language,
        limit: 20,
        offset: 0,
      })
        .then((res) => {
          if (active) {
            setResults(res.results);
          }
        })
        .catch(() => {
          if (active) {
            setError('Unable to search semantic dictionaries.');
            setResults([]);
          }
        })
        .finally(() => {
          if (active) {
            setLoading(false);
          }
        });
    }, 350);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [query, providerFilter, kindFilter, language, isOpen]);

  useEffect(() => {
    if (!isOpen || !selected) return;

    let active = true;
    setLoadingDetails(true);
    Promise.all([
      resolveSemantic(selected.canonicalId, selected.provider, language),
      applySemanticPreview({
        identifier: selected.canonicalId,
        provider: selected.provider,
        elementType: elementType ?? undefined,
        valueType: valueType ?? undefined,
      }),
    ])
      .then(([resolved, previewResult]) => {
        if (!active) return;
        setDetails(resolved.entry);
        setPreview(previewResult);
      })
      .catch(() => {
        if (!active) return;
        setPreview(null);
      })
      .finally(() => {
        if (!active) return;
        setLoadingDetails(false);
      });

    return () => {
      active = false;
    };
  }, [selected, elementType, valueType, language, isOpen]);

  if (!isOpen) return null;

  const handleClose = () => {
    setSelected(null);
    setDetails(null);
    setPreview(null);
    onClose();
  };

  const handleQueryChange = (value: string) => {
    setQuery(value);
    setError(null);
    if (value.trim().length < 2) {
      setLoading(false);
    }
  };

  const handleResultSelect = (entry: SemanticEntry) => {
    setSelected(entry);
    setDetails(null);
    setPreview(null);
  };

  const handleApply = async () => {
    if (!selected) return;
    const semanticId =
      activePreview?.semanticId || selected.canonicalIri || selected.canonicalId;
    onApply(semanticId);
    handleClose();
  };

  const renderDetails = () => {
    const entry = selected ? details || selected : null;
    if (!entry) {
      return <p className="semantic-muted">Select a result to see details.</p>;
    }

    return (
      <div className="semantic-details">
        <h4>{entry.preferredName || entry.canonicalId}</h4>
        <p className="semantic-muted">Provider: {entry.provider}</p>
        {entry.definition && <p>{entry.definition}</p>}
        <div className="semantic-detail-grid">
          <div>
            <span className="semantic-detail-label">Canonical ID</span>
            <span className="semantic-detail-value">{entry.canonicalId}</span>
          </div>
          {entry.canonicalIri && (
            <div>
              <span className="semantic-detail-label">IRI</span>
              <span className="semantic-detail-value">{entry.canonicalIri}</span>
            </div>
          )}
          {entry.datatypeHint && (
            <div>
              <span className="semantic-detail-label">Datatype</span>
              <span className="semantic-detail-value">{entry.datatypeHint}</span>
            </div>
          )}
          {entry.unitHint && (
            <div>
              <span className="semantic-detail-label">Unit</span>
              <span className="semantic-detail-value">{entry.unitHint}</span>
            </div>
          )}
        </div>
        {activePreview?.warnings?.length ? (
          <div className="semantic-warning">
            <strong>Warnings</strong>
            <ul>
              {activePreview.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {activePreview?.notes?.length ? (
          <div className="semantic-note">
            <strong>Notes</strong>
            <ul>
              {activePreview.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {activePreview?.elementType && (
          <p className="semantic-muted">
            Suggested element type: {activePreview.elementType}
          </p>
        )}
        {activePreview?.valueType && (
          <p className="semantic-muted">
            Suggested value type: {activePreview.valueType}
          </p>
        )}
      </div>
    );
  };

  return (
    <div className="semantic-modal-overlay" role="dialog" aria-modal="true">
      <div className="semantic-modal">
        <div className="semantic-modal-header">
          <div>
            <h3>Semantic dictionary lookup</h3>
            <p className="semantic-muted">
              Search ECLASS or IEC CDD to attach a semantic identifier.
            </p>
          </div>
          <button type="button" className="semantic-btn semantic-btn-ghost" onClick={handleClose}>
            Close
          </button>
        </div>

        <div className="semantic-modal-search">
          <input
            type="text"
            className="aas-input"
            placeholder="Search for a term (min 2 chars)…"
            value={query}
            onChange={(event) => handleQueryChange(event.target.value)}
          />
          <div className="semantic-filters">
            <label>
              Provider
              <select
                value={providerFilter}
                onChange={(event) => setProviderFilter(event.target.value)}
              >
                {providerOptions.map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Kind
              <select
                value={kindFilter}
                onChange={(event) =>
                  setKindFilter(event.target.value as SemanticKind)
                }
              >
                {KINDS.map((kind) => (
                  <option key={kind} value={kind}>
                    {kind}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Language
              <select
                value={language}
                onChange={(event) => setLanguage(event.target.value)}
              >
                {SUPPORTED_LANGUAGES.map((lang) => (
                  <option key={lang.code} value={lang.code}>
                    {lang.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        <div className="semantic-modal-body">
          <div className="semantic-results">
            {showSearchLoading && <p className="semantic-muted">Searching…</p>}
            {!showSearchLoading && visibleError && (
              <p className="semantic-error">{visibleError}</p>
            )}
            {!showSearchLoading && !visibleError && visibleResults.length === 0 && hasSearchQuery && (
              <p className="semantic-muted">No results.</p>
            )}
            {!showSearchLoading && !hasSearchQuery && (
              <p className="semantic-muted">Type at least two characters to search.</p>
            )}
            <ul>
              {visibleResults.map((entry) => (
                <li
                  key={`${entry.provider}-${entry.canonicalId}`}
                  className={`semantic-result-item${
                    selected?.canonicalId === entry.canonicalId ? ' selected' : ''
                  }`}
                  onClick={() => handleResultSelect(entry)}
                >
                  <div>
                    <strong>{entry.preferredName || entry.canonicalId}</strong>
                    <p className="semantic-muted">{entry.canonicalId}</p>
                  </div>
                  <div className="semantic-result-meta">
                    <span>{entry.provider}</span>
                    {entry.datatypeHint && <span>{entry.datatypeHint}</span>}
                    {entry.unitHint && <span>{entry.unitHint}</span>}
                  </div>
                </li>
              ))}
            </ul>
          </div>
          <div className="semantic-side">
            {loadingDetails && <p className="semantic-muted">Loading details…</p>}
            {!loadingDetails && renderDetails()}
          </div>
        </div>

        <div className="semantic-modal-footer">
          <button
            type="button"
            className="semantic-btn semantic-btn-ghost"
            onClick={handleClose}
          >
            Cancel
          </button>
          <button
            type="button"
            className="semantic-btn semantic-btn-primary"
            onClick={handleApply}
            disabled={!selected}
          >
            Apply semantic ID
          </button>
        </div>
      </div>
    </div>
  );
};

export default SemanticLookupModal;
