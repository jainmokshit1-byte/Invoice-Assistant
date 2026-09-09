"""Tests for error handling, diagnostics, and recovery suggestions."""
import tempfile
import os
import pytest
from extractor.errors import (
    diagnose_pdf_bytes,
    diagnose_exception,
    ExtractionError,
    CorruptedPDFError,
    EncryptedPDFError,
    EmptyFileError,
    NonPDFError,
    FileTooLargeError,
    NoExtractableTextError,
    TemplateMismatchError,
    AIExtractionError,
)
from extractor.security import check_upload, check_upload_detailed
from extractor.engine import extract_invoice


def test_diagnose_empty_bytes():
    diag = diagnose_pdf_bytes(b"", "empty_invoice.pdf")
    assert not diag["ok"]
    assert diag["code"] == "EMPTY_FILE"
    assert "0 bytes" in diag["message"]
    assert len(diag["suggestion"]) > 0


def test_diagnose_oversized_file():
    # 2 MB limit for test
    oversized_data = b"%PDF" + b"0" * (3 * 1024 * 1024)
    diag = diagnose_pdf_bytes(oversized_data, "large_invoice.pdf", max_mb=2)
    assert not diag["ok"]
    assert diag["code"] == "FILE_TOO_LARGE"
    assert "exceeds" in diag["message"].lower()
    assert "compress" in diag["suggestion"].lower()


def test_diagnose_png_image():
    png_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    diag = diagnose_pdf_bytes(png_data, "scanned_receipt.png")
    assert not diag["ok"]
    assert diag["code"] == "NON_PDF"
    assert "PNG" in diag["message"]
    assert "convert" in diag["suggestion"].lower()


def test_diagnose_jpeg_image():
    jpg_data = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    diag = diagnose_pdf_bytes(jpg_data, "photo.jpg")
    assert not diag["ok"]
    assert diag["code"] == "NON_PDF"
    assert "JPEG" in diag["message"]
    assert "convert" in diag["suggestion"].lower()


def test_diagnose_zip_or_docx():
    docx_data = b"PK\x03\x04\x14\x00\x06\x00"
    diag = diagnose_pdf_bytes(docx_data, "invoice.docx")
    assert not diag["ok"]
    assert diag["code"] == "NON_PDF"
    assert "Office" in diag["message"] or "ZIP" in diag["message"]
    assert "PDF" in diag["suggestion"]


def test_diagnose_html_document():
    html_data = b"<!DOCTYPE html><html><body><h1>Invoice</h1></body></html>"
    diag = diagnose_pdf_bytes(html_data, "receipt.html")
    assert not diag["ok"]
    assert diag["code"] == "NON_PDF"
    assert "HTML" in diag["message"]
    assert "Print" in diag["suggestion"]


def test_diagnose_corrupted_pdf_structure():
    corrupted_data = b"%PDF-1.4\n\x00\xffBrokenHeaderNotValidPDFStructureTrailerMissing"
    diag = diagnose_pdf_bytes(corrupted_data, "damaged_invoice.pdf")
    assert not diag["ok"]
    assert diag["code"] == "CORRUPTED_PDF"
    assert "corrupted" in diag["message"].lower() or "damaged" in diag["message"].lower()
    assert "print to pdf" in diag["suggestion"].lower() or "re-downloading" in diag["suggestion"].lower()


def test_check_upload_backwards_compatibility():
    # check_upload returns (bool, str)
    ok, msg = check_upload(b"", "empty.pdf")
    assert ok is False
    assert "0 bytes" in msg
    assert "Action required:" in msg or "—" in msg

    # check_upload_detailed returns structured dict
    diag = check_upload_detailed(b"", "empty.pdf")
    assert diag["ok"] is False
    assert diag["code"] == "EMPTY_FILE"
    assert diag["suggestion"] != ""


def test_diagnose_exception_corrupted_pdf():
    e = RuntimeError("cannot open broken document (PDFSyntaxError: expected xref)")
    diag = diagnose_exception(e, "broken.pdf")
    assert diag["code"] == "CORRUPTED_PDF"
    assert "corrupted" in diag["title"].lower()
    assert "print to pdf" in diag["suggestion"].lower()


def test_diagnose_exception_password_protected():
    e = Exception("PDFPasswordIncorrect: File is password-protected")
    diag = diagnose_exception(e, "secret.pdf")
    assert diag["code"] == "PASSWORD_PROTECTED"
    assert "password" in diag["title"].lower()
    assert "remove password" in diag["suggestion"].lower()


def test_diagnose_exception_ai_auth():
    e = Exception("401 Unauthorized: Invalid API key provided")
    diag = diagnose_exception(e, "invoice.pdf")
    assert diag["code"] == "AI_AUTH_FAILED"
    assert "authentication" in diag["title"].lower()
    assert "api key" in diag["suggestion"].lower()


def test_diagnose_exception_ai_model():
    e = Exception("404 Not Found: The model `gpt-fake-model` does not exist")
    diag = diagnose_exception(e, "invoice.pdf")
    assert diag["code"] == "AI_INVALID_MODEL"
    assert "model" in diag["title"].lower()
    assert "model" in diag["suggestion"].lower()


def test_diagnose_exception_ai_rate_limit():
    e = Exception("429 Too Many Requests: Rate limit reached for requests per minute")
    diag = diagnose_exception(e, "invoice.pdf")
    assert diag["code"] == "AI_QUOTA_EXCEEDED"
    assert "quota" in diag["title"].lower() or "rate limit" in diag["title"].lower()
    assert "billing" in diag["suggestion"].lower() or "wait" in diag["suggestion"].lower()


def test_diagnose_exception_ai_connection():
    e = Exception("Connection error: Failed to establish a new connection to api.openai.com")
    diag = diagnose_exception(e, "invoice.pdf")
    assert diag["code"] == "AI_CONNECTION_ERROR"
    assert "connection" in diag["title"].lower()
    assert "internet" in diag["suggestion"].lower() or "server" in diag["suggestion"].lower()


def test_diagnose_exception_no_text():
    e = ValueError("No text could be extracted from PDF (native or OCR).")
    diag = diagnose_exception(e, "scan.pdf")
    assert diag["code"] == "NO_TEXT_FOUND"
    assert "scanned" in diag["message"].lower() or "text" in diag["message"].lower()
    assert "ocr" in diag["suggestion"].lower()


def test_extract_invoice_corrupted_file_raises():
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4\nJUNK_DATA_NOT_VALID_PDF")
        tmp_path = f.name
    try:
        with pytest.raises(CorruptedPDFError) as exc_info:
            extract_invoice(tmp_path, {"vendor": "Acme", "fields": {}})
        err = exc_info.value
        assert err.code == "CORRUPTED_PDF"
        assert len(err.suggestion) > 0
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_extract_invoice_empty_template_raises():
    with pytest.raises(TemplateMismatchError) as exc_info:
        extract_invoice("dummy.pdf", {})
    assert exc_info.value.code == "TEMPLATE_MISMATCH"
    assert "template" in exc_info.value.suggestion.lower()


def test_batch_processing_resilience():
    """Verify that a batch with mixed valid and corrupted/invalid files does not crash."""
    import pymupdf as fitz
    from extractor.security import check_upload_detailed
    from extractor.errors import diagnose_exception

    # Create a valid PDF in memory
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "ACME Corporation\nInvoice Number: INV-001\nDate: 2026-01-01\nTotal: 100.00")
    valid_bytes = doc.tobytes()
    doc.close()

    batch = [
        ("valid.pdf", valid_bytes),
        ("corrupted.pdf", b"%PDF-1.4\ncorrupted_not_valid_content_at_all"),
        ("empty.pdf", b""),
        ("image.png", b"\x89PNG\r\n\x1a\nfakeimage"),
    ]

    invoices, rejected, failed = [], [], []

    for name, data in batch:
        diag = check_upload_detailed(data, name)
        if not diag["ok"]:
            diag["filename"] = name
            rejected.append(diag)
            continue

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        try:
            tpl = {
                "vendor": "ACME Corporation",
                "identify": {"keyword": "ACME"},
                "fields": {
                    "invoice_number": {"anchor": "Invoice Number"},
                    "total": {"anchor": "Total", "type": "money"},
                }
            }
            inv = extract_invoice(tmp_path, tpl)
            invoices.append(inv)
        except Exception as e:
            failed.append(diagnose_exception(e, filename=name))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    # Valid invoice was extracted successfully
    assert len(invoices) == 1
    assert invoices[0].invoice_number == "INV-001"
    assert invoices[0].total == 100.00

    # Corrupted, empty, and png were rejected or caught with actionable suggestions
    assert len(rejected) == 3
    rejected_codes = {r["code"] for r in rejected}
    assert "EMPTY_FILE" in rejected_codes
    assert "NON_PDF" in rejected_codes
    assert "CORRUPTED_PDF" in rejected_codes
    for r in rejected:
        assert len(r["suggestion"]) > 0
