/**
 * PdfViewer - PDF viewer with highlight overlay for evidence.
 *
 * Uses pdf.js for rendering and custom overlay for highlighting evidence regions.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import type { EvidenceRef } from '../../services/magicImportApi';
import './MagicImport.css';

// PDF.js types
interface PDFDocumentProxy {
  numPages: number;
  getPage(pageNumber: number): Promise<PDFPageProxy>;
}

interface PDFPageProxy {
  getViewport(params: { scale: number }): PDFPageViewport;
  render(params: {
    canvasContext: CanvasRenderingContext2D;
    viewport: PDFPageViewport;
  }): { promise: Promise<void> };
}

interface PDFPageViewport {
  width: number;
  height: number;
}

interface PDFjsLib {
  getDocument(src: string | { url: string }): { promise: Promise<PDFDocumentProxy> };
  GlobalWorkerOptions: { workerSrc: string };
}

interface PdfViewerProps {
  url: string | null;
  evidence: EvidenceRef | null;
  onPageChange?: (page: number) => void;
}

export default function PdfViewer({ url, evidence, onPageChange }: PdfViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [pdfDoc, setPdfDoc] = useState<PDFDocumentProxy | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [scale, setScale] = useState(1.0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pageViewport, setPageViewport] = useState<PDFPageViewport | null>(null);

  // Load PDF.js dynamically
  const loadPdfJs = useCallback(async () => {
    if (typeof window === 'undefined') return null;

    // Check if already loaded
    const windowWithPdfjs = window as Window & { pdfjsLib?: PDFjsLib };
    if (windowWithPdfjs.pdfjsLib) {
      return windowWithPdfjs.pdfjsLib;
    }

    // Load from CDN
    return new Promise<PDFjsLib>((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.0.379/pdf.min.mjs';
      script.type = 'module';
      script.onload = () => {
        // pdf.js sets pdfjsLib on window
        const lib = (window as Window & { pdfjsLib?: PDFjsLib }).pdfjsLib;
        if (lib) {
          lib.GlobalWorkerOptions.workerSrc =
            'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.0.379/pdf.worker.min.mjs';
          resolve(lib);
        } else {
          reject(new Error('PDF.js not loaded'));
        }
      };
      script.onerror = () => reject(new Error('Failed to load PDF.js'));
      document.head.appendChild(script);
    });
  }, []);

  // Load PDF document
  useEffect(() => {
    if (!url) {
      setPdfDoc(null);
      return;
    }

    let cancelled = false;

    const loadPdf = async () => {
      setLoading(true);
      setError(null);

      try {
        const pdfjsLib = await loadPdfJs();
        if (!pdfjsLib || cancelled) return;

        const loadingTask = pdfjsLib.getDocument(url);
        const doc = await loadingTask.promise;

        if (cancelled) return;

        setPdfDoc(doc);
        setTotalPages(doc.numPages);
        setCurrentPage(1);
      } catch (err) {
        if (!cancelled) {
          console.error('Failed to load PDF:', err);
          setError('Failed to load PDF');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadPdf();

    return () => {
      cancelled = true;
    };
  }, [url, loadPdfJs]);

  // Render current page
  useEffect(() => {
    if (!pdfDoc || !canvasRef.current) return;

    let cancelled = false;

    const renderPage = async () => {
      try {
        const page = await pdfDoc.getPage(currentPage);
        if (cancelled) return;

        const viewport = page.getViewport({ scale });
        setPageViewport(viewport);

        const canvas = canvasRef.current!;
        const context = canvas.getContext('2d')!;

        canvas.width = viewport.width;
        canvas.height = viewport.height;

        await page.render({
          canvasContext: context,
          viewport,
        }).promise;
      } catch (err) {
        console.error('Failed to render page:', err);
      }
    };

    renderPage();

    return () => {
      cancelled = true;
    };
  }, [pdfDoc, currentPage, scale]);

  // Navigate to evidence page when evidence changes
  useEffect(() => {
    if (evidence && evidence.page + 1 !== currentPage) {
      setCurrentPage(evidence.page + 1);
      onPageChange?.(evidence.page + 1);
    }
  }, [evidence, currentPage, onPageChange]);

  // Page navigation
  const goToPage = useCallback(
    (page: number) => {
      if (page >= 1 && page <= totalPages) {
        setCurrentPage(page);
        onPageChange?.(page);
      }
    },
    [totalPages, onPageChange]
  );

  // Zoom controls
  const zoomIn = () => setScale((s) => Math.min(s + 0.25, 3.0));
  const zoomOut = () => setScale((s) => Math.max(s - 0.25, 0.5));
  const resetZoom = () => setScale(1.0);

  // Render highlights
  const renderHighlights = () => {
    if (!evidence || !pageViewport || evidence.page + 1 !== currentPage) {
      return null;
    }

    return evidence.boxes.map((box, idx) => (
      <div
        key={idx}
        className="pdf-viewer__highlight"
        style={{
          left: `${box.x0 * 100}%`,
          top: `${box.y0 * 100}%`,
          width: `${(box.x1 - box.x0) * 100}%`,
          height: `${(box.y1 - box.y0) * 100}%`,
        }}
      />
    ));
  };

  if (!url) {
    return (
      <div className="pdf-viewer pdf-viewer--empty">
        <p>Upload a PDF to preview</p>
      </div>
    );
  }

  return (
    <div className="pdf-viewer" ref={containerRef}>
      {/* Toolbar */}
      <div className="pdf-viewer__toolbar">
        <div className="pdf-viewer__nav">
          <button
            className="pdf-viewer__btn"
            onClick={() => goToPage(currentPage - 1)}
            disabled={currentPage <= 1}
          >
            &lt;
          </button>
          <span className="pdf-viewer__page-info">
            Page {currentPage} of {totalPages}
          </span>
          <button
            className="pdf-viewer__btn"
            onClick={() => goToPage(currentPage + 1)}
            disabled={currentPage >= totalPages}
          >
            &gt;
          </button>
        </div>

        <div className="pdf-viewer__zoom">
          <button className="pdf-viewer__btn" onClick={zoomOut}>
            -
          </button>
          <span className="pdf-viewer__zoom-level">{Math.round(scale * 100)}%</span>
          <button className="pdf-viewer__btn" onClick={zoomIn}>
            +
          </button>
          <button className="pdf-viewer__btn" onClick={resetZoom}>
            Reset
          </button>
        </div>
      </div>

      {/* Canvas container */}
      <div className="pdf-viewer__container">
        {loading && (
          <div className="pdf-viewer__loading">
            <span>Loading PDF...</span>
          </div>
        )}

        {error && (
          <div className="pdf-viewer__error">
            <span>{error}</span>
          </div>
        )}

        <div className="pdf-viewer__page" style={{ position: 'relative' }}>
          <canvas ref={canvasRef} className="pdf-viewer__canvas" />

          {/* Highlight overlay */}
          {pageViewport && (
            <div
              className="pdf-viewer__overlay"
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: pageViewport.width,
                height: pageViewport.height,
                pointerEvents: 'none',
              }}
            >
              {renderHighlights()}
            </div>
          )}
        </div>
      </div>

      {/* Evidence quote */}
      {evidence && (
        <div className="pdf-viewer__quote">
          <strong>Evidence:</strong> &quot;{evidence.quote}&quot;
          <span className="pdf-viewer__quote-meta">
            (Page {evidence.page + 1}, {evidence.method}, {Math.round(evidence.locator_score * 100)}
            % match)
          </span>
        </div>
      )}
    </div>
  );
}
