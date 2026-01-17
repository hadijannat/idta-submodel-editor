/**
 * Preview panel showing dry-run mapping results before applying to form
 */

import { useState } from 'react';
import type { PreviewEntry } from './types';

interface PreviewPanelProps {
  entries: PreviewEntry[];
  onApply: () => void;
}

export default function PreviewPanel({ entries, onApply }: PreviewPanelProps) {
  const [expanded, setExpanded] = useState(false);

  if (entries.length === 0) return null;

  return (
    <div className="smart-mapper-preview">
      <div className="smart-mapper-preview-header">
        <h4>Preview ({entries.length} fields)</h4>
        <button
          type="button"
          className="btn btn-sm btn-ghost"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? '▼ Collapse' : '▶ Expand'}
        </button>
      </div>
      {expanded && (
        <div className="smart-mapper-preview-table">
          <table>
            <thead>
              <tr>
                <th>Field</th>
                <th>Type</th>
                <th>Value</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.path}>
                  <td className="preview-path">{entry.path}</td>
                  <td className="preview-type">{entry.type}</td>
                  <td className="preview-value" title={entry.value}>
                    {entry.value.length > 60
                      ? `${entry.value.slice(0, 60)}…`
                      : entry.value}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="smart-mapper-preview-actions">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={onApply}
        >
          Apply to form →
        </button>
      </div>
    </div>
  );
}
