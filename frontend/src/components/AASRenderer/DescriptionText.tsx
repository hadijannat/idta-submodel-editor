/**
 * DescriptionText component for rendering multi-language descriptions.
 */

import React from 'react';

interface DescriptionTextProps {
  description?: Record<string, string> | null;
}

export const DescriptionText: React.FC<DescriptionTextProps> = ({
  description,
}) => {
  if (!description || Object.keys(description).length === 0) {
    return null;
  }

  return (
    <div className="aas-description">
      {Object.entries(description).map(([lang, text]) => (
        <div key={lang} className="aas-description-line">
          <span className="aas-description-lang">{lang}:</span> {text}
        </div>
      ))}
    </div>
  );
};

export default DescriptionText;
