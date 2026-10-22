# Invoice Assistant

[![CI](https://github.com/jainmokshit1-byte/Invoice-Assistant/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jainmokshit1-byte/Invoice-Assistant/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.36+-FF4B4B.svg)
![License MIT](https://img.shields.io/badge/license-MIT-green.svg)

Privacy-first invoice extraction for accounts payable. Upload invoices as **PDFs or images** (digital, scanned, or phone photos), review the extracted data side by side with the original, and export to **Excel, Tally Prime XML, QuickBooks CSV, or JSON**.

---

## Features

- **Two extraction modes**
  - **Templates** — fast, deterministic, fully offline extraction for recurring vendors using coordinate-based YAML templates. Vendors are auto-detected.
  - **AI (any invoice)** — template-free extraction with Anthropic Claude, OpenAI, Google Gemini, Groq, Mistral, OpenRouter, or a local model (Ollama / vLLM / any OpenAI-compatible endpoint).
- **PDFs and images** — PNG, JPG, WEBP, TIFF, and BMP are converted to PDF on upload (EXIF rotation corrected). Scanned pages are read with offline **RapidOCR**; for vision-capable models, page images are also sent to the AI.
- **Verification** — arithmetic checks (line items, subtotal + tax = total), reconciliation against the totals printed on the document, business rules, and duplicate detection (file hash and vendor/number/date/total).
- **Review UI** — editable result tables, a document preview next to the extracted fields, and step-by-step progress during batch processing.
- **Template Studio** — build a vendor template from one sample by auto-build (offline), AI generation, point-and-click, or dropdowns.
- **Security** — cloud-AI lockout, PII redaction before AI calls, prompt-injection fencing, API keys never stored or logged, local audit log.

---

## Pages

| Page | Purpose |
| :--- | :--- |
| `app.py` — Batch Extraction | Template-based batch processing, review, and export |
| Extract Any Invoice | AI extraction for any layout; provider setup with **Test connection** |
| Add New Vendor | Create vendor templates |
| Manage | Templates, output files, duplicate history |
| Business Rules | Global and per-vendor compliance rules |
| Security & Logs | Privacy, upload limits, OCR settings, audit log |

---

## Quick Start

**Requirements:** Python **3.12** (RapidOCR's ONNX wheels are not available for newer versions).

```bash
git clone https://github.com/jainmokshit1-byte/Invoice-Assistant.git
cd Invoice-Assistant
python3.12 -m venv venv312
source venv312/bin/activate        # Windows: .\venv312\Scripts\Activate.ps1
pip install -r requirements.txt
python -m streamlit run app.py
```

Open http://localhost:8501. On Windows you can instead double-click **`Start Invoice Tool.bat`**.
On Debian/Ubuntu, install `libgl1 libglib2.0-0` first if OCR fails to load.

Try it with the files in `sample_invoices/`, or generate more with `python scripts/make_sample_invoices.py`.

**Command line (template mode):**

```bash
python run.py <vendor_id> <folder_of_pdfs> [output_folder]   # e.g. python run.py acme sample_invoices output
```

---

## AI Providers

Template mode, OCR, and validation work without any API key. For AI extraction, open **Extract Any Invoice → Provider & Model Configuration**, choose a provider, enter the key and model ID, and click **Test connection**. The settings are shared across pages for the session.

| Provider | Default model | Key environment variable |
| :--- | :--- | :--- |
| Anthropic (Claude) | `claude-sonnet-5` | `ANTHROPIC_API_KEY` |
| OpenAI | `gpt-4o` | `OPENAI_API_KEY` |
| Google Gemini | `gemini-2.5-flash` | `GEMINI_API_KEY` |
| Groq | `llama-3.3-70b-versatile` | `GROQ_API_KEY` |
| Mistral | `mistral-large-latest` | `MISTRAL_API_KEY` |
| OpenRouter | editable | `OPENROUTER_API_KEY` |
| Local (Ollama / vLLM) / Custom | editable | — |

Keys set as environment variables are pre-filled. Set `AI_TIMEOUT` (seconds, default 600) for slow local models.

---

## Configuration

**`security.yaml`** — also editable on the Security & Logs page:

```yaml
allow_cloud_ai: true        # false = only local AI endpoints are allowed
redact_before_ai: false     # strip emails, phones, account/card numbers before cloud AI calls
max_file_mb: 25
max_batch_files: 100
max_ai_chars: 60000         # cap on text sent to a model per invoice
ocr_enabled: true
ocr_dpi: 300
ocr_min_chars: 50           # pages with fewer real characters are OCR'd
ocr_min_confidence: 0.5
```

**`rules.yaml`** — business rules (also editable on the Business Rules page):

```yaml
global:
  require_any: [[invoice_number, po_number]]
  require_line_items: true
  date_not_future: true
  max_total: 100000.0
vendors:
  acme:
    require_any: [[po_number]]
```

**`templates/*.yaml`** — one file per vendor; created in Add New Vendor.

---

## Deployment

```bash
docker build -t invoice-assistant .
docker run -p 8501:8501 invoice-assistant
```

Render (`render.yaml`) and Railway (`railway.json`) configs are included — see [DEPLOYMENT.md](./DEPLOYMENT.md). For air-gapped installs see [ON-PREM.md](./ON-PREM.md).

---

## Project Structure

```text
app.py                  Batch extraction page (entry point)
pages/                  Other Streamlit pages
extractor/
  engine.py             Template extraction engine
  generic.py            AI extraction pipeline
  builder.py            Template builder + LLM provider clients
  autotemplate.py       Offline template auto-build
  ocr.py                OCR (RapidOCR + PyMuPDF), page rendering
  classify.py           Vendor auto-detection
  validate.py           Arithmetic validation
  reconcile.py          Cross-check against printed totals
  rules.py / dedupe.py  Business rules / duplicate detection
  export.py / exporters.py  Excel / Tally, QuickBooks, JSON
  security.py           Upload checks, image→PDF, AI guardrails, audit log
  ui.py                 Shared UI components
templates/              Vendor templates (YAML)
tests/                  pytest suite
```

---

## Testing

```bash
pip install pytest
python -m pytest tests/
```

CI runs the suite on every push (`.github/workflows/ci.yml`).

---

## Documentation

- [ARCHITECTURE.md](./ARCHITECTURE.md) — technical architecture
- [PROJECT_EXPLANATION.md](./PROJECT_EXPLANATION.md) — component reference
- [SECURITY.md](./SECURITY.md) — security model
- [DEPLOYMENT.md](./DEPLOYMENT.md) · [ON-PREM.md](./ON-PREM.md)

## License

MIT — see [LICENSE](./LICENSE).
