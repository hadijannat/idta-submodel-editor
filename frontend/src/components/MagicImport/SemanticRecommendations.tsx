/**
 * SemanticRecommendations - Popover showing semantic ID recommendations for a field.
 *
 * Uses the Template Knowledge System to suggest matching ECLASS/IEC CDD semantic IDs
 * based on the field's label, value, and evidence context.
 *
 * Features:
 * - Shows top recommendations with confidence scores
 * - Highlights if any recommendation matches the current semantic ID
 * - Includes definition text for informed selection
 * - Click to accept a recommendation
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import type { FieldExtraction } from '../../services/magicImportApi';
import {
  getSemanticRecommendations,
  type SemanticRecommendation,
  type RecommendationRequest,
} from '../../services/magicImportApi';
import './MagicImport.css';

export interface SemanticRecommendationsProps {
  /** The extraction to get recommendations for */
  extraction: FieldExtraction;
  /** Current semantic ID (if any) */
  currentSemanticId?: string | null;
  /** Callback when a recommendation is accepted */
  onAccept?: (recommendation: SemanticRecommendation) => void;
}

export default function SemanticRecommendations({
  extraction,
  currentSemanticId,
  onAccept,
}: SemanticRecommendationsProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recommendations, setRecommendations] = useState<SemanticRecommendation[]>([]);
  const popoverRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  // Fetch recommendations when popover opens
  const fetchRecommendations = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      // Extract label from path (last segment)
      const pathParts = extraction.path.split('.');
      const label = pathParts[pathParts.length - 1];

      const request: RecommendationRequest = {
        label,
        value: extraction.value_raw || undefined,
        context: extraction.evidence?.quote?.slice(0, 200) || undefined,
        top_k: 5,
        threshold: 0.4,
        current_semantic_id: currentSemanticId || undefined,
      };

      const response = await getSemanticRecommendations(request);
      setRecommendations(response.recommendations);
    } catch (err) {
      console.error('Failed to fetch semantic recommendations:', err);
      setError('Failed to load recommendations');
    } finally {
      setLoading(false);
    }
  }, [extraction, currentSemanticId]);

  // Fetch when opened
  useEffect(() => {
    if (isOpen) {
      fetchRecommendations();
    }
  }, [isOpen, fetchRecommendations]);

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(event.target as Node) &&
        buttonRef.current &&
        !buttonRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  // Close on escape
  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen]);

  const handleAccept = useCallback(
    (rec: SemanticRecommendation) => {
      onAccept?.(rec);
      setIsOpen(false);
    },
    [onAccept]
  );

  const togglePopover = useCallback(() => {
    setIsOpen((prev) => !prev);
  }, []);

  // Get confidence badge class
  const getConfidenceClass = (confidence: number): string => {
    if (confidence >= 0.8) return 'semantic-rec__confidence--high';
    if (confidence >= 0.6) return 'semantic-rec__confidence--medium';
    return 'semantic-rec__confidence--low';
  };

  return (
    <div className="semantic-rec">
      <button
        ref={buttonRef}
        type="button"
        className={`semantic-rec__trigger ${isOpen ? 'semantic-rec__trigger--active' : ''}`}
        onClick={togglePopover}
        title="Get semantic ID recommendations"
      >
        <span className="semantic-rec__icon">✨</span>
        <span className="semantic-rec__label">Suggest</span>
      </button>

      {isOpen && (
        <div ref={popoverRef} className="semantic-rec__popover">
          <div className="semantic-rec__header">
            <h4 className="semantic-rec__title">Semantic ID Recommendations</h4>
            <button
              type="button"
              className="semantic-rec__close"
              onClick={() => setIsOpen(false)}
              aria-label="Close"
            >
              ×
            </button>
          </div>

          <div className="semantic-rec__content">
            {loading && (
              <div className="semantic-rec__loading">
                <span className="semantic-rec__spinner" />
                Searching template knowledge...
              </div>
            )}

            {error && <div className="semantic-rec__error">{error}</div>}

            {!loading && !error && recommendations.length === 0 && (
              <div className="semantic-rec__empty">
                No matching semantic IDs found.
                <br />
                <small>Try a different field or check if the Knowledge Index is built.</small>
              </div>
            )}

            {!loading && !error && recommendations.length > 0 && (
              <ul className="semantic-rec__list">
                {recommendations.map((rec) => (
                  <li
                    key={rec.irdi}
                    className={`semantic-rec__item ${rec.is_current ? 'semantic-rec__item--current' : ''}`}
                    onClick={() => handleAccept(rec)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        handleAccept(rec);
                      }
                    }}
                  >
                    <div className="semantic-rec__item-header">
                      <span className="semantic-rec__item-label">{rec.label}</span>
                      <span
                        className={`semantic-rec__confidence ${getConfidenceClass(rec.confidence)}`}
                      >
                        {Math.round(rec.confidence * 100)}%
                      </span>
                    </div>
                    <span className="semantic-rec__item-irdi" title={rec.irdi}>
                      {rec.irdi}
                    </span>
                    {rec.definition && (
                      <p className="semantic-rec__item-definition">
                        {rec.definition.length > 120
                          ? `${rec.definition.slice(0, 120)}…`
                          : rec.definition}
                      </p>
                    )}
                    <div className="semantic-rec__item-meta">
                      {rec.source_template && (
                        <span className="semantic-rec__item-source">
                          IDTA {rec.source_template}
                        </span>
                      )}
                      {rec.is_current && (
                        <span className="semantic-rec__item-current-badge">Current</span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="semantic-rec__footer">
            <small>
              Click a recommendation to apply it. Powered by Template Knowledge System.
            </small>
          </div>
        </div>
      )}
    </div>
  );
}
