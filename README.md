# Invoice Assistant

[![CI](https://github.com/jainmokshit1-byte/Invoice-Assistant/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/jainmokshit1-byte/Invoice-Assistant/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.36+-FF4B4B.svg)
![Tests](https://img.shields.io/badge/tests-68%20passed-brightgreen.svg)
![License MIT](https://img.shields.io/badge/license-MIT-green.svg)
![Docker Ready](https://img.shields.io/badge/docker-ready-2496ED.svg)

**Invoice Assistant** is an enterprise-grade, privacy-first invoice intelligence and accounts payable (AP) automation platform. It extracts structured data from **any PDF invoice** — whether digital/vector or scanned paper receipts — validates arithmetic consistency, enforces business compliance rules, flags duplicate submissions, and exports accounting-ready records to **Excel (.xlsx)**, **Tally Prime XML**, **QuickBooks CSV**, and **JSON**.

---

## Key Highlights

- **Dual Extraction Architecture**:
  - **Deterministic Template Engine**: High-speed, zero-latency, millisecond extraction using coordinate-based bounding boxes for recurring vendor invoices. Completely offline with zero hallucinations.
  - **Universal AI Extractor**: Zero-shot, template-free extraction for arbitrary and non-standard invoices using state-of-the-art LLMs (Anthropic Claude, OpenAI GPT-4o, Google Gemini, Groq, Mistral, OpenRouter, or local Ollama).
- **Intelligent Hybrid Text & OCR Pipeline**:
  - Native text and word-level coordinate extraction via **pdfplumber**.
  - Automatic detection of scanned invoices with fallback to **RapidOCR (ONNX)** rendered at 300 DPI via **PyMuPDF (`fitz`)**.
  - Completely local ONNX execution — **no external Tesseract or CUDA dependencies required**.
  - Three-tier OCR confidence tagging (`[?text?]` for 0.4–0.5 confidence, `[??text??]` for <0.4 confidence).
- **Dual-Pass Arithmetic & Optical Reconciliation**:
  - Independent mathematical validation: verifies that `Quantity × Rate ≈ Line Total` and `Subtotal + Tax = Total`.
  - Optical ground-truth reconciliation: cross-checks extracted amounts against raw PDF printed values with configurable tolerance (`±0.05`).
- **Visual & Automated Template Studio**:
  - **Auto-Build**: 1-click automatic layout discovery that infers headers, tables, and anchor coordinates from a single sample PDF (100% offline, no AI required).
  - **AI Synthesize**: One-shot template generation via LLM.
  - **Point & Click**: Interactive coordinate mapper directly on document image previews.
- **Enterprise Security, Privacy & Air-Gapped Operation**:
  - **100% Offline Capability**: Run completely air-gapped using local templates and local LLMs via Ollama/vLLM.
  - **Zero Telemetry**: No tracking, phone-home, or third-party analytics.
  - **Cloud-Lockout Mode**: One toggle hard-blocks any network transmission to cloud providers.
  - **PII & Secret Scrubbing**: Automatic redaction of sensitive identifiers (bank accounts, IBANs, credit cards, emails, API keys).
  - **Prompt Injection Defense**: Untrusted invoice content is quarantined inside strict `<INVOICE_DATA>` anti-injection fences.
  - **Tamper-Evident Audit Trail**: All actions and file operations are recorded locally in `output/audit.csv`.
- **Deduplication & Fraud Protection**:
  - Dual-fingerprint verification: compares SHA-256 file hashes and `(vendor, invoice_number, invoice_date, total)` tuples against historical records to prevent double payments.
- **Accounting & ERP Integration**:
  - **Excel (`.xlsx`)**: Formatted workbooks with header metadata and itemized line items.
  - **Tally Prime XML**: Direct import format for Tally ERP systems.
  - **QuickBooks CSV**: Compatible bills import format.
  - **JSON Ledger**: Standardized JSON data format.
- **Modern Neobrutalist UI**:
  - Responsive, accessible interface featuring bold borders, hard offset shadows, high-contrast typography, in-line editable tables, and Material symbols.

---

## Application Pages & Workflows

The application provides a full-featured multi-page interface:

| Page | File | Purpose |
| :--- | :--- | :--- |
| **Batch Processing & Template Engine** | [`app.py`](./app.py) | Main dashboard. Auto-detects vendor templates, runs high-speed batch extractions, provides in-line editable header/line-item tables, displays arithmetic verification cards, and exports to Excel, Tally XML, QuickBooks CSV, and JSON. |
| **Extract Any Invoice** | [`pages/1_Extract_Any_Invoice.py`](./pages/1_Extract_Any_Invoice.py) | Universal AI-powered extractor. Processes arbitrary, unstructured, or unseen invoices without templates using multi-provider LLMs with RapidOCR fallback. |
| **Add New Vendor** | [`pages/2_Add_New_Vendor.py`](./pages/2_Add_New_Vendor.py) | Interactive template studio. Create recurring extraction templates via **Auto-build** (100% offline), **AI-assisted synthesis**, **Point-and-click coordinate selection**, or dropdown picking. |
| **Data & Template Hub** | [`pages/3_Manage.py`](./pages/3_Manage.py) | Manage active vendor templates, delete obsolete configurations, inspect generated output files, and clear duplicate detection history. |
| **Business Rules & Compliance** | [`pages/4_Business_Rules.py`](./pages/4_Business_Rules.py) | Configure per-vendor or global compliance checks (e.g., mandatory PO numbers, maximum spending thresholds, tax breakup requirements, future date prevention). |
| **Security & Audit Controls** | [`pages/5_Security_and_Logs.py`](./pages/5_Security_and_Logs.py) | Control privacy policies, enforce offline-only modes, configure PII redaction, set file upload thresholds, and inspect tamper-evident audit logs. |

---

## System Architecture & Data Flow

```
                     ┌──────────────────────────────┐
                     │   User Uploads PDF Invoice   │
                     └──────────────┬───────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────┐
                     │  File Safety & Hash Checks   │  ──► (SHA-256 calculation,
                     │  (extractor/security.py)     │       size limits verification)
                     └──────────────┬───────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────┐
                     │  Density & Layout Inspector  │
                     └──────┬────────────────┬──────┘
                            │                │
            Native Text     │                │ Scanned Document
            (>50 chars/pg)  │                │ (<50 chars/pg)
                            ▼                ▼
                     ┌─────────────┐  ┌─────────────────────────┐
                     │ pdfplumber  │  │ PyMuPDF (300 DPI image) │
                     │ Text Vector │  │ RapidOCR (ONNX Runtime) │
                     └──────┬──────┘  └────────────┬────────────┘
                            │                      │
                            └──────────┬───────────┘
                                       │
                      ┌────────────────┴────────────────┐
                      │    Extraction Path Selection    │
                      └───────┬──────────────────┬──────┘
                              │                  │
         Template Mode (app.py)                  │ Universal AI Mode (Page 1)
                              ▼                  ▼
              ┌─────────────────────────┐  ┌─────────────────────────┐
              │ Vendor Auto-Detection   │  │ Anti-Injection Guard    │
              │ (extractor/classify.py) │  │ & PII Redaction          │
              │ Exact Bounding Box Match│  │ Multi-Provider LLM Call │
              │ (extractor/engine.py)   │  │ Structured Table Mapping│
              └───────────────┬─────────┘  └─────────────┬───────────┘
                              │                          │
                              └───────────┬──────────────┘
                                          │
                                          ▼
                       ┌──────────────────────────────────────┐
                       │   Post-Processing & Verification     │
                       │   - Date Normalization (11 formats)  │
                       │   - Math Validation (Qty x Rate)     │
                       │   - Subtotal + Tax = Total Check     │
                       │   - Optical Printed Total Reconcile  │
                       │   - Business Rules Enforcement       │
                       │   - Duplicate Fingerprint Check      │
                       └──────────────────┬───────────────────┘
                                          │
                                          ▼
                       ┌──────────────────────────────────────┐
                       │     Multi-Format Accounting Export   │
                       │     - Formatted Excel (.xlsx)        │
                       │     - Tally Prime XML                │
                       │     - QuickBooks CSV                 │
                       │     - JSON Ledger                    │
                       └──────────────────────────────────────┘
```

---

## Tech Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Runtime** | Python 3.12 | Core execution environment (required for ONNX dependencies) |
| **User Interface** | Streamlit (1.36+) | Multi-page responsive web dashboard with custom Neobrutalist design |
| **PDF Extraction** | `pdfplumber` (0.11+) | Coordinate-aware native PDF text, word layout, and table extraction |
| **PDF Rendering** | PyMuPDF (`fitz` 1.24+) | High-resolution rasterization (300 DPI) for OCR and scanned page detection |
| **OCR Engine** | `rapidocr-onnxruntime` | Offline ONNX-based optical character recognition without Tesseract |
| **AI LLM Clients** | OpenAI, Anthropic, Gemini, Groq, Mistral, Ollama | Universal multi-provider LLM support with auto-retry and schema validation |
| **Data Contracts** | Pydantic (2.0+) | Strict typed validation for Invoices and Line Items |
| **Spreadsheet Engine** | `openpyxl` (3.1+) | Generating formatted, multi-tab Excel workbooks |
| **Config & Templates** | `PyYAML` (6.0+) | Parsing vendor templates, compliance rules, and security policies |
| **Test Suite** | `pytest` (9.1+) | 68 automated unit and integration tests |
| **Containerization** | Docker | Production-ready multi-stage container deployment |

---

## Python Version Requirement

> **You must use Python 3.12.** Python 3.13 and 3.14 are NOT supported.

`rapidocr-onnxruntime` requires pre-compiled ONNX Runtime wheels available for Python 3.12. Running on Python 3.13 or newer will cause package installation failures or require a C++ compiler to build dependencies from source.

- Download Python 3.12: [python.org/downloads/release/python-3120/](https://www.python.org/downloads/release/python-3120/)
- When installing on Windows, remember to check **"Add Python to PATH"**.

---

## Prerequisites & API Setup

1. **Python 3.12** installed.
2. *(Optional — for Universal AI Extractor only)* An API key from any of the following providers:
   - [Anthropic Console](https://console.anthropic.com/) (Claude 3.5 Sonnet / Claude 3 Haiku)
   - [OpenAI Platform](https://platform.openai.com/) (GPT-4o / GPT-4o-mini)
   - [Google AI Studio](https://aistudio.google.com/) (Gemini 2.5 Flash / Gemini 1.5 Pro)
   - [Groq Console](https://console.groq.com/) (Llama 3.3 70B Versatile)
   - [Mistral AI](https://console.mistral.ai/)
   - [OpenRouter](https://openrouter.ai/)
   - **Or 100% Free & Local**: [Ollama](https://ollama.ai/) running locally at `http://localhost:11434/v1` (e.g. `llama3.2`, `mistral`, `qwen2.5`).

*(Note: The main template extraction engine, rule validator, and OCR work 100% offline without any API keys).*

---

## Installation & Getting Started

### Windows

#### Option A — One-Click Launcher (Fastest)

Double-click:
```text
Start Invoice Tool.bat
```
This launcher checks for Python 3.12, creates the virtual environment (`venv312`) if needed, installs dependencies, and launches the app in your browser.

#### Option B — Manual PowerShell Setup

1. **Clone the repository**:
   ```powershell
   git clone https://github.com/jainmokshit1-byte/Invoice-Assistant.git
   cd Invoice-Assistant
   ```

2. **Allow PowerShell script execution** (if needed):
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

3. **Create and activate Python 3.12 virtual environment**:
   ```powershell
   py -3.12 -m venv venv312
   .\venv312\Scripts\Activate.ps1
   ```

4. **Install dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

5. **Run the Streamlit application**:
   ```powershell
   python -m streamlit run app.py
   ```

---

### macOS & Linux

1. **Clone the repository**:
   ```bash
   git clone https://github.com/jainmokshit1-byte/Invoice-Assistant.git
   cd Invoice-Assistant
   ```

2. **Create and activate Python 3.12 virtual environment**:
   ```bash
   python3.12 -m venv venv312
   source venv312/bin/activate
   ```

3. **Install system dependencies** (for Debian/Ubuntu):
   ```bash
   sudo apt-get update && sudo apt-get install -y libgl1-mesa-glx libglib2.0-0
   ```

4. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Run the application**:
   ```bash
   python -m streamlit run app.py
   ```

The application will open in your default browser at `http://localhost:8501`.

---

## Testing with Sample Invoices

The repository includes ready-to-test sample invoices in [`sample_invoices/`](./sample_invoices/):
- `sample_invoices/acme_001.pdf`
- `sample_invoices/acme_002.pdf`
- `sample_invoices/globex_001.pdf`

To generate additional synthetic test invoices, run:
```bash
python scripts/make_sample_invoices.py
```

---

## Docker & Cloud Deployment

### Local Docker Run

The project includes a production multi-stage [`Dockerfile`](./Dockerfile):

```bash
# Build the Docker container image
docker build -t invoice-assistant .

# Run the container on port 8501
docker run -p 8501:8501 invoice-assistant
```

Open [http://localhost:8501](http://localhost:8501) to access the app.

### Deploying to Render or Railway

- **Render**: Connect the repository and select **Blueprint**. Render automatically loads [`render.yaml`](./render.yaml).
- **Railway**: Connect the repository. Railway detects [`railway.json`](./railway.json) and [`Dockerfile`](./Dockerfile) automatically.

For detailed cloud deployment instructions, see [`DEPLOYMENT.md`](./DEPLOYMENT.md).

---

## Configuration

### Security & OCR Configuration (`security.yaml`)

```yaml
allow_cloud_ai: true          # Set false to hard-block all external AI endpoints
redact_before_ai: false       # Redact PII (bank accounts, emails, phones) before AI calls
max_file_mb: 25               # Maximum upload file size in megabytes
max_batch_files: 100          # Maximum documents in a single batch
max_text_chars_for_ai: 60000  # Character cap for LLM context injection
ocr_enabled: true             # Enable or disable RapidOCR fallback
ocr_dpi: 300                  # Rendering resolution for scanned pages
ocr_min_chars: 50             # Trigger OCR if page text length falls below this
ocr_min_confidence: 0.5       # OCR acceptance confidence threshold
```

### Business Rules Configuration (`rules.yaml`)

```yaml
global:
  require_any:
    - [invoice_number, po_number]  # Must contain at least one ID
  require_line_items: true         # Flag invoices missing line items
  require_tax_breakup: false       # Enforce separate tax breakup
  date_not_future: true            # Disallow future invoice dates
  max_total: 100000.0              # Alert on invoices exceeding threshold

vendors:
  acme:
    require_any:
      - [po_number]                # Acme requires a PO number specifically
```

---

## Project Structure

```text
Invoice-Assistant/
├── .github/
│   └── workflows/
│       └── ci.yml              # GitHub Actions CI workflow (tests on Python 3.12)
├── .streamlit/
│   └── config.toml             # Streamlit server & custom theme configuration
├── extractor/                  # Core extraction, OCR & validation package
│   ├── __init__.py             # Public API exports
│   ├── autotemplate.py         # 1-click automatic layout discovery & template generation
│   ├── builder.py              # Interactive template builder & LLM client wrappers
│   ├── classify.py             # Vendor template keyword scoring & layout classification
│   ├── dedupe.py               # Duplicate detection ledger & hash tracking
│   ├── engine.py               # Deterministic bounding-box template extraction engine
│   ├── export.py               # Formatted Excel (.xlsx) export engine
│   ├── exporters.py            # Tally XML, QuickBooks CSV, and JSON ledger exporters
│   ├── generic.py              # Universal AI extraction pipeline with auto-retry
│   ├── models.py               # Pydantic data schemas (Invoice, LineItem)
│   ├── ocr.py                  # PyMuPDF rendering & RapidOCR ONNX fallback
│   ├── pdf_utils.py            # Layout-aware X-coordinate table & summary extraction
│   ├── reconcile.py            # Printed totals optical cross-check & math verification
│   ├── rules.py                # Business rules engine & preset management
│   ├── security.py             # Sanitization, secret redaction & audit logging
│   ├── templates.py            # YAML template loaders, savers & validators
│   ├── ui.py                   # Responsive Neobrutalist design system & components
│   ├── utils.py                # Number parsing (_num) and multi-format date normalization
│   ├── validate.py             # Mathematical sanity validation & confidence scoring
│   └── validators.py           # Invoice number validation & Qty x Rate line math
├── pages/                      # Streamlit multi-page interface
│   ├── 1_Extract_Any_Invoice.py# AI Universal Extractor UI
│   ├── 2_Add_New_Vendor.py     # Template Studio (Auto-build, AI, Point & Click)
│   ├── 3_Manage.py             # Template & data management hub
│   ├── 4_Business_Rules.py     # Compliance & business rules configuration
│   └── 5_Security_and_Logs.py  # Security settings, PII redaction & audit trail
├── sample_invoices/            # Sample PDF invoices for testing
│   ├── acme_001.pdf
│   ├── acme_002.pdf
│   └── globex_001.pdf
├── scripts/
│   └── make_sample_invoices.py # Synthetic sample invoice PDF generator
├── templates/                  # Installed YAML vendor templates
│   ├── acme.yaml
│   ├── anthropic.yaml
│   ├── doordash.yaml
│   ├── globex.yaml
│   ├── indigo.yaml
│   ├── it_gst_invoices.yaml
│   └── meridian.yaml
├── tests/                      # Automated test suite (68 tests)
│   ├── test_core_modules.py
│   ├── test_generic.py
│   ├── test_num.py
│   ├── test_pdf_utils.py
│   ├── test_reconcile.py
│   ├── test_security.py
│   ├── test_utils.py
│   ├── test_validate.py
│   └── test_validators.py
├── app.py                      # Main application entry point & batch extraction dashboard
├── run.py                      # Programmatic launcher script
├── rules.yaml                  # Configured business rules
├── security.yaml               # Security, OCR & file upload settings
├── requirements.txt            # Production Python package requirements
├── requirements-onprem.txt     # Air-gapped on-premise package requirements
├── Dockerfile                  # Production container definition
├── render.yaml                 # Render Blueprint deployment config
├── railway.json                # Railway deployment config
├── Start Invoice Tool.bat      # Windows one-click desktop launcher
├── setup_venv312.bat           # Windows virtual environment setup script
├── ARCHITECTURE.md             # Deep technical architecture documentation
├── DEPLOYMENT.md               # Cloud deployment guide (Render, Railway, Docker)
├── ON-PREM.md                  # Air-gapped / on-premise installation guide
├── PROJECT_EXPLANATION.md      # Comprehensive technical breakdown & component reference
├── SECURITY.md                 # Security architecture & privacy whitepaper
└── README.md                   # Project documentation
```

---

## Running the Automated Test Suite

Run the full automated test suite using `pytest`:

```bash
python -m pytest tests/ -v --tb=short
```

The test suite covers:
- Core template engine loading and execution
- Layout-aware column gap detection and X-coordinate mapping
- Mathematical line-item verification (`Qty × Rate ≈ Line Total`)
- Subtotal and tax consistency checks
- Date normalization across 11 international date formats
- Number and currency string sanitization
- Prompt injection defense and secret scrubbing
- Duplicate invoice detection and history tracking

---

## Troubleshooting

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| `running scripts is disabled on this system` | PowerShell Execution Policy | Run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` in PowerShell. |
| `No module named rapidocr_onnxruntime` | Wrong Python version (3.13 or 3.14) | Recreate virtual environment with Python 3.12: `py -3.12 -m venv venv312`. |
| `No text could be extracted from page` | Scanned invoice with OCR disabled | Verify `security.yaml` has `ocr_enabled: true` and that `rapidocr-onnxruntime` is installed. |
| `OCR Triggered: 0` for scanned invoices | Virtual environment not activated | Activate environment (`.\venv312\Scripts\Activate.ps1` or `source venv312/bin/activate`) before running. |
| `AI Extraction Failed: Connection Error` | Invalid API key or model name | Check **Provider & Model Configuration** on the **Extract Any Invoice** page and verify API keys or base URL. |
| `Cloud provider blocked` | Offline policy is enabled | In **Security & Logs**, enable *Allow cloud AI providers*, or point the base URL to a local Ollama instance (`http://localhost:11434/v1`). |
| Duplicate warning displayed | Invoice was processed previously | The invoice hash or tuple exists in `output/history.csv`. Clear history in **Manage** if re-processing is intentional. |

---

## License

This project is licensed under the [MIT License](./README.md).
