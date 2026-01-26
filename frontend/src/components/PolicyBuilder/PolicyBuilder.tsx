/**
 * PolicyBuilder - Main 3-panel layout for building ODRL access policies.
 *
 * Layout:
 * - Left panel: Select elements from AAS tree
 * - Middle panel: Add partner BPNs and configure access type
 * - Right panel: Live ODRL JSON preview with validation
 */

import React, { useState, useCallback, useMemo } from 'react';
import type { UIElementSchema } from '../../types/ui-schema';
import type { PolicyConfig, AccessType } from '../../services/dataspaceApi';
import ElementSelector, { type SelectedElement } from './ElementSelector';
import PartnerSelector, { type Partner } from './PartnerSelector';
import AccessLevelPicker, { type AccessScope } from './AccessLevelPicker';
import PolicyPreview from './PolicyPreview';
import './PolicyBuilder.css';

interface PolicyBuilderProps {
  /** UI schema elements to select from */
  elements: UIElementSchema[];
  /** Callback when policy is confirmed */
  onPolicyConfirm?: (config: PolicyConfig) => void;
  /** Callback when cancelled */
  onCancel?: () => void;
  /** Initial policy config (for editing) */
  initialConfig?: PolicyConfig;
}

/**
 * PolicyBuilder component
 */
export const PolicyBuilder: React.FC<PolicyBuilderProps> = ({
  elements,
  onPolicyConfirm,
  onCancel,
  initialConfig,
}) => {
  // Element selection state
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(() => {
    if (initialConfig?.target_paths?.length) {
      return new Set(initialConfig.target_paths);
    }
    return new Set();
  });
  // Track selected elements for potential future use (e.g., showing labels)
  const [, setSelectedElements] = useState<SelectedElement[]>([]);

  // Partner selection state
  const [partners, setPartners] = useState<Partner[]>(() => {
    if (initialConfig?.allowed_partners?.length) {
      return initialConfig.allowed_partners.map((bpn) => ({ bpn, name: bpn }));
    }
    return [];
  });

  // Access configuration state
  const [accessType, setAccessType] = useState<AccessType>(
    initialConfig?.access_type || 'membership'
  );
  const [accessScope, setAccessScope] = useState<AccessScope>(() => {
    if (initialConfig?.valid_from || initialConfig?.valid_until) {
      return 'time-limited';
    }
    if (initialConfig?.target_paths?.length) {
      return 'selective';
    }
    return 'full';
  });
  const [validFrom, setValidFrom] = useState<string | null>(
    initialConfig?.valid_from || null
  );
  const [validUntil, setValidUntil] = useState<string | null>(
    initialConfig?.valid_until || null
  );

  // Handle element selection change
  const handleSelectionChange = useCallback(
    (paths: Set<string>, selected: SelectedElement[]) => {
      setSelectedPaths(paths);
      setSelectedElements(selected);

      // Auto-switch to selective scope when elements are selected
      if (paths.size > 0 && accessScope === 'full') {
        setAccessScope('selective');
      }
    },
    [accessScope]
  );

  // Handle partners change
  const handlePartnersChange = useCallback((newPartners: Partner[]) => {
    setPartners(newPartners);
  }, []);

  // Build policy config for preview
  const policyConfig = useMemo<PolicyConfig>(() => {
    const config: PolicyConfig = {
      access_type: accessType,
    };

    // Add target paths for selective access
    if (accessScope === 'selective' && selectedPaths.size > 0) {
      config.target_paths = Array.from(selectedPaths);
    }

    // Add allowed partners for restricted access
    if (accessType === 'restricted' && partners.length > 0) {
      config.allowed_partners = partners.map((p) => p.bpn);
    }

    // Add time constraints
    if (accessScope === 'time-limited') {
      if (validFrom) {
        config.valid_from = new Date(validFrom).toISOString();
      }
      if (validUntil) {
        config.valid_until = new Date(validUntil).toISOString();
      }
    }

    return config;
  }, [accessType, accessScope, selectedPaths, partners, validFrom, validUntil]);

  // Handle confirm
  const handleConfirm = useCallback(() => {
    onPolicyConfirm?.(policyConfig);
  }, [policyConfig, onPolicyConfirm]);

  // Summary text
  const summaryText = useMemo(() => {
    const parts: string[] = [];

    // Access type
    if (accessType === 'public') {
      parts.push('Public access');
    } else if (accessType === 'membership') {
      parts.push('Dataspace members only');
    } else {
      parts.push(`${partners.length} selected partner(s)`);
    }

    // Scope
    if (accessScope === 'selective') {
      parts.push(`${selectedPaths.size} element(s)`);
    } else if (accessScope === 'time-limited') {
      parts.push('time-limited');
    } else {
      parts.push('full submodel');
    }

    return parts.join(' \u2022 ');
  }, [accessType, accessScope, selectedPaths.size, partners.length]);

  return (
    <div className="policy-builder">
      <div className="policy-builder__header">
        <h2>Access Policy Builder</h2>
        <p className="policy-builder__subtitle">
          Configure who can access which parts of your submodel data
        </p>
      </div>

      <div className="policy-builder__panels">
        {/* Left Panel: Element Selection */}
        <div className="policy-builder__panel">
          <div className="policy-builder__panel-header">
            <h3>
              Select Elements
              <span
                className={`policy-builder__panel-badge ${
                  selectedPaths.size === 0 ? 'policy-builder__panel-badge--muted' : ''
                }`}
              >
                {selectedPaths.size}
              </span>
            </h3>
            <p>Choose which elements to include in the policy</p>
          </div>
          <div className="policy-builder__panel-content">
            <ElementSelector
              elements={elements}
              selectedPaths={selectedPaths}
              onSelectionChange={handleSelectionChange}
            />
          </div>
        </div>

        {/* Middle Panel: Partner Selection & Access Type */}
        <div className="policy-builder__panel">
          <div className="policy-builder__panel-header">
            <h3>
              Access Configuration
              <span
                className={`policy-builder__panel-badge ${
                  partners.length === 0 ? 'policy-builder__panel-badge--muted' : ''
                }`}
              >
                {partners.length}
              </span>
            </h3>
            <p>Define who can access the selected elements</p>
          </div>
          <div className="policy-builder__panel-content">
            <PartnerSelector
              partners={partners}
              onPartnersChange={handlePartnersChange}
              accessType={accessType}
              onAccessTypeChange={setAccessType}
            />

            <div style={{ marginTop: 24 }}>
              <AccessLevelPicker
                scope={accessScope}
                onScopeChange={setAccessScope}
                validFrom={validFrom}
                validUntil={validUntil}
                onValidFromChange={setValidFrom}
                onValidUntilChange={setValidUntil}
                hasElementSelection={true}
                selectedElementCount={selectedPaths.size}
              />
            </div>
          </div>
        </div>

        {/* Right Panel: Policy Preview */}
        <div className="policy-builder__panel">
          <div className="policy-builder__panel-header">
            <h3>Policy Preview</h3>
            <p>Live ODRL policy JSON with validation</p>
          </div>
          <div className="policy-builder__panel-content">
            <PolicyPreview config={policyConfig} />
          </div>
        </div>
      </div>

      {/* Footer Actions */}
      <div className="policy-builder__footer">
        <div className="policy-builder__footer-info">{summaryText}</div>
        <div className="policy-builder__footer-actions">
          {onCancel && (
            <button
              type="button"
              className="policy-builder__btn--secondary"
              onClick={onCancel}
            >
              Cancel
            </button>
          )}
          {onPolicyConfirm && (
            <button
              type="button"
              className="policy-builder__btn--primary"
              onClick={handleConfirm}
            >
              Confirm Policy
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default PolicyBuilder;
