/**
 * Export utilities for rendering passport cards as PNG images.
 *
 * Uses html-to-image library for DOM-to-canvas conversion with
 * proper handling of CSS variables, gradients, and fonts.
 */
import { toPng, toBlob } from 'html-to-image';

/** Export result containing either success data or error */
export interface ExportResult {
  success: boolean;
  filename?: string;
  error?: string;
}

/** Options for customizing export behavior */
export interface ExportOptions {
  /** Base filename (without extension). Defaults to 'passport-card' */
  filename?: string;
  /** Scale factor for higher resolution. Defaults to 2 for retina */
  scale?: number;
  /** Background color. Defaults to white */
  backgroundColor?: string;
  /** Additional padding around the card in pixels */
  padding?: number;
}

const DEFAULT_OPTIONS: Required<ExportOptions> = {
  filename: 'passport-card',
  scale: 2,
  backgroundColor: '#ffffff',
  padding: 16,
};

/**
 * Generates a timestamped filename for the export.
 *
 * @param baseName - Base name for the file (e.g., 'Nameplate')
 * @returns Filename with date stamp (e.g., 'Nameplate_2024-01-17.png')
 */
export function generateExportFilename(baseName: string): string {
  const date = new Date().toISOString().split('T')[0];
  // Sanitize the base name to be filesystem-safe
  const sanitized = baseName.replace(/[^a-zA-Z0-9-_]/g, '_').replace(/_+/g, '_');
  return `${sanitized}_${date}.png`;
}

/**
 * Exports a DOM element as a PNG image and triggers download.
 *
 * @param element - The DOM element to export (typically a passport card)
 * @param options - Export customization options
 * @returns Promise resolving to export result
 *
 * @example
 * ```tsx
 * const cardRef = useRef<HTMLDivElement>(null);
 * const result = await exportToPng(cardRef.current, { filename: 'Nameplate' });
 * if (!result.success) {
 *   console.error(result.error);
 * }
 * ```
 */
export async function exportToPng(
  element: HTMLElement | null,
  options: ExportOptions = {}
): Promise<ExportResult> {
  if (!element) {
    return { success: false, error: 'No element provided for export' };
  }

  const mergedOptions = { ...DEFAULT_OPTIONS, ...options };
  const filename = generateExportFilename(mergedOptions.filename);

  try {
    // Configure html-to-image options
    const exportConfig = {
      pixelRatio: mergedOptions.scale,
      backgroundColor: mergedOptions.backgroundColor,
      // Add padding by expanding the capture area
      style: {
        margin: `${mergedOptions.padding}px`,
      },
      // Filter out elements that shouldn't be in the export
      filter: (node: HTMLElement): boolean => {
        // Skip elements with data-export-ignore attribute
        if (node.getAttribute?.('data-export-ignore') === 'true') {
          return false;
        }
        return true;
      },
      // Ensure fonts are properly embedded
      fontEmbedCSS: undefined, // Let library handle font embedding
      // Skip cross-origin checks for local fonts
      skipFonts: false,
    };

    // Generate PNG data URL
    const dataUrl = await toPng(element, exportConfig);

    // Create download link
    const link = document.createElement('a');
    link.download = filename;
    link.href = dataUrl;
    link.click();

    return { success: true, filename };
  } catch (err) {
    const errorMessage = err instanceof Error ? err.message : 'Unknown export error';
    console.error('[PassportMode] Export failed:', errorMessage);
    return { success: false, error: errorMessage };
  }
}

/**
 * Exports a DOM element as a Blob for programmatic use.
 * Useful for clipboard operations or server uploads.
 *
 * @param element - The DOM element to export
 * @param options - Export customization options
 * @returns Promise resolving to Blob or null on error
 */
export async function exportToBlob(
  element: HTMLElement | null,
  options: ExportOptions = {}
): Promise<Blob | null> {
  if (!element) {
    return null;
  }

  const mergedOptions = { ...DEFAULT_OPTIONS, ...options };

  try {
    const blob = await toBlob(element, {
      pixelRatio: mergedOptions.scale,
      backgroundColor: mergedOptions.backgroundColor,
      filter: (node: HTMLElement): boolean => {
        return node.getAttribute?.('data-export-ignore') !== 'true';
      },
    });

    return blob;
  } catch (err) {
    console.error('[PassportMode] Blob export failed:', err);
    return null;
  }
}

/**
 * Checks if the browser supports the required export APIs.
 *
 * @returns true if export is supported
 */
export function isExportSupported(): boolean {
  // Check for required APIs
  return (
    typeof document !== 'undefined' &&
    typeof window !== 'undefined' &&
    typeof HTMLCanvasElement !== 'undefined' &&
    typeof document.createElement === 'function'
  );
}
