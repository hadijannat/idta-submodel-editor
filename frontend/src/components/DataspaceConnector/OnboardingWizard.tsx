/**
 * OnboardingWizard - Multi-step connection wizard.
 *
 * Guides users through the dataspace connection process:
 * 1. Select environment
 * 2. Choose EDC mode
 * 3. Enter credentials (if required)
 * 4. Connect and monitor progress
 */

import { useState, useCallback, useEffect } from 'react';
import type { UseFormReturn } from 'react-hook-form';
import type { SubmodelFormData } from '../../types/aas-elements';
import { useDataspace } from './useDataspace';
import EnvironmentSelector from './EnvironmentSelector';
import EDCModeSelector from './EDCModeSelector';
import ConnectionStatus from './ConnectionStatus';

interface OnboardingWizardProps {
  form?: UseFormReturn<SubmodelFormData>;
  onConnected?: () => void;
  onCancel?: () => void;
}

type WizardStep = 'environment' | 'edc-mode' | 'credentials' | 'connecting';

export default function OnboardingWizard({
  onConnected,
  onCancel,
}: OnboardingWizardProps) {
  const [step, setStep] = useState<WizardStep>('environment');

  const {
    connection,
    environments,
    edcModes,
    isConnecting,
    isLoadingConfig,
    error,
    selectedEnvironment,
    selectedEDCMode,
    bpn,
    credentials,
    setSelectedEnvironment,
    setSelectedEDCMode,
    setBpn,
    setCredentials,
    connect,
    disconnect,
    loadConfig,
    reset,
  } = useDataspace({
    onConnected: () => {
      onConnected?.();
    },
  });

  // Load configuration on mount
  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  // Get selected environment info
  const selectedEnvInfo = environments.find((e) => e.id === selectedEnvironment);
  const requiresBpn = selectedEnvInfo?.requires_bpn ?? false;
  const requiresCredentials = selectedEnvInfo?.requires_credentials ?? false;

  // Handle next step
  const handleNext = useCallback(() => {
    if (step === 'environment') {
      setStep('edc-mode');
    } else if (step === 'edc-mode') {
      if (requiresBpn || requiresCredentials) {
        setStep('credentials');
      } else {
        setStep('connecting');
        connect();
      }
    } else if (step === 'credentials') {
      setStep('connecting');
      connect();
    }
  }, [step, requiresBpn, requiresCredentials, connect]);

  // Handle back
  const handleBack = useCallback(() => {
    if (step === 'edc-mode') {
      setStep('environment');
    } else if (step === 'credentials') {
      setStep('edc-mode');
    } else if (step === 'connecting') {
      disconnect();
      if (requiresBpn || requiresCredentials) {
        setStep('credentials');
      } else {
        setStep('edc-mode');
      }
    }
  }, [step, requiresBpn, requiresCredentials, disconnect]);

  // Handle cancel
  const handleCancel = useCallback(() => {
    reset();
    onCancel?.();
  }, [reset, onCancel]);

  // Handle credential change
  const handleCredentialChange = useCallback(
    (key: string, value: string) => {
      setCredentials({ ...credentials, [key]: value });
    },
    [credentials, setCredentials]
  );

  // Validate credentials step
  const credentialsValid =
    (!requiresBpn || (bpn && bpn.startsWith('BPNL'))) &&
    (!requiresCredentials || Object.values(credentials).some((v) => v));

  if (isLoadingConfig) {
    return (
      <div className="dataspace-wizard">
        <div className="dataspace-wizard__loading">
          <div className="dataspace-wizard__spinner" />
          <p>Loading dataspace configuration...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="dataspace-wizard">
      {/* Step indicator */}
      <div className="dataspace-wizard__steps">
        <div
          className={`dataspace-wizard__step ${
            step === 'environment' ? 'dataspace-wizard__step--active' : ''
          } ${
            step !== 'environment' ? 'dataspace-wizard__step--completed' : ''
          }`}
        >
          <span className="dataspace-wizard__step-number">1</span>
          <span className="dataspace-wizard__step-label">Environment</span>
        </div>
        <div className="dataspace-wizard__step-connector" />
        <div
          className={`dataspace-wizard__step ${
            step === 'edc-mode' ? 'dataspace-wizard__step--active' : ''
          } ${
            step !== 'environment' && step !== 'edc-mode'
              ? 'dataspace-wizard__step--completed'
              : ''
          }`}
        >
          <span className="dataspace-wizard__step-number">2</span>
          <span className="dataspace-wizard__step-label">EDC Mode</span>
        </div>
        {(requiresBpn || requiresCredentials) && (
          <>
            <div className="dataspace-wizard__step-connector" />
            <div
              className={`dataspace-wizard__step ${
                step === 'credentials' ? 'dataspace-wizard__step--active' : ''
              } ${
                step === 'connecting' ? 'dataspace-wizard__step--completed' : ''
              }`}
            >
              <span className="dataspace-wizard__step-number">3</span>
              <span className="dataspace-wizard__step-label">Credentials</span>
            </div>
          </>
        )}
        <div className="dataspace-wizard__step-connector" />
        <div
          className={`dataspace-wizard__step ${
            step === 'connecting' ? 'dataspace-wizard__step--active' : ''
          } ${
            connection?.status === 'connected'
              ? 'dataspace-wizard__step--completed'
              : ''
          }`}
        >
          <span className="dataspace-wizard__step-number">
            {requiresBpn || requiresCredentials ? '4' : '3'}
          </span>
          <span className="dataspace-wizard__step-label">Connect</span>
        </div>
      </div>

      {/* Step content */}
      <div className="dataspace-wizard__content">
        {step === 'environment' && (
          <div className="dataspace-wizard__panel">
            <h3>Select Dataspace Environment</h3>
            <p className="dataspace-wizard__description">
              Choose the dataspace environment you want to connect to. The sandbox
              is recommended for testing and development.
            </p>
            <EnvironmentSelector
              environments={environments}
              selected={selectedEnvironment}
              onChange={setSelectedEnvironment}
            />
          </div>
        )}

        {step === 'edc-mode' && (
          <div className="dataspace-wizard__panel">
            <h3>Choose EDC Integration</h3>
            <p className="dataspace-wizard__description">
              Select how the Eclipse Data Connector should integrate with your AAS
              infrastructure.
            </p>
            <EDCModeSelector
              modes={edcModes}
              selected={selectedEDCMode}
              onChange={setSelectedEDCMode}
            />
          </div>
        )}

        {step === 'credentials' && (
          <div className="dataspace-wizard__panel">
            <h3>Enter Credentials</h3>
            <p className="dataspace-wizard__description">
              Provide the credentials required for the selected environment.
            </p>

            {requiresBpn && (
              <div className="dataspace-wizard__field">
                <label htmlFor="bpn">Business Partner Number (BPN)</label>
                <input
                  id="bpn"
                  type="text"
                  value={bpn}
                  onChange={(e) => setBpn(e.target.value)}
                  placeholder="BPNL0000000000XX"
                  className={`dataspace-wizard__input ${
                    bpn && !bpn.startsWith('BPNL') ? 'dataspace-wizard__input--error' : ''
                  }`}
                />
                {bpn && !bpn.startsWith('BPNL') && (
                  <span className="dataspace-wizard__field-error">
                    BPN must start with &quot;BPNL&quot;
                  </span>
                )}
                <span className="dataspace-wizard__field-help">
                  Your Catena-X Business Partner Number
                </span>
              </div>
            )}

            {requiresCredentials && (
              <>
                <div className="dataspace-wizard__field">
                  <label htmlFor="clientId">Client ID</label>
                  <input
                    id="clientId"
                    type="text"
                    value={credentials.client_id || ''}
                    onChange={(e) => handleCredentialChange('client_id', e.target.value)}
                    placeholder="Enter client ID"
                    className="dataspace-wizard__input"
                  />
                </div>
                <div className="dataspace-wizard__field">
                  <label htmlFor="clientSecret">Client Secret</label>
                  <input
                    id="clientSecret"
                    type="password"
                    value={credentials.client_secret || ''}
                    onChange={(e) =>
                      handleCredentialChange('client_secret', e.target.value)
                    }
                    placeholder="Enter client secret"
                    className="dataspace-wizard__input"
                  />
                </div>
              </>
            )}
          </div>
        )}

        {step === 'connecting' && (
          <div className="dataspace-wizard__panel dataspace-wizard__panel--connecting">
            <h3>Connecting to Dataspace</h3>

            {connection && (
              <div className="dataspace-wizard__connection-info">
                <ConnectionStatus
                  status={connection.status}
                  progress={connection.progress}
                  progressMessage={connection.progress_message}
                  showProgress
                  size="lg"
                />

                <div className="dataspace-wizard__connection-details">
                  <div className="dataspace-wizard__detail">
                    <span className="dataspace-wizard__detail-label">Environment:</span>
                    <span className="dataspace-wizard__detail-value">
                      {selectedEnvInfo?.name || selectedEnvironment}
                    </span>
                  </div>
                  <div className="dataspace-wizard__detail">
                    <span className="dataspace-wizard__detail-label">EDC Mode:</span>
                    <span className="dataspace-wizard__detail-value">
                      {edcModes.find((m) => m.id === selectedEDCMode)?.name ||
                        selectedEDCMode}
                    </span>
                  </div>
                  {bpn && (
                    <div className="dataspace-wizard__detail">
                      <span className="dataspace-wizard__detail-label">BPN:</span>
                      <span className="dataspace-wizard__detail-value">{bpn}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {error && (
              <div className="dataspace-wizard__error">
                <span className="dataspace-wizard__error-icon">!</span>
                <span className="dataspace-wizard__error-text">{error}</span>
              </div>
            )}

            {connection?.status === 'connected' && (
              <div className="dataspace-wizard__success">
                <span className="dataspace-wizard__success-icon">&#10003;</span>
                <span className="dataspace-wizard__success-text">
                  Successfully connected to dataspace!
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="dataspace-wizard__actions">
        {step !== 'environment' && step !== 'connecting' && (
          <button
            type="button"
            className="dataspace-wizard__btn dataspace-wizard__btn--secondary"
            onClick={handleBack}
          >
            Back
          </button>
        )}

        {step === 'connecting' && isConnecting && (
          <button
            type="button"
            className="dataspace-wizard__btn dataspace-wizard__btn--secondary"
            onClick={handleBack}
          >
            Cancel
          </button>
        )}

        {onCancel && step === 'environment' && (
          <button
            type="button"
            className="dataspace-wizard__btn dataspace-wizard__btn--secondary"
            onClick={handleCancel}
          >
            Cancel
          </button>
        )}

        <div className="dataspace-wizard__actions-spacer" />

        {step !== 'connecting' && (
          <button
            type="button"
            className="dataspace-wizard__btn dataspace-wizard__btn--primary"
            onClick={handleNext}
            disabled={step === 'credentials' && !credentialsValid}
          >
            {step === 'credentials' ||
            (step === 'edc-mode' && !requiresBpn && !requiresCredentials)
              ? 'Connect'
              : 'Next'}
          </button>
        )}

        {step === 'connecting' && connection?.status === 'connected' && (
          <button
            type="button"
            className="dataspace-wizard__btn dataspace-wizard__btn--primary"
            onClick={onConnected}
          >
            Continue
          </button>
        )}

        {step === 'connecting' && connection?.status === 'failed' && (
          <button
            type="button"
            className="dataspace-wizard__btn dataspace-wizard__btn--primary"
            onClick={() => connect()}
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
}
