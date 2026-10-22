"""
OCR module for scanned/image-based PDFs using PyMuPDF (fitz) and RapidOCR (ONNX).
Maintains lazy initialization and handles mixed native/scanned PDF documents page-by-page.
"""
from __future__ import annotations
import functools
import gc
import logging
import os
import re
import traceback
from typing import Tuple

import fitz  # PyMuPDF
import numpy as np

from .pdf_utils import _pdf_text
from .security import log_event, load_settings  # FIX 3: needed for audit trail on OCR confidence fallback

logger = logging.getLogger(__name__)

_OCR_ENGINE = None


def get_ocr_engine():
    """Lazy-load singleton instance of RapidOCR."""
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _OCR_ENGINE = RapidOCR()
            logger.info("RapidOCR engine initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize RapidOCR engine: {e}")
            raise RuntimeError(
                f"Failed to load OCR engine. Ensure ONNX runtime dependencies are installed. Error: {e}"
            ) from e
    return _OCR_ENGINE


def _strip_page_markers(text: str) -> str:
    """Strip page section markers, control chars, and non-alphanumeric noise to evaluate true content length."""
    if not text:
        return ""
    clean = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    clean = re.sub(r'---\s*PAGE\s*\d+\s*---', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'===\s*.*?\s*===', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'[^a-zA-Z0-9]', '', clean)
    return clean


def is_scanned(pdf_path: str, min_chars_per_page: int = 50) -> bool:
    """
    Detect whether a PDF is overall scanned/image-only by analyzing cumulative native alphanumeric text.
    Sums ALL pages completely without early exiting.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    try:
        doc = fitz.open(pdf_path)
        if doc.is_encrypted:
            doc.close()  # FIX 6: prevent file handle leak on encrypted PDFs
            return False

        page_count = len(doc)
        if page_count == 0:
            doc.close()
            return True

        total_chars = 0
        for page in doc:
            text = page.get_text("text") or ""
            total_chars += len(_strip_page_markers(text))

        doc.close()
        return total_chars < (min_chars_per_page * page_count)
    except Exception as e:
        logger.warning(f"Error inspecting PDF structure for {pdf_path}: {e}")
        return True


def _page_key(pdf_path: str):
    st = os.stat(pdf_path)
    return pdf_path, st.st_mtime_ns, st.st_size


@functools.lru_cache(maxsize=64)
def _ocr_boxes(pdf_path: str, mtime_ns: int, size: int, page_idx: int, dpi: int):
    """OCR one page once. Returns ((x0, top, x1, bottom, text, conf), ...) in PDF points.
    Cached on (path, mtime, size) so vendor detection, extraction and the builder all
    reuse the same pass instead of re-running OCR on the same scan."""
    zoom = dpi / 72.0
    with fitz.open(pdf_path) as doc:
        pix = doc[page_idx].get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    img_rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    # RapidOCR works with RGB numpy arrays; the ONNX model handles its own normalisation.
    result, _ = get_ocr_engine()(img_rgb)
    del img_rgb, pix
    gc.collect()
    boxes = []
    for box, text, conf in result or []:
        xs, ys = [pt[0] for pt in box], [pt[1] for pt in box]
        if text.strip():
            boxes.append((min(xs) / zoom, min(ys) / zoom, max(xs) / zoom, max(ys) / zoom,
                          text.strip(), float(conf)))
    return tuple(boxes)


def _rows(boxes):
    """Group boxes into visual rows (vertical centres within half a box height), left to right."""
    rows = []
    for b in sorted(boxes, key=lambda b: (b[1] + b[3]) / 2):
        cy, h = (b[1] + b[3]) / 2, b[3] - b[1]
        if rows and abs(cy - rows[-1][0]) <= max(h, rows[-1][1]) / 2:
            rows[-1][2].append(b)
        else:
            rows.append([cy, h, [b]])
    return [sorted(r[2], key=lambda b: b[0]) for r in rows]


def _ocr_lines(boxes, min_confidence: float, p_idx: int = 1):
    """Rebuild text lines from OCR boxes so table rows stay on one line
    ("Consulting hours   20   75.00   1,500.00") instead of one cell per line.
    Low-confidence cells are marked [?text?] (0.4 <= conf < min) or [??text??] (< 0.4).
    Returns (lines, confidences of the kept boxes)."""
    kept = [b for b in boxes if b[5] >= 0.4]
    if not kept and boxes:
        # Confidence filter removed everything — log the range so the threshold can be tuned
        confs = [b[5] for b in boxes]
        logger.warning(
            f"[OCR DIAG] Page {p_idx}: all {len(boxes)} boxes below 0.4. "
            f"Actual range: min={min(confs):.3f} max={max(confs):.3f}. "
            "Consider lowering ocr_min_confidence in security.yaml.")
        # FIX 3: audit trail + warning so the fallback is never silent
        log_event("ocr_low_confidence",
                  f"page {p_idx}: all boxes below threshold {min_confidence}, "
                  "using emergency fallback (conf > 0.1)")
        # Emergency fallback: accept anything with conf > 0.1 to avoid empty output
        kept = [b for b in boxes if b[5] > 0.1]

    def mark(text, conf):
        if conf >= min_confidence:
            return text
        return f"[?{text}?]" if conf >= 0.4 else f"[??{text}??]"

    lines = ["   ".join(mark(b[4], b[5]) for b in row) for row in _rows(kept)]
    return lines, [b[5] for b in kept]


def ocr_page_words(pdf_path: str, page_idx: int, dpi: int = None, min_confidence: float = 0.4):
    """pdfplumber-style words (x0, x1, top, bottom, text) for a scanned page, so the
    coordinate templates and the template builder also work on scans and photos.
    A box holding several words is split on spaces, x positions spread by character."""
    dpi = dpi or int(load_settings().get("ocr_dpi", 300))
    words = []
    for x0, top, x1, bottom, text, conf in _ocr_boxes(*_page_key(pdf_path), page_idx, dpi):
        if conf < min_confidence:
            continue
        per_char = (x1 - x0) / max(len(text), 1)
        # OCR often glues "Bill No.:GBX-77" together; split after such a colon so the
        # template anchor ("Bill No") and its value become separate words again
        for m in re.finditer(r"[^\s:]+:(?=\S)|\S+", text):
            words.append({"text": m.group(), "x0": x0 + m.start() * per_char,
                          "x1": x0 + m.end() * per_char, "top": top, "bottom": bottom})
    return words


def is_scan_page(page, words=None) -> bool:
    """True when a pdfplumber page has too little real text to be digital (scan/photo)."""
    sec = load_settings()
    native = "".join(w["text"] for w in (page.extract_words() if words is None else words))
    return bool(sec.get("ocr_enabled", True)) and len(_strip_page_markers(native)) < int(sec.get("ocr_min_chars", 50))


def ocr_page_lines(pdf_path: str, page_idx: int, dpi: int = None) -> list[str]:
    """Text lines of a scanned page (OCR rows, no confidence markers)."""
    dpi = dpi or int(load_settings().get("ocr_dpi", 300))
    return _ocr_lines(_ocr_boxes(*_page_key(pdf_path), page_idx, dpi), min_confidence=0.0)[0]


def page_words(pdf_path: str, page, page_idx: int):
    """Words of a pdfplumber page; falls back to OCR when the page is a scan/photo
    (fewer than ocr_min_chars real characters). Returns (words, ocr_used)."""
    words = page.extract_words()
    if not is_scan_page(page, words):
        return words, False
    try:
        return ocr_page_words(pdf_path, page_idx), True
    except Exception as e:
        logger.error(f"OCR word extraction failed on {pdf_path} page {page_idx + 1}: {e}")
        return words, False


def page_images(pdf_path: str, max_pages: int = 3, long_side: int = 1600) -> list[bytes]:
    """JPEG renders of the first pages, sized for vision models (~1600px long side)."""
    out = []
    with fitz.open(pdf_path) as doc:
        for page in list(doc)[:max_pages]:
            zoom = long_side / max(page.rect.width, page.rect.height)
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            out.append(pix.tobytes("jpeg", jpg_quality=85))
    return out


def ocr_pdf(
    pdf_path: str,
    dpi: int = 300,
    min_confidence: float = 0.5,
    min_chars_per_page: int = 50,
    force_ocr: bool = False
) -> Tuple[str, bool, float]:
    """
    Process PDF page-by-page. Pages with sufficient native text use native text,
    while pages below min_chars_per_page (or when force_ocr is True) are OCR'd.

    Returns:
        tuple: (full_extracted_text, ocr_used: bool, ocr_confidence_avg: float)
    """
    key = _page_key(pdf_path)
    page_texts, confs = [], []
    ocr_used = False
    with fitz.open(pdf_path) as doc:
        native_pages = [page.get_text("text") or "" for page in doc]

    for p_idx, native_txt in enumerate(native_pages, start=1):
        if not force_ocr and len(_strip_page_markers(native_txt)) >= min_chars_per_page:
            page_texts.append("\n".join([f"--- PAGE {p_idx} ---", "=== NATIVE PAGE TEXT ===", native_txt]))
            continue
        ocr_used = True
        # FIX 1: never log raw OCR text (PII risk)
        lines, page_confs = _ocr_lines(_ocr_boxes(*key, p_idx - 1, dpi), min_confidence, p_idx)
        confs.extend(page_confs)
        page_texts.append("\n".join([f"--- PAGE {p_idx} ---", "=== OCR TEXT ==="] + lines))

    avg_conf = (sum(confs) / len(confs)) if confs else (1.0 if not ocr_used else 0.0)
    return "\n\n".join(page_texts), ocr_used, round(avg_conf, 4)


def extract_text_with_ocr_fallback(
    pdf_path: str,
    dpi: int = None,
    min_chars: int = 50,
    min_confidence: float = 0.5,
    force_ocr: bool = False,
    pdf_doc=None
) -> Tuple[str, bool, float]:
    """
    Primary Entry Point for PDF Text Extraction with Per-Page OCR Fallback.
    Automatically detects scanned documents and invokes RapidOCR.
    """
    from .security import load_settings
    sec = load_settings()
    dpi = dpi or int(sec.get("ocr_dpi", 300))

    if not sec.get("ocr_enabled", True):
        native_text = _pdf_text(pdf_path, pdf_doc=pdf_doc)
        return native_text, False, 1.0

    scanned = force_ocr or is_scanned(pdf_path, min_chars_per_page=min_chars)

    try:
        text, ocr_used, avg_conf = ocr_pdf(
            pdf_path, dpi=dpi, min_confidence=min_confidence,
            min_chars_per_page=min_chars, force_ocr=scanned
        )
        # Strip structural markers before checking whether we actually got content.
        # Without this, marker-only output ("--- PAGE 1 ---\n=== OCR TEXT ===")
        # looks non-empty but produces nothing useful for the LLM.
        _clean = re.sub(r'---\s*PAGE\s*\d+\s*---', '', text, flags=re.IGNORECASE)
        _clean = re.sub(r'===\s*\S.*?\s*===', '', _clean, flags=re.IGNORECASE)
        _clean = _clean.strip()
        if _clean:
            return text, ocr_used, avg_conf
        logger.warning(f"[OCR] ocr_pdf returned no usable text for {pdf_path}; falling back to pdfplumber.")
    except Exception as e:
        logger.error(
            f"OCR execution failed on {pdf_path}: {type(e).__name__}: {e}\n"
            f"{traceback.format_exc()}"
        )

    native_text = _pdf_text(pdf_path, pdf_doc=pdf_doc)
    return native_text, False, 1.0
