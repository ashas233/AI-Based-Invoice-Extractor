# Invoice Extractor — Project Report

**Purpose:** Interview preparation and project overview  
**Project type:** Human-reviewed invoice extraction application  
**Current public demo:** [Hugging Face Static Space](https://huggingface.co/spaces/ashas2345/invoice-extractor-free-demo)

## 1. Executive summary

Invoice Extractor is designed to turn invoice PDFs and images into structured,
reviewable invoice records. Its full application uses a Streamlit user
interface and a FastAPI backend. The backend prepares uploaded documents,
sends page images to an Anthropic vision model, parses the response into typed
invoice data, and runs business checks before the user reviews and saves it.
Saved invoices can be listed and exported to CSV or Excel.

The public free demo is intentionally different from the full application. It
is a static sample page, not a running Python service. It demonstrates example
fields and a simple arithmetic check, but it does not upload documents, call
an AI provider, or save data.

## 2. Problem and goals

Invoices arrive as PDFs, scans, or phone photos and vary in layout. Manually
copying vendor, date, line-item, and total information into a consistent
record can be slow. This project explores an end-to-end workflow that:

- Accepts common invoice documents.
- Converts supported documents into images for vision-based extraction.
- Returns data in a consistent schema.
- Checks arithmetic and basic field formats in application code.
- Keeps a human in the loop to correct and approve results.
- Stores approved records and supports later export.

## 3. System architecture

```text
                         Full application
┌──────────┐   HTTP    ┌──────────────┐
│ Browser  │ ────────► │ Streamlit UI │  :8501
└──────────┘           └──────┬───────┘
                              │ API_URL
                              ▼
                       ┌──────────────┐
                       │ FastAPI API  │  :8000
                       └──────┬───────┘
                              │
             ┌────────────────┼────────────────┐
             ▼                ▼                ▼
       Preprocessing    Anthropic vision   SQLite or
       PDF/photo pages  extraction         PostgreSQL
             │                │
             └───────► schema + validation
                              │
                              ▼
                   UI review → save → export

                  Free public sample demo
┌──────────┐   serves static HTML    ┌────────────────────┐
│ Browser  │ ──────────────────────► │ Hugging Face Space │
└──────────┘                         └────────────────────┘
```

In the full application, Streamlit is the presentation layer and FastAPI owns
the HTTP endpoints and application operations. The Streamlit UI uses the
`API_URL` environment variable to locate the API. In Docker Compose, the UI
reaches the API through the internal `api` service name.

## 4. Invoice processing flow

1. **Upload:** The user selects a PDF or image in the Streamlit interface.
2. **Request:** The UI sends the file to `POST /extract`.
3. **Input checks:** The API rejects uploads larger than 15 MB.
4. **Preprocessing:** PyMuPDF renders up to eight PDF pages at 150 DPI.
   Pillow applies EXIF orientation correction, autocontrast, resizing to a
   maximum 1,800-pixel side, and JPEG encoding. A supported photo is processed
   as an image page.
5. **Vision extraction:** The extractor sends page images to Anthropic. Prompt
   instructions request JSON matching the invoice schema, use null for
   invisible values, and avoid inventing information.
6. **Schema parsing:** Pydantic parses the response into an `Invoice` and its
   `LineItem` records.
7. **Business checks:** Application code checks line-item arithmetic,
   subtotal/tax/total relationships, date format, currency format, and
   negative totals.
8. **Correction attempt:** When the model response parses but validation finds
   problems, the extractor requests one correction pass by default. Thus the
   normal maximum is two model attempts. A malformed schema response can also
   be sent back for correction.
9. **Human review:** The UI displays the result and validation messages. Users
   can edit invoice fields and line items before saving.
10. **Save and export:** `POST /invoices` validates user-edited data again,
    saves it, and returns an ID. The UI can show history and request CSV or
    Excel exports.

## 5. Main components

| Component | Responsibility |
|---|---|
| `ui/streamlit_app.py` | Upload, preview, editable review, history, downloads, and local sample-demo UI |
| `app/main.py` | FastAPI routes, request flow, upload limit, vendor matching, duplicate checks, and database/export orchestration |
| `app/preprocess.py` | PDF/photo conversion and image normalization |
| `app/extractor.py` | Anthropic request, prompt, JSON parsing, and correction loop |
| `app/schemas.py` | Pydantic models for invoice, line item, extraction response, and save response |
| `app/validators.py` | Arithmetic, date, currency, and negative-total checks |
| `app/db.py` | SQLite/PostgreSQL initialization, save, query, and duplicate lookup |
| `app/vectorstore.py` | Optional FAISS-backed vendor-name matching and canonicalization |
| `app/export.py` | Flattening invoice rows and producing CSV/XLSX downloads |
| `eval/` | Synthetic dataset creation and extraction-quality evaluation |
| `tests/` | Unit tests for database operations and invoice validation |
| `infra/` | Azure deployment templates |
| `static_demo/index.html` | Standalone, sample-only page deployed to the free public Space |

## 6. API surface

| Method and path | Purpose |
|---|---|
| `GET /health` | Basic API health response |
| `POST /extract` | Accept an uploaded file and return extracted invoice data |
| `POST /demo` | Return fixed sample data without calling the AI provider |
| `POST /invoices` | Revalidate and save a reviewed invoice |
| `GET /invoices` | List saved invoice records |
| `GET /export?format=csv` | Download CSV |
| `GET /export?format=xlsx` | Download Excel; XLSX is the default format |

Extraction responses include the invoice, validation issues, possible
canonical vendor and duplicate indicator, page count, latency, and model token
usage.

## 7. Data model and storage

An invoice includes a required vendor name and total, optional invoice number,
date, currency, tax ID, subtotal, and tax, plus a list of line items. Each line
item has a description and amount, with optional quantity and unit price.

SQLite is the default local backend, with `data/invoices.db` as the default
path. PostgreSQL is supported by setting `DB_BACKEND=postgres` and configuring
the connection variables. Invoice payloads and validation issues are stored
as JSON along with searchable invoice columns.

Potential duplicates are identified using canonical vendor name, invoice
number, and total. Vendor canonicalization is separate and optional: the
FAISS-backed index uses normalized sentence embeddings and a configurable
similarity threshold (0.85 by default). Set `USE_VECTOR=0` to disable it.

## 8. Technology choices

- **Python:** backend and document processing.
- **Streamlit:** rapid development of an interactive review interface.
- **FastAPI:** typed HTTP API and request/response models.
- **PyMuPDF and Pillow:** rendering PDF pages and preparing images.
- **Anthropic vision API:** extracting fields from invoice page images.
- **Pydantic:** validating and representing structured invoice data.
- **SQLite / PostgreSQL:** persistence options for local and configured
  deployments.
- **Sentence Transformers and FAISS:** optional vendor similarity matching.
- **Pandas and OpenPyXL:** tabular formatting and CSV/XLSX output.
- **Pytest:** automated unit tests.

## 9. Reliability and safety considerations

The design uses multiple layers of checking: request-size limits,
preprocessing errors, schema parsing, business validation, and human review.
The save endpoint repeats business validation because users can change values
in the UI. The extractor explicitly asks the model not to guess missing data.

Real extraction requires a configured `ANTHROPIC_API_KEY`; the key should be
kept in an environment or secret manager, never committed to source control.
Invoices can contain sensitive personal and business information, so real
documents should not be uploaded to a public demo or shared without
authorization.

## 10. Testing and evaluation

The existing unit tests cover validator behavior and basic SQLite operations.
The focused suite was previously run with **8 passing tests**. The project
also includes an evaluation runner that compares model output with labeled
invoices and reports field accuracy, line-item matching, math-validation
success, latency, estimated cost, and failures.

Unit tests do not establish production extraction accuracy. That requires
running evaluations against a representative, properly authorized dataset and
tracking model/provider changes over time.

## 11. Deployment status

### Local full application

The full UI and API can run as two local processes on ports 8501 and 8000.
Real invoice extraction requires an Anthropic key and a working provider
account.

### Public free demo

The public Hugging Face Space is:

**https://huggingface.co/spaces/ashas2345/invoice-extractor-free-demo**

It is a public Static Space. Its page runs in the visitor's browser and
demonstrates fictional sample data and an arithmetic check. It has no backend
compute, model call, upload flow, or database persistence. The source is
public.

### Cloud templates

The repository includes Azure Container Apps templates for a separate cloud
deployment. They describe a UI and API container, Azure Files-backed SQLite
storage, container registry access through managed identity, and optional
Microsoft Entra authentication. Provisioning these resources may incur
charges; they are not part of the free static demo.

## 12. Known limitations and future work

**Current limitations**

- AI extraction depends on an external API and a valid key; model results can
  still be wrong.
- The pipeline handles at most eight PDF pages and a 15 MB upload.
- Business validation catches selected consistency issues, not every possible
  invoice-specific rule.
- Vendor similarity matching is threshold-based and requires evaluation on
  real vendor names.
- The public free demo does not perform real extraction.
- Broader API, integration, authentication, and security testing would be
  needed before production use.

**Possible next steps**

1. Add API and end-to-end tests for uploads, malformed documents, provider
   errors, editing, saving, and export.
2. Add authentication, authorization, rate limits, and stronger file-content
   validation.
3. Add structured logging, monitoring, and clear operational error reporting.
4. Add database migrations, backup/retention policies, and privacy controls.
5. Evaluate field-level accuracy and confidence on an authorized,
   representative dataset.
6. Improve handling of low-confidence fields, multi-invoice documents, and
   documents beyond the current page limit.

## 13. Interview presentation

### 30-second summary

> “I built an invoice-extraction application with a Streamlit frontend and a
> FastAPI backend. The backend preprocesses invoice PDFs or images, sends them
> to a vision model, parses the response into a Pydantic schema, and checks
> business arithmetic. Users review and edit the result before it is saved to
> SQLite, and they can export invoice history as CSV or Excel. The public free
> demo is a separate static sample page; actual document extraction needs the
> full backend and an API key.”

### Likely interviewer questions

**Why use a vision model instead of fixed templates?**  
Invoice layouts vary between vendors. A vision model can interpret varied
layouts, while the schema and validation make the result easier to consume.
The tradeoff is that model output can be inaccurate and must be checked.

**Why validate arithmetic in code?**  
The model may misread a number or produce inconsistent calculations.
Deterministic code can check the relationships that matter, and a user can
review the remaining ambiguities.

**Why ask a person to review the result?**  
Arithmetic checks cannot prove the values were read correctly from the source.
Human review lets the user correct extracted information before persistence.

**How do the frontend and backend communicate?**  
The Streamlit app makes HTTP requests to FastAPI. `API_URL` configures the
backend address, which supports separate local processes and container
services.

**How would you take this toward production?**  
I would prioritize user authentication, upload security, rate limiting,
secret management, observability, database migrations and backups,
end-to-end testing, and evaluation on representative authorized documents.
I would also define privacy, retention, and access policies for invoice data.

**What is the biggest limitation?**  
The model can still make extraction errors, so accuracy must be evaluated and
the human review step is important. Also, the current public free demo is a
static preview and does not extract uploaded invoices.

## 14. Files to review

- [API routes and orchestration](./app/main.py)
- [Extraction prompt and correction loop](./app/extractor.py)
- [Document preprocessing](./app/preprocess.py)
- [Invoice schemas](./app/schemas.py)
- [Business validation](./app/validators.py)
- [Persistence](./app/db.py)
- [Frontend workflow](./ui/streamlit_app.py)
- [Free public demo source](./static_demo/index.html)
