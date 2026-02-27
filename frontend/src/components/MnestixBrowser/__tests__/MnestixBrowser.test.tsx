/**
 * Tests for MnestixBrowser component.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MnestixBrowser from '../MnestixBrowser';
import * as api from '../../../services/api';

// Mock the API
vi.mock('../../../services/api', () => ({
  getPublicSettings: vi.fn(),
}));

describe('MnestixBrowser', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('should show loading state initially', () => {
    vi.mocked(api.getPublicSettings).mockImplementation(() => new Promise(() => {}));

    render(<MnestixBrowser />);

    expect(screen.getByText('Loading AAS Browser...')).toBeInTheDocument();
  });

  it('should show disabled state when mnestix is not enabled', async () => {
    vi.mocked(api.getPublicSettings).mockResolvedValue({
      mnestix_enabled: false,
      mnestix_url: null,
      basyx_registry_url: null,
      dataspace_enabled: false,
      magic_import_enabled: false,
      dpp_enabled: false,
    });

    render(<MnestixBrowser />);

    await waitFor(() => {
      expect(screen.getByText('AAS Browser Not Available')).toBeInTheDocument();
    });
  });

  it('should show error state when mnestix URL is not configured', async () => {
    vi.mocked(api.getPublicSettings).mockResolvedValue({
      mnestix_enabled: true,
      mnestix_url: null,
      basyx_registry_url: null,
      dataspace_enabled: false,
      magic_import_enabled: false,
      dpp_enabled: false,
    });

    render(<MnestixBrowser />);

    await waitFor(() => {
      expect(screen.getByText('Failed to Load AAS Browser')).toBeInTheDocument();
    });
    expect(screen.getByText('Mnestix URL is not configured')).toBeInTheDocument();
  });

  it('should render iframe when settings are valid', async () => {
    vi.mocked(api.getPublicSettings).mockResolvedValue({
      mnestix_enabled: true,
      mnestix_url: 'http://mnestix:3000',
      basyx_registry_url: 'http://registry:4002',
      dataspace_enabled: true,
      magic_import_enabled: true,
      dpp_enabled: false,
    });

    render(<MnestixBrowser />);

    await waitFor(() => {
      expect(screen.getByTitle('Mnestix AAS Browser')).toBeInTheDocument();
    });

    const iframe = screen.getByTitle('Mnestix AAS Browser') as HTMLIFrameElement;
    expect(iframe.src).toContain('http://mnestix:3000');
    expect(iframe.src).toContain('aasRegistry=http%3A%2F%2Fregistry%3A4002');
  });

  it('should call onClose when Close Browser button is clicked', async () => {
    const onClose = vi.fn();
    vi.mocked(api.getPublicSettings).mockResolvedValue({
      mnestix_enabled: true,
      mnestix_url: 'http://mnestix:3000',
      basyx_registry_url: null,
      dataspace_enabled: false,
      magic_import_enabled: false,
      dpp_enabled: false,
    });

    const user = userEvent.setup();
    render(<MnestixBrowser onClose={onClose} />);

    await waitFor(() => {
      expect(screen.getByText('Close Browser')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Close Browser'));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('should show error state when API call fails', async () => {
    vi.mocked(api.getPublicSettings).mockRejectedValue(new Error('Network error'));

    render(<MnestixBrowser />);

    await waitFor(() => {
      expect(screen.getByText('Failed to Load AAS Browser')).toBeInTheDocument();
    });
    expect(screen.getByText('Failed to load browser settings')).toBeInTheDocument();
  });

  it('should render Open in New Tab link with correct URL', async () => {
    vi.mocked(api.getPublicSettings).mockResolvedValue({
      mnestix_enabled: true,
      mnestix_url: 'http://mnestix:3000',
      basyx_registry_url: 'http://registry:4002',
      dataspace_enabled: false,
      magic_import_enabled: false,
      dpp_enabled: false,
    });

    render(<MnestixBrowser />);

    await waitFor(() => {
      expect(screen.getByText('Open in New Tab')).toBeInTheDocument();
    });

    const link = screen.getByText('Open in New Tab') as HTMLAnchorElement;
    expect(link.href).toContain('http://mnestix:3000');
    expect(link.target).toBe('_blank');
    expect(link.rel).toContain('noopener');
  });
});
