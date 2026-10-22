"""Smoke test for the PDF preview renderer used by the Document Preview panel."""
from pathlib import Path

from extractor.ui import pdf_page_png

SAMPLE = Path(__file__).resolve().parent.parent / "sample_invoices" / "acme_001.pdf"


def test_pdf_page_png_renders_first_page():
    png, n_pages = pdf_page_png(SAMPLE.read_bytes())
    assert n_pages == 1
    assert png.startswith(b"\x89PNG")


def test_pdf_page_png_clamps_out_of_range_page():
    png, _ = pdf_page_png(SAMPLE.read_bytes(), page=5)
    assert png.startswith(b"\x89PNG")
