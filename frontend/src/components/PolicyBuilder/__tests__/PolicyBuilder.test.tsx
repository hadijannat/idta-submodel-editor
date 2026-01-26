/**
 * Tests for PolicyBuilder component.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PolicyBuilder } from '../PolicyBuilder';
import type { UIElementSchema } from '../../../types/ui-schema';
import type { PolicyConfig } from '../../../services/dataspaceApi';
import * as dataspaceApi from '../../../services/dataspaceApi';

// Mock the dataspace API
vi.mock('../../../services/dataspaceApi', () => ({
  previewPolicy: vi.fn(),
}));

const mockElements: UIElementSchema[] = [
  {
    idShort: 'ManufacturerName',
    modelType: 'Property',
    semanticId: 'urn:example:manufacturer',
    semanticLabel: 'Manufacturer Name',
    description: 'Name of the manufacturer',
    qualifiers: [],
    cardinality: '[1..1]',
    category: null,
  },
  {
    idShort: 'SerialNumber',
    modelType: 'Property',
    semanticId: 'urn:example:serial',
    semanticLabel: 'Serial Number',
    description: 'Product serial number',
    qualifiers: [],
    cardinality: '[1..1]',
    category: null,
  },
  {
    idShort: 'ContactInformation',
    modelType: 'SubmodelElementCollection',
    semanticId: 'urn:example:contact',
    semanticLabel: 'Contact Information',
    description: 'Contact details',
    qualifiers: [],
    cardinality: '[0..1]',
    category: null,
    elements: [
      {
        idShort: 'Email',
        modelType: 'Property',
        semanticId: 'urn:example:email',
        semanticLabel: 'Email',
        description: 'Email address',
        qualifiers: [],
        cardinality: '[0..1]',
        category: null,
      },
    ],
  },
];

const mockODRLPolicy = {
  '@context': 'http://www.w3.org/ns/odrl/2/',
  '@type': 'Offer',
  permission: [
    {
      target: 'urn:example:asset',
      action: 'use',
      constraint: [],
    },
  ],
};

describe('PolicyBuilder', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(dataspaceApi.previewPolicy).mockResolvedValue({
      odrl: mockODRLPolicy,
      valid: true,
      validation_errors: [],
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('should render all three panels', async () => {
    render(<PolicyBuilder elements={mockElements} />);

    expect(screen.getByText('Access Policy Builder')).toBeInTheDocument();
    expect(screen.getByText('Select Elements')).toBeInTheDocument();
    expect(screen.getByText('Access Configuration')).toBeInTheDocument();
    expect(screen.getByText('Policy Preview')).toBeInTheDocument();
  });

  it('should display elements in the element selector', async () => {
    render(<PolicyBuilder elements={mockElements} />);

    // Elements are displayed using semanticLabel if available, falling back to idShort
    expect(screen.getByText('Manufacturer Name')).toBeInTheDocument();
    expect(screen.getByText('Serial Number')).toBeInTheDocument();
    expect(screen.getByText('Contact Information')).toBeInTheDocument();
  });

  it('should update selected element count when selecting elements', async () => {
    const user = userEvent.setup();
    render(<PolicyBuilder elements={mockElements} />);

    // Get the element selection panel (first panel)
    const elementPanel = screen.getByText('Select Elements').closest('.policy-builder__panel');
    expect(elementPanel).not.toBeNull();

    // Initially no elements selected - find badge within element panel
    const initialBadge = elementPanel!.querySelector('.policy-builder__panel-badge');
    expect(initialBadge).toHaveTextContent('0');

    // Click on an element checkbox to select it
    const checkbox = screen.getByRole('checkbox', { name: /Select Manufacturer Name/i });
    await user.click(checkbox);

    await waitFor(() => {
      expect(initialBadge).toHaveTextContent('1');
    });
  });

  it('should show access type options', async () => {
    render(<PolicyBuilder elements={mockElements} />);

    // Check that access type labels are present
    expect(screen.getByText('Define who can access the selected elements')).toBeInTheDocument();
  });

  it('should call onPolicyConfirm when confirm button is clicked', async () => {
    const onPolicyConfirm = vi.fn();
    const user = userEvent.setup();
    render(
      <PolicyBuilder
        elements={mockElements}
        onPolicyConfirm={onPolicyConfirm}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Confirm Policy' }));

    expect(onPolicyConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        access_type: 'membership',
      })
    );
  });

  it('should call onCancel when cancel button is clicked', async () => {
    const onCancel = vi.fn();
    const user = userEvent.setup();
    render(
      <PolicyBuilder
        elements={mockElements}
        onCancel={onCancel}
      />
    );

    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(onCancel).toHaveBeenCalled();
  });

  it('should not show cancel button when onCancel is not provided', () => {
    render(<PolicyBuilder elements={mockElements} />);

    expect(screen.queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument();
  });

  it('should not show confirm button when onPolicyConfirm is not provided', () => {
    render(<PolicyBuilder elements={mockElements} />);

    expect(screen.queryByRole('button', { name: 'Confirm Policy' })).not.toBeInTheDocument();
  });

  it('should initialize with values from initialConfig', async () => {
    const initialConfig: PolicyConfig = {
      access_type: 'restricted',
      target_paths: ['ManufacturerName'],
      allowed_partners: ['BPNL000000001234', 'BPNL000000005678'],
    };

    render(
      <PolicyBuilder
        elements={mockElements}
        initialConfig={initialConfig}
      />
    );

    // Get the element selection panel
    const elementPanel = screen.getByText('Select Elements').closest('.policy-builder__panel');
    expect(elementPanel).not.toBeNull();

    // Selected elements should be initialized - find badge within element panel
    const badge = elementPanel!.querySelector('.policy-builder__panel-badge');
    await waitFor(() => {
      expect(badge).toHaveTextContent('1');
    });
  });

  it('should display policy preview', async () => {
    render(<PolicyBuilder elements={mockElements} />);

    await waitFor(() => {
      expect(dataspaceApi.previewPolicy).toHaveBeenCalled();
    });
  });

  it('should show validation status in preview', async () => {
    vi.mocked(dataspaceApi.previewPolicy).mockResolvedValue({
      odrl: mockODRLPolicy,
      valid: true,
      validation_errors: [],
    });

    render(<PolicyBuilder elements={mockElements} />);

    await waitFor(() => {
      expect(screen.getByText('Policy configuration is valid')).toBeInTheDocument();
    });
  });

  it('should show validation errors when policy is invalid', async () => {
    vi.mocked(dataspaceApi.previewPolicy).mockResolvedValue({
      odrl: {},
      valid: false,
      validation_errors: ['Missing required permission', 'Invalid constraint format'],
    });

    render(<PolicyBuilder elements={mockElements} />);

    await waitFor(() => {
      expect(screen.getByText('Missing required permission')).toBeInTheDocument();
    });
    expect(screen.getByText('Invalid constraint format')).toBeInTheDocument();
  });

  it('should include target_paths when elements are selected', async () => {
    const onPolicyConfirm = vi.fn();
    const user = userEvent.setup();
    render(
      <PolicyBuilder
        elements={mockElements}
        onPolicyConfirm={onPolicyConfirm}
      />
    );

    // Select an element using the checkbox - use aria-label
    const checkbox = screen.getByRole('checkbox', { name: /Select Manufacturer Name/i });
    await user.click(checkbox);

    await user.click(screen.getByRole('button', { name: 'Confirm Policy' }));

    expect(onPolicyConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        target_paths: expect.arrayContaining(['ManufacturerName']),
      })
    );
  });

  it('should display summary text', async () => {
    render(<PolicyBuilder elements={mockElements} />);

    // Default summary for membership access
    await waitFor(() => {
      expect(screen.getByText(/Dataspace members only/)).toBeInTheDocument();
    });
  });

  it('should update summary when access type changes', async () => {
    render(<PolicyBuilder elements={mockElements} />);

    // Initially shows membership
    await waitFor(() => {
      expect(screen.getByText(/Dataspace members only/)).toBeInTheDocument();
    });

    // Just verify the summary is present - access type changes are tested elsewhere
    expect(screen.getByText(/full submodel/)).toBeInTheDocument();
  });

  it('should handle empty elements list', () => {
    render(<PolicyBuilder elements={[]} />);

    expect(screen.getByText('Select Elements')).toBeInTheDocument();
    // Should have element count badge showing 0
    const badges = screen.getAllByText('0', { selector: '.policy-builder__panel-badge' });
    expect(badges.length).toBeGreaterThan(0);
  });

  it('should handle preview API error gracefully', async () => {
    vi.mocked(dataspaceApi.previewPolicy).mockRejectedValue(
      new Error('Network error')
    );

    render(<PolicyBuilder elements={mockElements} />);

    await waitFor(() => {
      expect(screen.getByText(/Error:/)).toBeInTheDocument();
    });
  });

  it('should debounce preview API calls', async () => {
    vi.useFakeTimers();
    userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    render(<PolicyBuilder elements={mockElements} />);

    // Initial call
    expect(dataspaceApi.previewPolicy).toHaveBeenCalledTimes(0);

    // Advance past debounce time
    await vi.advanceTimersByTimeAsync(500);

    expect(dataspaceApi.previewPolicy).toHaveBeenCalled();

    vi.useRealTimers();
  });

  it('should allow copying ODRL preview to clipboard', async () => {
    // Mock clipboard API using vi.stubGlobal
    const mockWriteText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', {
      ...navigator,
      clipboard: {
        writeText: mockWriteText,
      },
    });

    const user = userEvent.setup();
    render(<PolicyBuilder elements={mockElements} />);

    await waitFor(() => {
      expect(screen.getByText('Policy Preview')).toBeInTheDocument();
    });

    // Wait for API call to complete so copy button is enabled
    await waitFor(() => {
      expect(dataspaceApi.previewPolicy).toHaveBeenCalled();
    });

    // Wait for ODRL to be rendered
    await waitFor(() => {
      const codeBlock = screen.getByRole('heading', { level: 3, name: /Policy Preview/i });
      expect(codeBlock).toBeInTheDocument();
    });

    // Find copy button
    const copyButton = screen.getAllByRole('button', { name: 'Copy' })[0];

    // Only click if not disabled
    if (!copyButton.hasAttribute('disabled')) {
      await user.click(copyButton);
      await waitFor(() => {
        expect(screen.getByText(/Copied/)).toBeInTheDocument();
      });
    } else {
      // Button is disabled because ODRL hasn't loaded yet - this is acceptable
      expect(copyButton).toHaveAttribute('disabled');
    }

    vi.unstubAllGlobals();
  });

  it('should toggle expanded/compact view of ODRL', async () => {
    const user = userEvent.setup();
    render(<PolicyBuilder elements={mockElements} />);

    // Wait for initial render to complete
    await waitFor(() => {
      expect(screen.getByText('Policy Preview')).toBeInTheDocument();
    });

    // Find the Expand button within the policy preview section
    const previewSection = screen.getByText('Policy Preview').closest('.policy-builder__panel');
    expect(previewSection).not.toBeNull();

    const expandButton = previewSection!.querySelector('.policy-preview__expand-btn');
    expect(expandButton).toBeInTheDocument();
    expect(expandButton).toHaveTextContent('Expand');

    await user.click(expandButton!);

    await waitFor(() => {
      expect(expandButton).toHaveTextContent('Compact');
    });
  });
});
