import React from 'react';

interface SemanticChipProps {
  semanticId?: string | null;
  onOpen: () => void;
  onClear?: () => void;
}

const truncate = (value: string, max = 28) => {
  if (value.length <= max) return value;
  return `${value.slice(0, max)}…`;
};

export const SemanticChip: React.FC<SemanticChipProps> = ({
  semanticId,
  onOpen,
  onClear,
}) => {
  return (
    <div className="semantic-chip-row">
      {semanticId ? (
        <span className="semantic-chip" title={semanticId}>
          {truncate(semanticId)}
        </span>
      ) : (
        <span className="semantic-chip semantic-chip-empty">No semantic ID</span>
      )}
      <div className="semantic-chip-actions">
        <button type="button" className="semantic-btn" onClick={onOpen}>
          {semanticId ? 'Change' : 'Add'}
        </button>
        {semanticId && onClear && (
          <button
            type="button"
            className="semantic-btn semantic-btn-ghost"
            onClick={onClear}
          >
            Clear
          </button>
        )}
      </div>
    </div>
  );
};

export default SemanticChip;
