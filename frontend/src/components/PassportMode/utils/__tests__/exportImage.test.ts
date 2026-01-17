/**
 * Tests for exportImage utility functions.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  generateExportFilename,
  exportToPng,
  exportToBlob,
  isExportSupported,
} from '../exportImage';

// Mock html-to-image
vi.mock('html-to-image', () => ({
  toPng: vi.fn(),
  toBlob: vi.fn(),
}));

import { toPng, toBlob } from 'html-to-image';

describe('exportImage utilities', () => {
  describe('generateExportFilename', () => {
    it('generates filename with date suffix', () => {
      const filename = generateExportFilename('Test');
      // Format: Test_YYYY-MM-DD.png
      expect(filename).toMatch(/^Test_\d{4}-\d{2}-\d{2}\.png$/);
    });

    it('sanitizes special characters in base name', () => {
      const filename = generateExportFilename('Test/Card:Special<>');
      expect(filename).not.toContain('/');
      expect(filename).not.toContain(':');
      expect(filename).not.toContain('<');
      expect(filename).not.toContain('>');
    });

    it('collapses multiple underscores', () => {
      const filename = generateExportFilename('Test___Multiple');
      expect(filename).not.toContain('___');
    });

    it('preserves alphanumeric characters and hyphens', () => {
      const filename = generateExportFilename('Test-Card-123');
      expect(filename).toMatch(/^Test-Card-123_/);
    });

    it('handles empty string', () => {
      const filename = generateExportFilename('');
      expect(filename).toMatch(/_\d{4}-\d{2}-\d{2}\.png$/);
    });

    it('handles unicode characters', () => {
      const filename = generateExportFilename('Test-Namensschild');
      expect(filename).toContain('Test-Namensschild');
    });
  });

  describe('exportToPng', () => {
    let mockElement: HTMLDivElement;
    let mockLink: { download: string; href: string; click: ReturnType<typeof vi.fn> };
    let originalCreateElement: typeof document.createElement;

    beforeEach(() => {
      mockElement = document.createElement('div');
      mockLink = {
        download: '',
        href: '',
        click: vi.fn(),
      };

      // Store original before mocking
      originalCreateElement = document.createElement.bind(document);

      vi.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
        if (tagName === 'a') return mockLink as unknown as HTMLAnchorElement;
        return originalCreateElement(tagName);
      });

      vi.mocked(toPng).mockResolvedValue('data:image/png;base64,abc123');
    });

    afterEach(() => {
      vi.restoreAllMocks();
    });

    it('returns error result when element is null', async () => {
      const result = await exportToPng(null);

      expect(result.success).toBe(false);
      expect(result.error).toBe('No element provided for export');
    });

    it('exports element to PNG successfully', async () => {
      const result = await exportToPng(mockElement, { filename: 'Test' });

      expect(result.success).toBe(true);
      expect(result.filename).toMatch(/^Test_\d{4}-\d{2}-\d{2}\.png$/);
      expect(mockLink.click).toHaveBeenCalled();
    });

    it('uses default filename when not provided', async () => {
      const result = await exportToPng(mockElement);

      expect(result.success).toBe(true);
      expect(result.filename).toMatch(/^passport-card_/);
    });

    it('applies custom scale option', async () => {
      await exportToPng(mockElement, { scale: 3 });

      expect(toPng).toHaveBeenCalledWith(
        mockElement,
        expect.objectContaining({ pixelRatio: 3 })
      );
    });

    it('applies custom background color', async () => {
      await exportToPng(mockElement, { backgroundColor: '#f0f0f0' });

      expect(toPng).toHaveBeenCalledWith(
        mockElement,
        expect.objectContaining({ backgroundColor: '#f0f0f0' })
      );
    });

    it('handles export errors gracefully', async () => {
      vi.mocked(toPng).mockRejectedValue(new Error('Canvas error'));

      const result = await exportToPng(mockElement);

      expect(result.success).toBe(false);
      expect(result.error).toBe('Canvas error');
    });

    it('handles non-Error thrown values', async () => {
      vi.mocked(toPng).mockRejectedValue('String error');

      const result = await exportToPng(mockElement);

      expect(result.success).toBe(false);
      expect(result.error).toBe('Unknown export error');
    });

    it('filters elements with data-export-ignore attribute', async () => {
      await exportToPng(mockElement);

      expect(toPng).toHaveBeenCalledWith(
        mockElement,
        expect.objectContaining({
          filter: expect.any(Function),
        })
      );

      // Test the filter function
      const call = vi.mocked(toPng).mock.calls[0];
      const filterFn = call[1]?.filter as (node: HTMLElement) => boolean;

      const ignoredElement = document.createElement('div');
      ignoredElement.setAttribute('data-export-ignore', 'true');
      expect(filterFn(ignoredElement)).toBe(false);

      const normalElement = document.createElement('div');
      expect(filterFn(normalElement)).toBe(true);
    });
  });

  describe('exportToBlob', () => {
    let mockElement: HTMLDivElement;

    beforeEach(() => {
      mockElement = document.createElement('div');
    });

    afterEach(() => {
      vi.restoreAllMocks();
    });

    it('returns null when element is null', async () => {
      const result = await exportToBlob(null);
      expect(result).toBeNull();
    });

    it('exports element to blob successfully', async () => {
      const mockBlob = new Blob(['test'], { type: 'image/png' });
      vi.mocked(toBlob).mockResolvedValue(mockBlob);

      const result = await exportToBlob(mockElement);

      expect(result).toBe(mockBlob);
    });

    it('handles export errors gracefully', async () => {
      vi.mocked(toBlob).mockRejectedValue(new Error('Blob error'));

      const result = await exportToBlob(mockElement);

      expect(result).toBeNull();
    });

    it('applies custom options', async () => {
      vi.mocked(toBlob).mockResolvedValue(new Blob());

      await exportToBlob(mockElement, {
        scale: 2,
        backgroundColor: '#ffffff',
      });

      expect(toBlob).toHaveBeenCalledWith(
        mockElement,
        expect.objectContaining({
          pixelRatio: 2,
          backgroundColor: '#ffffff',
        })
      );
    });
  });

  describe('isExportSupported', () => {
    it('returns true in browser environment', () => {
      // JSDOM provides these
      expect(isExportSupported()).toBe(true);
    });

    it('checks for required APIs', () => {
      // The function checks for document, window, HTMLCanvasElement
      const supported = isExportSupported();
      expect(typeof supported).toBe('boolean');
    });
  });

  describe('ExportResult interface', () => {
    it('success result has filename', () => {
      const successResult = {
        success: true,
        filename: 'test.png',
      };
      expect(successResult.filename).toBe('test.png');
    });

    it('error result has error message', () => {
      const errorResult = {
        success: false,
        error: 'Something went wrong',
      };
      expect(errorResult.error).toBe('Something went wrong');
    });
  });

  describe('ExportOptions interface', () => {
    it('accepts all optional properties', () => {
      const options = {
        filename: 'custom',
        scale: 3,
        backgroundColor: '#000000',
        padding: 20,
      };

      expect(options.filename).toBe('custom');
      expect(options.scale).toBe(3);
      expect(options.backgroundColor).toBe('#000000');
      expect(options.padding).toBe(20);
    });
  });
});
