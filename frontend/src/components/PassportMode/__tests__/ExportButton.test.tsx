/**
 * Tests for ExportButton component.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { ExportButton } from '../ExportButton';
import * as exportImage from '../utils/exportImage';

// Mock the exportImage utilities
vi.mock('../utils/exportImage', () => ({
  exportToPng: vi.fn(),
  isExportSupported: vi.fn(() => true),
}));

// Mock i18n
vi.mock('../i18n', () => ({
  usePassportI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'export.button': 'Export',
        'export.tooltip': 'Export card as PNG image',
        'export.exporting': 'Exporting...',
        'export.success': 'Card exported successfully',
        'export.error': 'Export failed',
        'export.unsupported': 'Export not supported',
      };
      return translations[key] || key;
    },
  }),
}));

describe('ExportButton', () => {
  let mockCardRef: React.RefObject<HTMLDivElement>;
  let mockElement: HTMLDivElement;

  beforeEach(() => {
    mockElement = document.createElement('div');
    mockCardRef = { current: mockElement };

    vi.mocked(exportImage.isExportSupported).mockReturnValue(true);
    vi.mocked(exportImage.exportToPng).mockResolvedValue({
      success: true,
      filename: 'test.png',
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders when export is supported', () => {
      render(<ExportButton cardRef={mockCardRef} />);

      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('does not render when export is not supported', () => {
      vi.mocked(exportImage.isExportSupported).mockReturnValue(false);

      const { container } = render(<ExportButton cardRef={mockCardRef} />);

      expect(container.firstChild).toBeNull();
    });

    it('displays export button text', () => {
      render(<ExportButton cardRef={mockCardRef} />);

      expect(screen.getByText('Export')).toBeInTheDocument();
    });

    it('has correct tooltip/aria-label', () => {
      render(<ExportButton cardRef={mockCardRef} />);

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('title', 'Export card as PNG image');
      expect(button).toHaveAttribute('aria-label', 'Export card as PNG image');
    });

    it('has data-export-ignore attribute to exclude itself from exports', () => {
      render(<ExportButton cardRef={mockCardRef} />);

      const button = screen.getByRole('button');
      expect(button).toHaveAttribute('data-export-ignore', 'true');
    });
  });

  describe('disabled state', () => {
    it('is disabled when disabled prop is true', () => {
      render(<ExportButton cardRef={mockCardRef} disabled={true} />);

      expect(screen.getByRole('button')).toBeDisabled();
    });

    it('has disabled class when disabled', () => {
      render(<ExportButton cardRef={mockCardRef} disabled={true} />);

      expect(screen.getByRole('button')).toHaveClass('passport-export-button--disabled');
    });

    it('does not trigger export when disabled', async () => {
      render(<ExportButton cardRef={mockCardRef} disabled={true} />);

      fireEvent.click(screen.getByRole('button'));

      expect(exportImage.exportToPng).not.toHaveBeenCalled();
    });
  });

  describe('export flow', () => {
    it('calls exportToPng when clicked', async () => {
      render(<ExportButton cardRef={mockCardRef} passportType="nameplate" />);

      fireEvent.click(screen.getByRole('button'));

      await waitFor(() => {
        expect(exportImage.exportToPng).toHaveBeenCalledWith(
          mockElement,
          expect.objectContaining({ filename: 'Digital-Nameplate' })
        );
      });
    });

    it('uses correct filename for nameplate type', async () => {
      render(<ExportButton cardRef={mockCardRef} passportType="nameplate" />);

      fireEvent.click(screen.getByRole('button'));

      await waitFor(() => {
        expect(exportImage.exportToPng).toHaveBeenCalledWith(
          mockElement,
          expect.objectContaining({ filename: 'Digital-Nameplate' })
        );
      });
    });

    it('uses correct filename for pcf type', async () => {
      render(<ExportButton cardRef={mockCardRef} passportType="pcf" />);

      fireEvent.click(screen.getByRole('button'));

      await waitFor(() => {
        expect(exportImage.exportToPng).toHaveBeenCalledWith(
          mockElement,
          expect.objectContaining({ filename: 'Product-Carbon-Footprint' })
        );
      });
    });

    it('uses correct filename for generic type', async () => {
      render(<ExportButton cardRef={mockCardRef} passportType="generic" />);

      fireEvent.click(screen.getByRole('button'));

      await waitFor(() => {
        expect(exportImage.exportToPng).toHaveBeenCalledWith(
          mockElement,
          expect.objectContaining({ filename: 'Passport-Card' })
        );
      });
    });

    it('uses default filename when no type specified', async () => {
      render(<ExportButton cardRef={mockCardRef} />);

      fireEvent.click(screen.getByRole('button'));

      await waitFor(() => {
        expect(exportImage.exportToPng).toHaveBeenCalledWith(
          mockElement,
          expect.objectContaining({ filename: 'Passport-Card' })
        );
      });
    });
  });

  describe('loading state', () => {
    it('shows loading state while exporting', async () => {
      // Make exportToPng take some time
      vi.mocked(exportImage.exportToPng).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve({ success: true }), 100))
      );

      render(<ExportButton cardRef={mockCardRef} />);

      fireEvent.click(screen.getByRole('button'));

      expect(screen.getByRole('button')).toHaveClass('passport-export-button--loading');
      expect(screen.getByText('Exporting...')).toBeInTheDocument();
    });

    it('is disabled while exporting', async () => {
      vi.mocked(exportImage.exportToPng).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve({ success: true }), 100))
      );

      render(<ExportButton cardRef={mockCardRef} />);

      fireEvent.click(screen.getByRole('button'));

      expect(screen.getByRole('button')).toBeDisabled();
    });

    it('prevents multiple clicks while exporting', async () => {
      vi.mocked(exportImage.exportToPng).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve({ success: true }), 100))
      );

      render(<ExportButton cardRef={mockCardRef} />);

      fireEvent.click(screen.getByRole('button'));
      fireEvent.click(screen.getByRole('button'));
      fireEvent.click(screen.getByRole('button'));

      expect(exportImage.exportToPng).toHaveBeenCalledTimes(1);
    });

    it('ignores late export results after unmount', async () => {
      const onSuccess = vi.fn();
      let resolveExport!: (value: exportImage.ExportResult) => void;
      vi.mocked(exportImage.exportToPng).mockImplementation(
        () =>
          new Promise((resolve) => {
            resolveExport = resolve;
          })
      );

      const { unmount } = render(
        <ExportButton cardRef={mockCardRef} onExportSuccess={onSuccess} />
      );

      fireEvent.click(screen.getByRole('button'));
      unmount();

      await act(async () => {
        resolveExport({ success: true, filename: 'late.png' });
      });

      expect(onSuccess).not.toHaveBeenCalled();
    });
  });

  describe('success state', () => {
    it('shows success class after successful export', async () => {
      vi.mocked(exportImage.exportToPng).mockResolvedValue({
        success: true,
        filename: 'test.png',
      });

      render(<ExportButton cardRef={mockCardRef} />);

      fireEvent.click(screen.getByRole('button'));

      await waitFor(() => {
        expect(screen.getByRole('button')).toHaveClass('passport-export-button--success');
      });
    });

    it('calls onExportSuccess callback on success', async () => {
      const onSuccess = vi.fn();
      vi.mocked(exportImage.exportToPng).mockResolvedValue({
        success: true,
        filename: 'test.png',
      });

      render(<ExportButton cardRef={mockCardRef} onExportSuccess={onSuccess} />);

      fireEvent.click(screen.getByRole('button'));

      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalledWith('test.png');
      });
    });
  });

  describe('error state', () => {
    it('shows error class after failed export', async () => {
      vi.mocked(exportImage.exportToPng).mockResolvedValue({
        success: false,
        error: 'Canvas error',
      });

      render(<ExportButton cardRef={mockCardRef} />);

      fireEvent.click(screen.getByRole('button'));

      await waitFor(() => {
        expect(screen.getByRole('button')).toHaveClass('passport-export-button--error');
      });
    });

    it('calls onExportError callback on error', async () => {
      const onError = vi.fn();
      vi.mocked(exportImage.exportToPng).mockResolvedValue({
        success: false,
        error: 'Canvas error',
      });

      render(<ExportButton cardRef={mockCardRef} onExportError={onError} />);

      fireEvent.click(screen.getByRole('button'));

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith('Canvas error');
      });
    });

    it('handles thrown exceptions', async () => {
      const onError = vi.fn();
      vi.mocked(exportImage.exportToPng).mockRejectedValue(new Error('Unexpected error'));

      render(<ExportButton cardRef={mockCardRef} onExportError={onError} />);

      fireEvent.click(screen.getByRole('button'));

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith('Unexpected error');
      });
    });
  });

  describe('null ref handling', () => {
    it('does not call export when ref is null', async () => {
      const nullRef = { current: null };

      render(<ExportButton cardRef={nullRef} />);

      fireEvent.click(screen.getByRole('button'));

      expect(exportImage.exportToPng).not.toHaveBeenCalled();
    });
  });

  describe('CSS classes', () => {
    it('has base class', () => {
      render(<ExportButton cardRef={mockCardRef} />);

      expect(screen.getByRole('button')).toHaveClass('passport-export-button');
    });

    it('button has correct type attribute', () => {
      render(<ExportButton cardRef={mockCardRef} />);

      expect(screen.getByRole('button')).toHaveAttribute('type', 'button');
    });
  });

  describe('accessibility', () => {
    it('has accessible name', () => {
      render(<ExportButton cardRef={mockCardRef} />);

      expect(screen.getByRole('button', { name: /export/i })).toBeInTheDocument();
    });

    it('updates aria-label during loading', async () => {
      vi.mocked(exportImage.exportToPng).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve({ success: true }), 100))
      );

      render(<ExportButton cardRef={mockCardRef} />);

      fireEvent.click(screen.getByRole('button'));

      expect(screen.getByRole('button')).toHaveAttribute('aria-label', 'Exporting...');
    });
  });
});

describe('ExportButton module exports', () => {
  it('exports ExportButton as named export', () => {
    expect(ExportButton).toBeDefined();
    expect(typeof ExportButton).toBe('function');
  });
});
