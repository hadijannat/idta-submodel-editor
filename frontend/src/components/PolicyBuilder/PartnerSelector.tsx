/**
 * PartnerSelector - Component for adding partner BPNs to access policies.
 *
 * Allows users to search/add partner organizations by their
 * Business Partner Numbers (BPNs) for Catena-X / Manufacturing-X dataspaces.
 */

import React, { useState, useCallback } from 'react';
import type { AccessType } from '../../services/dataspaceApi';

export interface Partner {
  bpn: string;
  name: string;
}

interface PartnerSelectorProps {
  /** Currently selected partners */
  partners: Partner[];
  /** Callback when partners change */
  onPartnersChange: (partners: Partner[]) => void;
  /** Current access type */
  accessType: AccessType;
  /** Callback when access type changes */
  onAccessTypeChange: (type: AccessType) => void;
}

/**
 * Validate BPN format (BPNL followed by 12 alphanumeric characters)
 */
function isValidBPN(bpn: string): boolean {
  // BPN format: BPNL + 12 alphanumeric chars (or BPNS/BPNA for sites/addresses)
  const bpnPattern = /^BPN[LSA][0-9A-Z]{12}$/;
  return bpnPattern.test(bpn.toUpperCase());
}

/**
 * Format BPN for display (uppercase)
 */
function formatBPN(bpn: string): string {
  return bpn.toUpperCase().trim();
}

/**
 * PartnerSelector component
 */
export const PartnerSelector: React.FC<PartnerSelectorProps> = ({
  partners,
  onPartnersChange,
  accessType,
  onAccessTypeChange,
}) => {
  const [bpnInput, setBpnInput] = useState('');
  const [nameInput, setNameInput] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleAddPartner = useCallback(() => {
    const formattedBPN = formatBPN(bpnInput);

    // Validate BPN
    if (!formattedBPN) {
      setError('Please enter a BPN');
      return;
    }

    if (!isValidBPN(formattedBPN)) {
      setError('Invalid BPN format. Expected: BPNL followed by 12 characters');
      return;
    }

    // Check for duplicates
    if (partners.some((p) => p.bpn === formattedBPN)) {
      setError('This partner has already been added');
      return;
    }

    // Add partner
    const newPartner: Partner = {
      bpn: formattedBPN,
      name: nameInput.trim() || formattedBPN,
    };

    onPartnersChange([...partners, newPartner]);
    setBpnInput('');
    setNameInput('');
    setError(null);

    // Auto-switch to restricted if adding first partner
    if (partners.length === 0 && accessType !== 'restricted') {
      onAccessTypeChange('restricted');
    }
  }, [bpnInput, nameInput, partners, onPartnersChange, accessType, onAccessTypeChange]);

  const handleRemovePartner = useCallback(
    (bpn: string) => {
      onPartnersChange(partners.filter((p) => p.bpn !== bpn));
    },
    [partners, onPartnersChange]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleAddPartner();
      }
    },
    [handleAddPartner]
  );

  const accessOptions: { type: AccessType; icon: string; label: string }[] = [
    { type: 'public', icon: '\u{1F310}', label: 'Public' },
    { type: 'membership', icon: '\u{1F465}', label: 'Members' },
    { type: 'restricted', icon: '\u{1F512}', label: 'Selected' },
  ];

  return (
    <div className="partner-selector">
      {/* Access Type Quick Selection */}
      <div className="partner-selector__access-type">
        <span className="partner-selector__access-type-label">Access Level</span>
        <div className="partner-selector__access-options">
          {accessOptions.map((option) => (
            <button
              key={option.type}
              type="button"
              className={`partner-selector__access-option ${
                accessType === option.type ? 'partner-selector__access-option--selected' : ''
              }`}
              onClick={() => onAccessTypeChange(option.type)}
            >
              <div className="partner-selector__access-option-icon">{option.icon}</div>
              <div className="partner-selector__access-option-name">{option.label}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Partner Input (only shown for restricted access) */}
      {accessType === 'restricted' && (
        <>
          <div className="partner-selector__input-group">
            <input
              type="text"
              className={`partner-selector__input ${error ? 'partner-selector__input--error' : ''}`}
              placeholder="BPN (e.g., BPNL000000000001)"
              value={bpnInput}
              onChange={(e) => {
                setBpnInput(e.target.value);
                setError(null);
              }}
              onKeyDown={handleKeyDown}
              aria-label="Partner BPN"
            />
            <button
              type="button"
              className="partner-selector__add-btn"
              onClick={handleAddPartner}
              disabled={!bpnInput.trim()}
            >
              Add
            </button>
          </div>

          <input
            type="text"
            className="partner-selector__input"
            placeholder="Partner name (optional)"
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            onKeyDown={handleKeyDown}
            aria-label="Partner name"
          />

          {error && <div className="partner-selector__error">{error}</div>}

          {/* Partner List */}
          <div className="partner-selector__list">
            {partners.length === 0 ? (
              <div className="partner-selector__empty">
                No partners added yet. Add partners by entering their BPN above.
              </div>
            ) : (
              partners.map((partner) => (
                <div key={partner.bpn} className="partner-selector__item">
                  <div className="partner-selector__item-info">
                    <span className="partner-selector__item-name">{partner.name}</span>
                    <span className="partner-selector__item-bpn">{partner.bpn}</span>
                  </div>
                  <button
                    type="button"
                    className="partner-selector__remove-btn"
                    onClick={() => handleRemovePartner(partner.bpn)}
                    aria-label={`Remove ${partner.name}`}
                  >
                    Remove
                  </button>
                </div>
              ))
            )}
          </div>
        </>
      )}

      {/* Info for other access types */}
      {accessType === 'public' && (
        <div className="partner-selector__empty">
          Public access: All dataspace participants can access the selected elements.
        </div>
      )}

      {accessType === 'membership' && (
        <div className="partner-selector__empty">
          Membership access: Only verified dataspace members can access the selected elements.
        </div>
      )}
    </div>
  );
};

export default PartnerSelector;
