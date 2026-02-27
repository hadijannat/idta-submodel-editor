import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import { ExportPanel } from '../index';

describe('ExportPanel', () => {
  const baseProps = {
    templateName: 'Digital Nameplate',
    onExportAasx: vi.fn(async () => {}),
    onExportJson: vi.fn(async () => {}),
    onExportPdf: vi.fn(async () => {}),
    onVerify: vi.fn(async () => {}),
    onValidate: vi.fn(async () => true),
    onReset: vi.fn(),
  };

  it('renders conformance summary when available', () => {
    render(
      <ExportPanel
        {...baseProps}
        conformanceResult={{
          passed: false,
          errors: [{ level: 'error', message: 'Missing AssetInformation.assetKind' }],
          warnings: [{ level: 'warning', message: 'Recommended field missing' }],
          engine_version: '0.3.1',
          duration_ms: 123,
          format: 'aasx',
        }}
      />
    );

    expect(screen.getByText('✗ AAS conformance check failed')).toBeInTheDocument();
    expect(
      screen.getByText(/Missing AssetInformation\.assetKind/)
    ).toBeInTheDocument();
    expect(screen.getByText(/Recommended field missing/)).toBeInTheDocument();
    expect(screen.getByText(/Engine: 0.3.1/)).toBeInTheDocument();
  });

  it('disables verify while conformance check is running', () => {
    render(<ExportPanel {...baseProps} conformanceChecking />);
    const verifyButton = screen.getByRole('button', { name: /Verifying\.\.\./i });
    expect(verifyButton).toBeDisabled();
  });
});
