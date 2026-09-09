"""
Centralized exceptions and diagnostic utilities for invoice extraction.
Provides descriptive, actionable error reporting and recovery suggestions.
"""
from __future__ import annotations

import logging
import os
import re
import traceback
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# =====================================================================
# Structured Extraction Exceptions
# =====================================================================

class ExtractionError(Exception):
    """Base exception for all invoice extraction errors with actionable suggestions."""

    def __init__(
        self,
        message: str,
        suggestion: str = "",
        code: str = "EXTRACTION_ERROR",
        filename: str = "",
        details: str = "",
        title: str = "Invoice Extraction Failed",
    ):
        super().__init__(message)
        self.message = message
        self.suggestion = suggestion
        self.code = code
        self.filename = filename
        self.details = details
        self.title = title

    def to_dict(self) -> Dict[str, str]:
        return {
            "title": self.title,
            "message": self.message,
            "suggestion": self.suggestion,
            "code": self.code,
            "filename": self.filename,
            "details": self.details,
        }

    def __str__(self) -> str:
        s = self.message
        if self.suggestion:
            s += f"  → Action required: {self.suggestion}"
        return s


class CorruptedPDFError(ExtractionError):
    def __init__(self, message: str, suggestion: str = "", filename: str = "", details: str = ""):
        super().__init__(
            message=message,
            suggestion=suggestion or (
                "The PDF structure is damaged or the download was interrupted. "
                "Try opening the document in a web browser or Adobe Acrobat and saving/printing it as a new PDF."
            ),
            code="CORRUPTED_PDF",
            filename=filename,
            details=details,
            title="Corrupted or Damaged PDF",
        )


class EncryptedPDFError(ExtractionError):
    def __init__(self, message: str, suggestion: str = "", filename: str = "", details: str = ""):
        super().__init__(
            message=message,
            suggestion=suggestion or (
                "The PDF is encrypted or password-protected. "
                "Please open it in your PDF viewer and save an unencrypted copy (File → Print/Export as PDF) before uploading."
            ),
            code="PASSWORD_PROTECTED",
            filename=filename,
            details=details,
            title="Password-Protected PDF",
        )


class EmptyFileError(ExtractionError):
    def __init__(self, message: str, suggestion: str = "", filename: str = "", details: str = ""):
        super().__init__(
            message=message,
            suggestion=suggestion or (
                "The uploaded file contains no data or 0 pages. "
                "Verify that the invoice was exported properly from your accounting or billing software."
            ),
            code="EMPTY_FILE",
            filename=filename,
            details=details,
            title="Empty File (0 Bytes or 0 Pages)",
        )


class NonPDFError(ExtractionError):
    def __init__(self, message: str, suggestion: str = "", filename: str = "", details: str = ""):
        super().__init__(
            message=message,
            suggestion=suggestion or (
                "The uploaded file is not a valid PDF document. "
                "Ensure the file is an authentic PDF and was not merely renamed with a .pdf extension."
            ),
            code="NON_PDF",
            filename=filename,
            details=details,
            title="Invalid File Format",
        )


class FileTooLargeError(ExtractionError):
    def __init__(self, message: str, suggestion: str = "", filename: str = "", details: str = ""):
        super().__init__(
            message=message,
            suggestion=suggestion or (
                "Compress the PDF using an online PDF optimizer, split into smaller page batches, "
                "or increase 'max_file_mb' under Security & Logs."
            ),
            code="FILE_TOO_LARGE",
            filename=filename,
            details=details,
            title="File Size Limit Exceeded",
        )


class NoExtractableTextError(ExtractionError):
    def __init__(self, message: str, suggestion: str = "", filename: str = "", details: str = ""):
        super().__init__(
            message=message,
            suggestion=suggestion or (
                "No selectable text was found in this document (it appears to be a scanned image or photo). "
                "Enable OCR in Security & Logs, or use 'Extract Any Invoice' in the sidebar to process scanned documents."
            ),
            code="NO_TEXT_FOUND",
            filename=filename,
            details=details,
            title="No Selectable Text Found",
        )


class TemplateMismatchError(ExtractionError):
    def __init__(self, message: str, suggestion: str = "", filename: str = "", details: str = ""):
        super().__init__(
            message=message,
            suggestion=suggestion or (
                "The layout of this invoice does not match the chosen template. "
                "Try using 'Auto-detect vendor', build an updated template under 'Add New Vendor', "
                "or use 'Extract Any Invoice' for instant AI extraction."
            ),
            code="TEMPLATE_MISMATCH",
            filename=filename,
            details=details,
            title="Template Mismatch",
        )


class AIExtractionError(ExtractionError):
    def __init__(self, message: str, suggestion: str = "", code: str = "AI_ERROR", filename: str = "", details: str = ""):
        super().__init__(
            message=message,
            suggestion=suggestion,
            code=code,
            filename=filename,
            details=details,
            title="AI Extraction Error",
        )


# =====================================================================
# PDF Diagnostics
# =====================================================================

def diagnose_pdf_bytes(data: bytes, filename: str = "", max_mb: int = 25) -> Dict[str, Any]:
    """
    Perform comprehensive validation on uploaded file bytes.
    Identifies empty files, oversized files, non-PDF formats, encryption, and structural corruption.
    
    Returns a diagnostic dict:
        {
            "ok": bool,
            "code": str,
            "title": str,
            "message": str,
            "suggestion": str,
            "details": str
        }
    """
    fn = filename or "Uploaded file"

    # 1. Empty data
    if not data or len(data) == 0:
        return {
            "ok": False,
            "code": "EMPTY_FILE",
            "title": "Empty File (0 Bytes)",
            "message": f"'{fn}' is completely empty (0 bytes received).",
            "suggestion": "Check the source file export or download, and ensure the document contains data before uploading.",
            "details": f"File size: 0 bytes. Filename: {fn}",
        }

    # 2. File size cap
    max_bytes = max_mb * 1024 * 1024
    if len(data) > max_bytes:
        uploaded_mb = len(data) / (1024 * 1024)
        return {
            "ok": False,
            "code": "FILE_TOO_LARGE",
            "title": "File Size Limit Exceeded",
            "message": f"'{fn}' is {uploaded_mb:.1f} MB, which exceeds the configured limit of {max_mb} MB.",
            "suggestion": (
                "Compress the document using a PDF optimizer, split the document into smaller parts, "
                "or increase the 'Max upload size' setting in Security & Logs."
            ),
            "details": f"Size: {len(data)} bytes ({uploaded_mb:.2f} MB). Limit: {max_bytes} bytes ({max_mb} MB).",
        }

    # 3. Magic signature check (detect common non-PDF formats)
    if not data[:5].startswith(b"%PDF"):
        # Check specific common formats
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            msg = f"'{fn}' is a PNG image file, not a PDF."
            sugg = "Convert the PNG image into a PDF document (e.g. using Print to PDF) before uploading."
        elif data[:2] == b"\xff\xd8":
            msg = f"'{fn}' is a JPEG image file, not a PDF."
            sugg = "Convert the JPEG image into a PDF document before uploading."
        elif data[:4] == b"PK\x03\x04":
            msg = f"'{fn}' appears to be a ZIP archive or Microsoft Office document (.docx / .xlsx), not a PDF."
            sugg = "Extract the PDF invoice from the archive, or use 'Save As PDF' from Word/Excel."
        elif data[:5].lower().startswith(b"<!doc") or data[:5].lower().startswith(b"<html"):
            msg = f"'{fn}' is an HTML web page file, not a PDF."
            sugg = "Open the web page in your browser and select 'Print' → 'Save as PDF' before uploading."
        elif b"%PDF" in data[:1024]:
            # Some non-standard generators put junk bytes before %PDF
            pass
        else:
            msg = f"'{fn}' is not a valid PDF (missing standard '%PDF' document signature)."
            sugg = "Ensure the file was genuinely exported as a PDF document and was not merely renamed with a .pdf extension."

        if not (b"%PDF" in data[:1024]):
            return {
                "ok": False,
                "code": "NON_PDF",
                "title": "Invalid File Format",
                "message": msg,
                "suggestion": sugg,
                "details": f"First 16 bytes: {data[:16]!r}",
            }

    # 4. Structural integrity check (using PyMuPDF / fitz if available, or pdfminer)
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError:
            fitz = None

    if fitz is not None:
        try:
            doc = fitz.open(stream=data, filetype="pdf")
            try:
                if doc.is_encrypted:
                    return {
                        "ok": False,
                        "code": "PASSWORD_PROTECTED",
                        "title": "Password-Protected PDF",
                        "message": f"'{fn}' is encrypted or protected by a password.",
                        "suggestion": (
                            "Please remove password protection from the document before uploading "
                            "(open in your PDF viewer and choose 'Print to PDF' or export an unencrypted copy)."
                        ),
                        "details": f"Doc encryption flag: {getattr(doc, 'is_encrypted', True)}",
                    }
                if len(doc) == 0:
                    return {
                        "ok": False,
                        "code": "EMPTY_PDF",
                        "title": "Document Contains 0 Pages",
                        "message": f"'{fn}' contains no pages (page count is 0).",
                        "suggestion": "Verify that the PDF export finished completely and re-upload the document.",
                        "details": "Page count: 0",
                    }
            finally:
                doc.close()
        except Exception as e:
            err_msg = str(e)
            return {
                "ok": False,
                "code": "CORRUPTED_PDF",
                "title": "Corrupted or Damaged PDF",
                "message": f"'{fn}' is corrupted or damaged and cannot be parsed ({err_msg}).",
                "suggestion": (
                    "The file structure appears incomplete or damaged. "
                    "Try re-downloading the invoice or re-saving it through Chrome or Adobe Acrobat ('Print to PDF')."
                ),
                "details": f"Parser error: {traceback.format_exc()}",
            }
    else:
        # Fallback to pdfplumber/pdfminer stream inspection
        try:
            import io
            import pdfplumber
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                if len(pdf.pages) == 0:
                    return {
                        "ok": False,
                        "code": "EMPTY_PDF",
                        "title": "Document Contains 0 Pages",
                        "message": f"'{fn}' contains no pages (page count is 0).",
                        "suggestion": "Verify that the PDF export finished completely and re-upload the document.",
                        "details": "Page count: 0",
                    }
        except Exception as e:
            err_msg = str(e)
            if "password" in err_msg.lower():
                return {
                    "ok": False,
                    "code": "PASSWORD_PROTECTED",
                    "title": "Password-Protected PDF",
                    "message": f"'{fn}' is encrypted or protected by a password.",
                    "suggestion": "Remove password protection from the document before uploading.",
                    "details": err_msg,
                }
            return {
                "ok": False,
                "code": "CORRUPTED_PDF",
                "title": "Corrupted or Damaged PDF",
                "message": f"'{fn}' is corrupted or damaged and cannot be parsed ({err_msg}).",
                "suggestion": "Try re-saving the PDF using 'Print to PDF' and upload again.",
                "details": traceback.format_exc(),
            }

    return {
        "ok": True,
        "code": "OK",
        "title": "Valid PDF",
        "message": "",
        "suggestion": "",
        "details": "",
    }


# =====================================================================
# Exception Diagnosis & Recovery Suggestions
# =====================================================================

def diagnose_exception(e: Exception, filename: str = "", context: str = "") -> Dict[str, str]:
    """
    Inspect an exception raised anywhere during extraction or processing,
    and convert it into a clear, actionable diagnostic dictionary:
        {
            "title": str,
            "message": str,
            "suggestion": str,
            "code": str,
            "filename": str,
            "details": str
        }
    """
    fn = filename or "Document"
    raw_msg = str(e).strip()
    low = raw_msg.lower()
    tb_str = traceback.format_exc()

    # 1. Custom structured ExtractionError
    if isinstance(e, ExtractionError):
        res = e.to_dict()
        if filename and not res["filename"]:
            res["filename"] = filename
        return res

    # 2. Corrupted / damaged PDF file
    if any(k in low for k in ("cannot open broken document", "broken document", "syntaxerror",
                              "syntax error", "pdfsyntaxerror", "eof marker not found",
                              "filedataerror", "formaterror", "damaged")):
        return {
            "title": "Corrupted or Damaged PDF",
            "message": f"'{fn}' could not be parsed because its internal PDF structure is corrupted or truncated.",
            "suggestion": "Open the invoice in a PDF reader or web browser and re-save it using 'Print to PDF' to regenerate clean document structures.",
            "code": "CORRUPTED_PDF",
            "filename": fn,
            "details": raw_msg or tb_str,
        }

    # 3. Password / Encryption
    if any(k in low for k in ("password", "encrypted", "filedecryptionerror", "pdfpasswordincorrect")):
        return {
            "title": "Password-Protected PDF",
            "message": f"'{fn}' is encrypted or requires a password to open.",
            "suggestion": "Remove password protection from the document before uploading (e.g. open in browser/reader and print as an unencrypted PDF).",
            "code": "PASSWORD_PROTECTED",
            "filename": fn,
            "details": raw_msg or tb_str,
        }

    # 4. No extractable text / scanned image
    if "no text could be extracted" in low or "no selectable text" in low:
        return {
            "title": "No Selectable Text (Scanned Image)",
            "message": f"'{fn}' contains no selectable digital text. It appears to be a scanned document, receipt photo, or image-only PDF.",
            "suggestion": "Ensure OCR is enabled in Security & Logs, or use 'Extract Any Invoice' in the sidebar to process scanned documents.",
            "code": "NO_TEXT_FOUND",
            "filename": fn,
            "details": raw_msg or tb_str,
        }

    # 5. Security guardrail / AI blocked
    if isinstance(e, PermissionError) or "cloud ai is disabled" in low or "ai_blocked" in low:
        return {
            "title": "AI Extraction Blocked by Security Policy",
            "message": raw_msg or "Cloud AI providers are disabled in your Security settings.",
            "suggestion": "Go to 'Security & Logs' in the sidebar to re-enable Cloud AI, or use a local model such as Ollama.",
            "code": "AI_BLOCKED",
            "filename": fn,
            "details": raw_msg or tb_str,
        }

    # 6. AI Authentication / API Key
    if any(k in low for k in ("api key", "authentication", "unauthorized", "401", "invalid api key", "incorrect api key")):
        return {
            "title": "AI Provider Authentication Failed",
            "message": "The API key was rejected by the selected AI provider.",
            "suggestion": "Open '① AI setup' on the page, verify your API key, ensure there are no trailing spaces, and save again.",
            "code": "AI_AUTH_FAILED",
            "filename": fn,
            "details": raw_msg or tb_str,
        }

    # 7. AI Model ID not found
    if any(k in low for k in ("model", "not found", "does not exist", "404", "model_not_found")):
        return {
            "title": "AI Model Not Found",
            "message": f"The model ID specified is not recognized or not available for your provider account: {raw_msg}",
            "suggestion": "Check the model name spelling in '① AI setup'. Examples: OpenAI: `gpt-4o`, Anthropic: `claude-3-5-sonnet-latest`, Gemini: `gemini-2.5-flash`.",
            "code": "AI_INVALID_MODEL",
            "filename": fn,
            "details": raw_msg or tb_str,
        }

    # 8. AI Rate Limit / Quota Exceeded
    if any(k in low for k in ("rate limit", "429", "quota", "insufficient_quota", "resource_exhausted")):
        return {
            "title": "AI Rate Limit or Quota Exceeded",
            "message": "The AI provider returned a rate limit or insufficient balance/quota error.",
            "suggestion": "Check your provider account billing/usage credits, wait a minute before retrying, or switch to a different provider.",
            "code": "AI_QUOTA_EXCEEDED",
            "filename": fn,
            "details": raw_msg or tb_str,
        }

    # 9. AI Connection / Timeout / Offline
    if any(k in low for k in ("connect", "connection", "timeout", "timed out", "econnrefused", "name resolution", "couldn't reach")):
        return {
            "title": "AI Connection Failed",
            "message": "Could not connect to the AI service endpoint.",
            "suggestion": "Check your internet connection. If using a local model server (Ollama/vLLM), make sure the local server is running and the Base URL is correct.",
            "code": "AI_CONNECTION_ERROR",
            "filename": fn,
            "details": raw_msg or tb_str,
        }

    # 10. AI JSON Output parsing failed
    if any(k in low for k in ("json", "valid json", "jsondecodeerror", "expecting value")):
        return {
            "title": "Invalid AI Response Format",
            "message": "The AI model returned text that could not be parsed into invoice data.",
            "suggestion": "Retry extraction, or select a larger/more capable model (such as `gpt-4o` or `claude-3-5-sonnet`) which reliably outputs valid JSON.",
            "code": "AI_INVALID_JSON",
            "filename": fn,
            "details": raw_msg or tb_str,
        }

    # 11. Template / Anchor extraction errors
    if isinstance(e, KeyError) or "template" in low or "anchor" in low:
        return {
            "title": "Template Extraction Error",
            "message": f"Could not match expected template fields for '{fn}': {raw_msg}",
            "suggestion": "Verify that this invoice belongs to the selected vendor, or create/adjust the template in 'Add New Vendor'.",
            "code": "TEMPLATE_ERROR",
            "filename": fn,
            "details": raw_msg or tb_str,
        }

    # 12. Generic fallback
    return {
        "title": "Extraction Failed",
        "message": f"An unexpected error occurred while processing '{fn}': {raw_msg or type(e).__name__}",
        "suggestion": "Verify the document format. If using template extraction, try 'Extract Any Invoice' in the sidebar as an alternative.",
        "code": "UNEXPECTED_ERROR",
        "filename": fn,
        "details": tb_str if tb_str != "NoneType: None\n" else raw_msg,
    }
