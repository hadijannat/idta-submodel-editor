/**
 * Tests for PublicationManager component.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PublicationManager from '../PublicationManager';
import * as dataspaceApi from '../../../services/dataspaceApi';

// Mock the dataspace API
vi.mock('../../../services/dataspaceApi', () => ({
  createPublication: vi.fn(),
  listPublications: vi.fn(),
  getPublication: vi.fn(),
  deletePublication: vi.fn(),
  pollPublicationStatus: vi.fn(),
}));

// Mock window.confirm
const originalConfirm = window.confirm;

const mockPublications: dataspaceApi.SubmodelPublication[] = [
  {
    publication_id: 'pub-123',
    connection_id: 'conn-123',
    template_name: 'DigitalNameplate',
    submodel_id: 'urn:submodel:nameplate:123',
    status: 'published',
    aas_endpoint: 'http://basyx:8081/shells/aas123',
    dtr_asset_id: 'dtr-asset-123',
    edc_offer_id: 'edc-offer-123',
    policy_id: 'policy-123',
    created_at: '2024-01-15T10:30:00Z',
    updated_at: '2024-01-15T10:30:00Z',
  },
  {
    publication_id: 'pub-456',
    connection_id: 'conn-123',
    template_name: 'PCF',
    submodel_id: 'urn:submodel:pcf:456',
    status: 'pending',
    aas_endpoint: null,
    dtr_asset_id: null,
    edc_offer_id: null,
    policy_id: null,
    created_at: '2024-01-14T09:00:00Z',
    updated_at: '2024-01-14T09:00:00Z',
  },
  {
    publication_id: 'pub-789',
    connection_id: 'conn-123',
    template_name: 'ContactInfo',
    submodel_id: 'urn:submodel:contact:789',
    status: 'failed',
    aas_endpoint: null,
    dtr_asset_id: null,
    edc_offer_id: null,
    policy_id: null,
    created_at: '2024-01-13T08:00:00Z',
    updated_at: '2024-01-13T08:00:00Z',
  },
];

describe('PublicationManager', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.confirm = vi.fn(() => true);
    vi.mocked(dataspaceApi.listPublications).mockResolvedValue({
      publications: mockPublications,
      total: 3,
    });
  });

  afterEach(() => {
    window.confirm = originalConfirm;
    cleanup();
  });

  it('should show loading state initially', async () => {
    vi.mocked(dataspaceApi.listPublications).mockImplementation(
      () => new Promise(() => {})
    );

    render(<PublicationManager connectionId="conn-123" />);

    expect(screen.getByText('Loading publications...')).toBeInTheDocument();
  });

  it('should display publications list', async () => {
    render(<PublicationManager connectionId="conn-123" />);

    await waitFor(() => {
      expect(screen.getByText('DigitalNameplate')).toBeInTheDocument();
    });

    expect(screen.getByText('PCF')).toBeInTheDocument();
    expect(screen.getByText('ContactInfo')).toBeInTheDocument();
  });

  it('should display publication status badges', async () => {
    render(<PublicationManager connectionId="conn-123" />);

    await waitFor(() => {
      expect(screen.getByText('Published')).toBeInTheDocument();
    });

    expect(screen.getByText('Pending')).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });

  it('should show empty state when no publications', async () => {
    vi.mocked(dataspaceApi.listPublications).mockResolvedValue({
      publications: [],
      total: 0,
    });

    render(<PublicationManager connectionId="conn-123" />);

    await waitFor(() => {
      expect(screen.getByText('No publications yet')).toBeInTheDocument();
    });

    expect(
      screen.getByText('Publish your first submodel to the dataspace')
    ).toBeInTheDocument();
  });

  it('should show error state on load failure', async () => {
    vi.mocked(dataspaceApi.listPublications).mockRejectedValue(
      new Error('Network error')
    );

    render(<PublicationManager connectionId="conn-123" />);

    await waitFor(() => {
      expect(screen.getByText('Error: Network error')).toBeInTheDocument();
    });
  });

  it('should filter publications by status', async () => {
    const user = userEvent.setup();
    render(<PublicationManager connectionId="conn-123" />);

    await waitFor(() => {
      expect(screen.getByText('DigitalNameplate')).toBeInTheDocument();
    });

    // Find filter buttons using more specific approach
    const filterButtons = screen.getAllByRole('button');
    const publishedFilterButton = filterButtons.find((btn) =>
      btn.textContent?.includes('Published (')
    );
    const failedFilterButton = filterButtons.find((btn) =>
      btn.textContent?.includes('Failed/Unpublished')
    );
    const allFilterButton = filterButtons.find((btn) =>
      btn.textContent?.match(/^All \(\d+\)$/)
    );

    expect(publishedFilterButton).toBeDefined();
    expect(failedFilterButton).toBeDefined();
    expect(allFilterButton).toBeDefined();

    // Filter by published
    await user.click(publishedFilterButton!);

    await waitFor(() => {
      expect(screen.getByText('DigitalNameplate')).toBeInTheDocument();
    });
    expect(screen.queryByText('PCF')).not.toBeInTheDocument();
    expect(screen.queryByText('ContactInfo')).not.toBeInTheDocument();

    // Filter by failed
    await user.click(failedFilterButton!);

    await waitFor(() => {
      expect(screen.getByText('ContactInfo')).toBeInTheDocument();
    });
    expect(screen.queryByText('DigitalNameplate')).not.toBeInTheDocument();

    // Show all
    await user.click(allFilterButton!);

    await waitFor(() => {
      expect(screen.getByText('DigitalNameplate')).toBeInTheDocument();
      expect(screen.getByText('PCF')).toBeInTheDocument();
      expect(screen.getByText('ContactInfo')).toBeInTheDocument();
    });
  });

  it('should search publications', async () => {
    const user = userEvent.setup();
    render(<PublicationManager connectionId="conn-123" />);

    await waitFor(() => {
      expect(screen.getByText('DigitalNameplate')).toBeInTheDocument();
    });

    // Search for nameplate
    await user.type(screen.getByPlaceholderText('Search publications...'), 'nameplate');

    await waitFor(() => {
      expect(screen.getByText('DigitalNameplate')).toBeInTheDocument();
    });
    expect(screen.queryByText('PCF')).not.toBeInTheDocument();
    expect(screen.queryByText('ContactInfo')).not.toBeInTheDocument();
  });

  it('should show no matches message when search has no results', async () => {
    const user = userEvent.setup();
    render(<PublicationManager connectionId="conn-123" />);

    await waitFor(() => {
      expect(screen.getByText('DigitalNameplate')).toBeInTheDocument();
    });

    // Search for non-existent term
    await user.type(screen.getByPlaceholderText('Search publications...'), 'xyz123');

    await waitFor(() => {
      expect(screen.getByText('No publications match your filters')).toBeInTheDocument();
    });
  });

  it('should clear filters', async () => {
    const user = userEvent.setup();
    render(<PublicationManager connectionId="conn-123" />);

    await waitFor(() => {
      expect(screen.getByText('DigitalNameplate')).toBeInTheDocument();
    });

    // Apply search filter
    await user.type(screen.getByPlaceholderText('Search publications...'), 'xyz123');

    await waitFor(() => {
      expect(screen.getByText('No publications match your filters')).toBeInTheDocument();
    });

    // Clear filters
    await user.click(screen.getByRole('button', { name: 'Clear filters' }));

    await waitFor(() => {
      expect(screen.getByText('DigitalNameplate')).toBeInTheDocument();
    });
  });

  it('should refresh publications list', async () => {
    const user = userEvent.setup();
    render(<PublicationManager connectionId="conn-123" />);

    await waitFor(() => {
      expect(screen.getByText('DigitalNameplate')).toBeInTheDocument();
    });

    // Click refresh button (it uses title attribute)
    const refreshButton = screen.getByTitle('Refresh publications');
    await user.click(refreshButton);

    await waitFor(() => {
      expect(dataspaceApi.listPublications).toHaveBeenCalledTimes(2);
    });
  });

  it('should call onPublish when publish button is clicked', async () => {
    const onPublish = vi.fn();
    const user = userEvent.setup();
    render(<PublicationManager connectionId="conn-123" onPublish={onPublish} />);

    await waitFor(() => {
      expect(screen.getByText('+ Publish Submodel')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: '+ Publish Submodel' }));

    expect(onPublish).toHaveBeenCalled();
  });

  it('should handle unpublish with confirmation', async () => {
    vi.mocked(dataspaceApi.deletePublication).mockResolvedValue({
      publication_id: 'pub-123',
      status: 'unpublished',
      message: 'Unpublished successfully',
    });

    const user = userEvent.setup();
    render(<PublicationManager connectionId="conn-123" />);

    await waitFor(() => {
      expect(screen.getByText('DigitalNameplate')).toBeInTheDocument();
    });

    // Find the published publication row and click unpublish
    const publishedRow = screen.getByText('DigitalNameplate').closest('.dataspace-publication');
    expect(publishedRow).not.toBeNull();

    const unpublishButton = within(publishedRow!).getByTitle('Unpublish');
    await user.click(unpublishButton);

    expect(window.confirm).toHaveBeenCalledWith(
      'Are you sure you want to unpublish this submodel? This will remove it from the dataspace.'
    );

    await waitFor(() => {
      expect(dataspaceApi.deletePublication).toHaveBeenCalledWith('pub-123');
    });
  });

  it('should not unpublish when confirmation is cancelled', async () => {
    window.confirm = vi.fn(() => false);

    const user = userEvent.setup();
    render(<PublicationManager connectionId="conn-123" />);

    await waitFor(() => {
      expect(screen.getByText('DigitalNameplate')).toBeInTheDocument();
    });

    const publishedRow = screen.getByText('DigitalNameplate').closest('.dataspace-publication');
    const unpublishButton = within(publishedRow!).getByTitle('Unpublish');
    await user.click(unpublishButton);

    expect(dataspaceApi.deletePublication).not.toHaveBeenCalled();
  });

  it('should refresh single publication status', async () => {
    const updatedPublication = {
      ...mockPublications[0],
      updated_at: '2024-01-15T12:00:00Z',
    };
    vi.mocked(dataspaceApi.getPublication).mockResolvedValue(updatedPublication);

    const user = userEvent.setup();
    render(<PublicationManager connectionId="conn-123" />);

    await waitFor(() => {
      expect(screen.getByText('DigitalNameplate')).toBeInTheDocument();
    });

    const publishedRow = screen.getByText('DigitalNameplate').closest('.dataspace-publication');
    const refreshButton = within(publishedRow!).getByTitle('Refresh status');
    await user.click(refreshButton);

    await waitFor(() => {
      expect(dataspaceApi.getPublication).toHaveBeenCalledWith('pub-123');
    });
  });

  it('should display publication details', async () => {
    render(<PublicationManager connectionId="conn-123" />);

    await waitFor(() => {
      expect(screen.getByText('DigitalNameplate')).toBeInTheDocument();
    });

    // Check submodel ID is displayed
    expect(screen.getByText('urn:submodel:nameplate:123')).toBeInTheDocument();

    // Check AAS endpoint is displayed for published item
    expect(screen.getByText('http://basyx:8081/shells/aas123')).toBeInTheDocument();

    // Check EDC offer is displayed
    expect(screen.getByText('edc-offer-123')).toBeInTheDocument();
  });

  it('should call onSelectPublication when clicking a publication', async () => {
    const onSelectPublication = vi.fn();
    const user = userEvent.setup();
    render(
      <PublicationManager
        connectionId="conn-123"
        onSelectPublication={onSelectPublication}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('DigitalNameplate')).toBeInTheDocument();
    });

    await user.click(screen.getByText('DigitalNameplate'));

    expect(onSelectPublication).toHaveBeenCalledWith(mockPublications[0]);
  });

  it('should show publication count summary', async () => {
    render(<PublicationManager connectionId="conn-123" />);

    await waitFor(() => {
      expect(screen.getByText('3 of 3 publications')).toBeInTheDocument();
    });
  });

  it('should update summary when filtered', async () => {
    const user = userEvent.setup();
    render(<PublicationManager connectionId="conn-123" />);

    await waitFor(() => {
      expect(screen.getByText('3 of 3 publications')).toBeInTheDocument();
    });

    // Find the published filter button
    const filterButtons = screen.getAllByRole('button');
    const publishedFilterButton = filterButtons.find((btn) =>
      btn.textContent?.includes('Published (')
    );

    expect(publishedFilterButton).toBeDefined();
    await user.click(publishedFilterButton!);

    await waitFor(() => {
      expect(screen.getByText('1 of 3 publications')).toBeInTheDocument();
    });
  });

  it('should not show unpublish button for non-published items', async () => {
    render(<PublicationManager connectionId="conn-123" />);

    await waitFor(() => {
      expect(screen.getByText('PCF')).toBeInTheDocument();
    });

    // PCF is pending, should not have unpublish button
    const pendingRow = screen.getByText('PCF').closest('.dataspace-publication');
    expect(within(pendingRow!).queryByTitle('Unpublish')).not.toBeInTheDocument();

    // Failed item should not have unpublish button
    const failedRow = screen.getByText('ContactInfo').closest('.dataspace-publication');
    expect(within(failedRow!).queryByTitle('Unpublish')).not.toBeInTheDocument();
  });

  it('should show empty state publish button when no publications', async () => {
    vi.mocked(dataspaceApi.listPublications).mockResolvedValue({
      publications: [],
      total: 0,
    });

    const onPublish = vi.fn();
    const user = userEvent.setup();
    render(<PublicationManager connectionId="conn-123" onPublish={onPublish} />);

    await waitFor(() => {
      expect(screen.getByText('No publications yet')).toBeInTheDocument();
    });

    // The empty state should also have a publish button
    const buttons = screen.getAllByRole('button', { name: '+ Publish Submodel' });
    expect(buttons.length).toBeGreaterThan(0);

    await user.click(buttons[0]);
    expect(onPublish).toHaveBeenCalled();
  });
});
