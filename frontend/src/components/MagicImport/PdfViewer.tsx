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
  getTextContent(): Promise<{ items: Array<{ str?: string }> }>;
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
  confidence?: number;
  onPageChange?: (page: number) => void;
  focusToken?: number;
}

export default function PdfViewer({
  url,
  evidence,
  confidence,
  onPageChange,
  focusToken,
}: PdfViewerProps) {
  const viewerRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const pendingFocusRef = useRef<{ page: number; box: EvidenceRef['boxes'][0] } | null>(
    null
  );
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [pageText, setPageText] = useState('');
  const [pdfDoc, setPdfDoc] = useState<PDFDocumentProxy | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [scale, setScale] = useState(1.0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pageViewport, setPageViewport] = useState<PDFPageViewport | null>(null);
  const [thumbnails, setThumbnails] = useState<Array<{ page: number; dataUrl: string }>>(
    []
  );

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

        try {
          const textContent = await page.getTextContent();
          if (!cancelled) {
            const text = textContent.items.map((item) => item.str || '').join(' ');
            setPageText(text);
          }
        } catch {
          if (!cancelled) {
            setPageText('');
          }
        }

        const pending = pendingFocusRef.current;
        if (pending && pending.page === currentPage && scrollRef.current) {
          const box = pending.box;
          const centerX =
            (box.x0 + (box.x1 - box.x0) / 2) * viewport.width;
          const centerY =
            (box.y0 + (box.y1 - box.y0) / 2) * viewport.height;
          scrollRef.current.scrollTo({
            left: Math.max(0, centerX - scrollRef.current.clientWidth / 2),
            top: Math.max(0, centerY - scrollRef.current.clientHeight / 2),
            behavior: 'smooth',
          });
          pendingFocusRef.current = null;
        }
      } catch (err) {
        console.error('Failed to render page:', err);
      }
    };

    renderPage();

    return () => {
      cancelled = true;
    };
  }, [pdfDoc, currentPage, scale]);

  // Generate thumbnails for quick navigation
  useEffect(() => {
    if (!pdfDoc) {
      setThumbnails([]);
      return;
    }

    let cancelled = false;

    const buildThumbnails = async () => {
      const thumbs: Array<{ page: number; dataUrl: string }> = [];
      const maxPages = Math.min(pdfDoc.numPages, 12);
      for (let pageNum = 1; pageNum <= maxPages; pageNum += 1) {
        try {
          const page = await pdfDoc.getPage(pageNum);
          if (cancelled) return;
          const viewport = page.getViewport({ scale: 0.2 });
          const canvas = document.createElement('canvas');
          const context = canvas.getContext('2d');
          if (!context) continue;
          canvas.width = viewport.width;
          canvas.height = viewport.height;
          await page.render({ canvasContext: context, viewport }).promise;
          const dataUrl = canvas.toDataURL('image/png');
          thumbs.push({ page: pageNum, dataUrl });
        } catch {
          // Skip thumbnail on failure
        }
      }
      if (!cancelled) setThumbnails(thumbs);
    };

    buildThumbnails();

    return () => {
      cancelled = true;
    };
  }, [pdfDoc]);

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

  const focusEvidence = useCallback(() => {
    if (!evidence || !pageViewport) return;
    if (!evidence.boxes || evidence.boxes.length === 0) return;

    const box = evidence.boxes[0];
    const targetPage = evidence.page + 1;

    const boxWidth = (box.x1 - box.x0) * pageViewport.width;
    const container = scrollRef.current;
    let nextScale = scale;

    if (container && boxWidth > 0) {
      const targetWidth = Math.min(container.clientWidth, container.clientHeight) * 0.45;
      const factor = targetWidth / boxWidth;
      if (factor > 1.05) {
        nextScale = Math.min(3.0, scale * factor);
      }
    }

    pendingFocusRef.current = { page: targetPage, box };
    if (targetPage !== currentPage) {
      setCurrentPage(targetPage);
    }
    if (nextScale !== scale) {
      setScale(nextScale);
    }
  }, [evidence, pageViewport, scale, currentPage]);

  // Trigger focus when requested
  useEffect(() => {
    if (focusToken === undefined) return;
    if (!evidence) return;
    focusEvidence();
  }, [focusToken, evidence, focusEvidence]);

  // Zoom controls
  const zoomIn = () => setScale((s) => Math.min(s + 0.25, 3.0));
  const zoomOut = () => setScale((s) => Math.max(s - 0.25, 0.5));
  const resetZoom = () => setScale(1.0);

  // Get highlight class based on confidence
  const getHighlightClass = () => {
    if (confidence === undefined) return 'pdf-viewer__highlight';
    if (confidence >= 0.9) return 'pdf-viewer__highlight pdf-viewer__highlight--high';
    if (confidence >= 0.8) return 'pdf-viewer__highlight pdf-viewer__highlight--medium';
    return 'pdf-viewer__highlight pdf-viewer__highlight--low';
  };

  // Render highlights
  const renderHighlights = () => {
    if (!evidence || !pageViewport || evidence.page + 1 !== currentPage) {
      return null;
    }

    const highlightClass = getHighlightClass();

    return evidence.boxes.map((box, idx) => (
      <div
        key={idx}
        className={highlightClass}
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
    <div className="pdf-viewer" ref={viewerRef}>
      {/* Toolbar */}
      <div className="pdf-viewer__toolbar">
        <div className="pdf-viewer__nav">
          <button
            type="button"
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
            type="button"
            className="pdf-viewer__btn"
            onClick={() => goToPage(currentPage + 1)}
            disabled={currentPage >= totalPages}
          >
            &gt;
          </button>
        </div>

        <div className="pdf-viewer__zoom">
          <button type="button" className="pdf-viewer__btn" onClick={zoomOut}>
            -
          </button>
          <span className="pdf-viewer__zoom-level">{Math.round(scale * 100)}%</span>
          <button type="button" className="pdf-viewer__btn" onClick={zoomIn}>
            +
          </button>
          <button type="button" className="pdf-viewer__btn" onClick={resetZoom}>
            Reset
          </button>
        </div>

        {evidence && (
          <button
            type="button"
            className="pdf-viewer__btn pdf-viewer__btn--focus"
            onClick={focusEvidence}
          >
            Focus evidence
          </button>
        )}
      </div>

      {/* Canvas container */}
      <div className="pdf-viewer__container" ref={scrollRef}>
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

        <div className="pdf-viewer__content">
          <div className="pdf-viewer__thumbs">
            {thumbnails.map((thumb) => (
              <button
                type="button"
                key={`thumb-${thumb.page}`}
                className={`pdf-viewer__thumb ${
                  thumb.page === currentPage ? 'active' : ''
                }`}
                onClick={() => goToPage(thumb.page)}
                title={`Page ${thumb.page}`}
              >
                <img src={thumb.dataUrl} alt={`Page ${thumb.page}`} />
                <span>{thumb.page}</span>
              </button>
            ))}
            {totalPages > thumbnails.length && (
              <div className="pdf-viewer__thumb-more">
                +{totalPages - thumbnails.length} pages
              </div>
            )}
          </div>

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

      {pageText && (
        <div className="pdf-viewer__page-text">
          <strong>Page text:</strong> {pageText.slice(0, 240)}
          {pageText.length > 240 ? '…' : ''}
        </div>
      )}
    </div>
  );
}
