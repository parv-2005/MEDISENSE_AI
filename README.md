# MediSense AI

MediSense AI turns a medical report (a PDF or a photo of one) into a plain-language explanation and lets the patient ask follow-up questions that are answered strictly from the report's own text.

The system implements the six stages of the working flowchart end to end:

1. **Authentication** with JWT tokens
2. **Upload** of a PDF or image, stored on disk with metadata in MongoDB
3. **Text extraction** through an OCR pipeline that picks PyMuPDF for digital PDFs and Tesseract for scans
4. **AI analysis** with Google Gemini, producing a structured, per-value explanation
5. **RAG follow-up questions** over a ChromaDB vector store
6. **A Next.js dashboard** to view reports, extracted text, analysis and ask questions

Companion documents:

- [ARCHITECTURE.md](ARCHITECTURE.md) explains every component, data model and request path.
- [DECISIONS.md](DECISIONS.md) records each major design decision and why it was made.

---

## Table of contents

1. [Repository layout](#1-repository-layout)
2. [Prerequisites](#2-prerequisites)
3. [Where to paste your API keys](#3-where-to-paste-your-api-keys)
4. [Install and run, step by step](#4-install-and-run-step-by-step)
5. [How the system works, stage by stage](#5-how-the-system-works-stage-by-stage)
6. [API reference](#6-api-reference)
7. [Data stored in MongoDB and ChromaDB](#7-data-stored-in-mongodb-and-chromadb)
8. [Running the tests](#8-running-the-tests)
9. [Configuration reference](#9-configuration-reference)
10. [Troubleshooting](#10-troubleshooting)
11. [Evaluation notes for research use](#11-evaluation-notes-for-research-use)
12. [Limitations and safety](#12-limitations-and-safety)

---

## 1. Repository layout

```
MediSense AI/
├── README.md              this file
├── ARCHITECTURE.md        component-level architecture and data flow
├── DECISIONS.md           design decision log
├── backend/               FastAPI service (Python 3.11+)
│   ├── app/
│   │   ├── main.py                 application factory, CORS, lifespan (MongoDB connect)
│   │   ├── config.py               settings loaded from .env
│   │   ├── database.py             Motor client, collection names, indexes
│   │   ├── core/security.py        bcrypt password hashing, JWT issue/verify
│   │   ├── core/deps.py            current-user dependency
│   │   ├── models/schemas.py       Pydantic request/response models
│   │   ├── routers/auth.py         /api/auth/*
│   │   ├── routers/reports.py      /api/reports/*  (upload, extract, analyze, ask)
│   │   └── services/
│   │       ├── storage.py          save uploads to disk
│   │       ├── ocr/                pdf_detect, digital, scanned, preprocess, cleaner, pipeline
│   │       ├── analysis_service.py Gemini prompt + structured-output parsing
│   │       ├── gemini_client.py    the only module that talks to Gemini
│   │       └── rag/                chunker, vector_store (ChromaDB), qa_service
│   ├── tests/                      55 pytest tests (unit + end-to-end API)
│   ├── uploads/                    uploaded files (created at runtime)
│   ├── chroma_db/                  ChromaDB persistent store (created at runtime)
│   ├── requirements.txt            minimum versions
│   ├── requirements.lock.txt       exact versions that passed the test suite
│   └── .env.example                copy to .env and fill in keys
└── frontend/              Next.js 15 app (React 19, Tailwind CSS 4)
    ├── app/                        login, register, dashboard, reports/[id]
    ├── components/                 PipelineRail, AnalysisView, AskPanel, ui
    ├── lib/api.ts                  typed client for the backend
    ├── lib/auth.tsx                auth context, route guard
    └── .env.local.example          copy to .env.local
```

## 2. Prerequisites

| Requirement | Why | Install |
|---|---|---|
| Python 3.11 or newer | backend | https://www.python.org/downloads/ |
| Node.js 20 or newer | frontend | https://nodejs.org/ |
| MongoDB 6 or newer | stores users, reports, analyses, Q&A | local server or free Atlas cluster (https://www.mongodb.com/atlas) |
| Tesseract OCR 5 | reads scanned PDFs and images | Windows: https://github.com/UB-Mannheim/tesseract/wiki, macOS: `brew install tesseract`, Debian/Ubuntu: `sudo apt install tesseract-ocr` |
| Google Gemini API key | analysis and embeddings | https://aistudio.google.com/app/apikey |

Tesseract is only needed when a scanned PDF or an image is uploaded. Digital PDFs work without it. Poppler is **not** required; PyMuPDF renders pages itself.

## 3. Where to paste your API keys

Only one external API is used: **Google Gemini** (via the official `google-genai` SDK). It provides both the analysis model and the embedding model, so a single key runs the whole AI side.

### Backend keys and connection strings

Create `backend/.env` by copying the template:

```bash
cd backend
cp .env.example .env        # PowerShell: Copy-Item .env.example .env
```

Then edit `backend/.env` and fill in these three lines:

```ini
GEMINI_API_KEY=paste-your-gemini-key-here
MONGODB_URI=mongodb://localhost:27017        # or your Atlas mongodb+srv:// string
JWT_SECRET=paste-a-long-random-secret-here   # generate: python -c "import secrets; print(secrets.token_urlsafe(48))"
```

If Tesseract is not on your PATH, also set:

```ini
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

### Frontend

Create `frontend/.env.local`:

```bash
cd frontend
cp .env.local.example .env.local
```

It contains one value, the backend URL. The default is correct for local use:

```ini
NEXT_PUBLIC_API_URL=http://localhost:8000
```

No keys go in the frontend. The browser never talks to Gemini directly.

### Services that must be running

| Service | Default location | Needed for |
|---|---|---|
| MongoDB | `mongodb://localhost:27017` | everything (the backend refuses to start without it) |
| Gemini API | Google cloud, via key | stages 4 and 5 (analysis, questions) and indexing at the end of stage 3 |
| Tesseract | local binary | stage 3 for scans and images only |

## 4. Install and run, step by step

### Step 1: start MongoDB

Either run a local server:

```bash
mongod --dbpath /path/to/data
```

or create a free MongoDB Atlas cluster, allow your IP, and copy the connection string into `MONGODB_URI`.

### Step 2: backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env          # then edit .env as described in section 3
uvicorn app.main:app --reload --port 8000
```

Check it is alive:

```
GET http://localhost:8000/api/health   ->  {"status":"ok","model":"gemini-2.5-flash"}
```

Interactive API docs are served at http://localhost:8000/docs.

### Step 3: frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Open http://localhost:3000. You will be redirected to the sign-in page.

### Step 4: use it

1. Create an account.
2. On the dashboard, choose a PDF or image, or drop it on the panel.
3. You are taken to the report page. The pipeline rail shows Upload, Extract text, AI analysis and Ask filling in as each stage completes. Extraction and analysis run automatically after an upload.
4. Read the analysis, inspect the exact extracted text, and ask questions in the Ask tab.

## 5. How the system works, stage by stage

This section describes the exact processing path so it can be cited in a paper. File references point at the implementing module.

### Stage 1: Authentication

Files: `backend/app/routers/auth.py`, `backend/app/core/security.py`, `backend/app/core/deps.py`

1. **Register**: the client posts name, email and password. The email is lower-cased and checked against a unique index in the `users` collection. The password is hashed with **bcrypt** (cost factor 12, random per-password salt). The plaintext is never stored or logged.
2. **Login**: the stored hash is verified with a constant-time bcrypt comparison.
3. **Token**: on success the server issues a **JWT** (HS256) whose `sub` claim is the user's MongoDB `_id`, with `iat` and `exp` claims. The default lifetime is 24 hours.
4. **Protected routes**: every report endpoint depends on `get_current_user`, which reads the `Authorization: Bearer` header, verifies the signature and expiry, and loads the user document. Missing, expired or tampered tokens yield HTTP 401.
5. **Ownership**: every report query includes `user_id`, so a user can never read, analyse or delete another user's report. A foreign report ID returns 404, not 403, to avoid leaking existence.

### Stage 2: Upload report

Files: `backend/app/routers/reports.py` (`upload_report`), `backend/app/services/storage.py`

1. The multipart upload is validated by MIME type. Accepted: `application/pdf`, `image/png`, `image/jpeg`, `image/webp`, `image/tiff`, `image/bmp`. Anything else returns 415.
2. The file is streamed to `backend/uploads/<uuid>.<ext>` in 1 MB chunks, enforcing a size limit (25 MB by default, HTTP 413 when exceeded). The random name prevents path traversal and collisions.
3. A document is inserted into the `reports` collection with the original filename, stored filename, MIME type, size, `status: "uploaded"` and timestamps.
4. The response is the report record. The frontend then calls the extraction endpoint.

### Stage 3: Text extraction (OCR pipeline)

Files: `backend/app/services/ocr/pipeline.py` and siblings

The pipeline runs in a worker thread so the async server stays responsive.

1. **Fetch the report** by ID (owner-scoped) and locate the stored file. Status becomes `extracting`.
2. **Decide the branch** (`pdf_detect.py`). For PDFs, PyMuPDF extracts the text layer of every page and counts non-whitespace characters. A page with at least 40 such characters is considered to carry a real text layer. If at least half the pages qualify, the PDF is **digital**; otherwise it is treated as **scanned**. Images always take the OCR branch.
3. **Digital branch** (`digital.py`): `page.get_text("text")` on each page. This preserves reading order and line breaks, which matters for tabular lab results.
4. **Scanned branch** (`scanned.py`, `preprocess.py`):
   - Pages are rasterised by PyMuPDF at 300 DPI (no Poppler dependency).
   - Each page image is preprocessed with OpenCV: convert to grayscale, upscale small images so the page is at least 1200 px wide (cubic interpolation), bilateral filter to denoise while keeping edges, 3x3 median blur to remove speckle, then Otsu's automatic threshold to produce a clean black-on-white binary image.
   - Tesseract (`pytesseract`, English, `--oem 3 --psm 6`) reads each image. Page-segmentation mode 6 assumes a single uniform block of text, which suits report tables better than the default automatic layout analysis.
   - If the Tesseract binary is missing, extraction fails with an HTTP 422 whose message explains how to install it.
5. **Clean and format** (`cleaner.py`): normalise line endings and form feeds, strip control characters, rejoin words hyphenated across line breaks, collapse runs of spaces and blank lines, trim every line, and repair the two most common OCR digit confusions inside numeric tokens (`O` to `0`, `l`/`I` to `1`, only when adjacent to digits, so words are untouched).
6. **Save** the cleaned text, the method used (`digital` or `ocr`) and the page count on the report document. Status becomes `extracted`. Any previous analysis for that report is deleted because it no longer corresponds to the current text.
7. **Index for RAG**: the text is split into overlapping chunks (900 characters, 150 overlap, paragraph-aware) and embedded with Gemini `gemini-embedding-001` (768 dimensions), then upserted into ChromaDB under the user's collection with `report_id` metadata. This is why the flowchart's arrow from the reports collection into the RAG box exists: the vectors are derived from the saved text at this point.

### Stage 4: AI analysis (Gemini)

Files: `backend/app/services/analysis_service.py`, `backend/app/services/gemini_client.py`

1. **Fetch extracted text** from MongoDB. If the report has none, return 409 with "Run text extraction before analysis". Status becomes `analyzing`.
2. **Build the prompt**. A fixed system instruction frames the model as a careful report explainer that must not invent values and must flag out-of-range results. The user prompt lists the exact JSON keys wanted and embeds the report text between clear delimiters.
3. **Call Gemini** (`gemini-2.5-flash` by default) with `response_mime_type="application/json"` and a JSON schema (`ANALYSIS_SCHEMA`). Gemini's structured-output mode constrains the reply to that schema. Temperature is 0.2 to keep results reproducible.
4. **Parse and validate**. The reply is parsed (code fences and stray prose are tolerated), then validated with the Pydantic model `ReportAnalysis`. Status values are normalised to `low | normal | high | abnormal | unknown`, urgency to `routine | soon | urgent | unknown`, and a safety disclaimer is inserted if the model omitted it.
5. **Store** the validated analysis together with the raw model response and the model name in the `analyses` collection (one per report; re-running replaces it). Status becomes `analyzed`.

The analysis contains: report type, a plain-language summary, one finding per measured parameter (value, printed reference range, status, explanation), abnormal flags, insights, recommendations, an urgency estimate and the disclaimer.

### Stage 5: RAG for follow-up questions

Files: `backend/app/services/rag/*`

1. **User asks a question** on a specific report.
2. **Ensure the index exists**. If the ChromaDB store has no vectors for the report but MongoDB still has the text (for example after the `chroma_db` folder was deleted), the report is re-chunked and re-embedded on the spot.
3. **Retrieve**: the question is embedded with the same Gemini embedding model and ChromaDB returns the top 5 nearest chunks by cosine distance, filtered to this user's collection and this `report_id`.
4. **Generate**: the retrieved chunks are numbered `[1]..[k]` and placed before the question. A system instruction tells Gemini to answer only from those excerpts, cite them with `[n]`, say when the answer is not in the report, and never diagnose or prescribe.
5. **Return and store**: the answer, the source chunks (with their similarity scores) and the model name are saved in `qa_history` and returned. The UI shows the answer and lets the reader expand the exact passages used.

### Stage 6: View results (Next.js)

Files: `frontend/app/*`, `frontend/components/*`

- **Dashboard**: list of the user's reports with status, extraction method, page count and size; upload panel with drag-and-drop.
- **Report page**: a pipeline rail mirroring the flowchart (Upload, Extract text, AI analysis, Ask) that fills as stages complete, plus three tabs. *AI analysis* renders the findings as a ruled sheet with a coloured status bar per row and the summary, insights, recommendations and urgency. *Extracted text* shows the exact cleaned text the AI read. *Ask a question* holds the Q&A history, suggested questions and expandable source passages.
- Authentication state lives in a React context; the JWT is kept in `localStorage` and attached to every API call by `lib/api.ts`.

## 6. API reference

All routes are prefixed with `/api`. Report routes require `Authorization: Bearer <token>`.

| Method | Path | Purpose | Success | Notable errors |
|---|---|---|---|---|
| POST | `/auth/register` | create account, returns token + user | 201 | 409 email taken, 422 invalid body |
| POST | `/auth/login` | returns token + user | 200 | 401 bad credentials |
| GET | `/auth/me` | current user | 200 | 401 |
| POST | `/reports/upload` | multipart `file` | 201 | 415 type, 413 size, 400 empty |
| GET | `/reports` | list own reports (without text) | 200 | |
| GET | `/reports/{id}` | one report incl. extracted text | 200 | 404 |
| DELETE | `/reports/{id}` | delete file, report, analysis, Q&A, vectors | 204 | 404 |
| POST | `/reports/{id}/extract` | run OCR pipeline + index | 200 | 422 extraction failed (e.g. Tesseract missing), 410 file gone |
| POST | `/reports/{id}/analyze` | run Gemini analysis | 200 | 409 not extracted, 502 Gemini error, 503 key missing |
| GET | `/reports/{id}/analysis` | stored analysis | 200 | 404 none yet |
| POST | `/reports/{id}/ask` | `{ "question": "..." }` | 200 | 409 not indexed, 502 Gemini error |
| GET | `/reports/{id}/qa` | question/answer history | 200 | |
| GET | `/health` | liveness | 200 | |

OpenAPI docs: http://localhost:8000/docs

## 7. Data stored in MongoDB and ChromaDB

**MongoDB** database `medisense` (configurable):

| Collection | Key fields | Indexes |
|---|---|---|
| `users` | name, email, password_hash, created_at | unique `email` |
| `reports` | user_id, original_filename, stored_filename, content_type, size_bytes, status, extracted_text, extraction_method, page_count, chunk_count, error, created_at, updated_at | `(user_id, created_at)` |
| `analyses` | report_id, user_id, model, analysis (validated object), raw_response, created_at | unique `report_id` |
| `qa_history` | report_id, user_id, question, answer, sources[], model, created_at | `(report_id, created_at)` |

**ChromaDB** (persistent, `backend/chroma_db`): one collection per user named `user_<id>`, cosine space. Each vector's ID is `<report_id>:<chunk_index>` with metadata `{report_id, chunk_index}` and the chunk text as the document.

**Disk**: `backend/uploads/<uuid>.<ext>` holds the original files.

## 8. Running the tests

```bash
cd backend
.venv\Scripts\activate           # or source .venv/bin/activate
pytest
```

55 tests run in about ten seconds and need **no** MongoDB, Gemini key or Tesseract:

- MongoDB is replaced by an in-memory implementation (`mongomock-motor`).
- Gemini is replaced at the dependency boundary by a fake that returns fixed JSON and deterministic embeddings.
- ChromaDB, PyMuPDF, OpenCV preprocessing and the cleaning rules run for real.
- The one Tesseract call is stubbed in a single test so routing, preprocessing and cleaning are still exercised.

Coverage by area: JWT and password hashing, text cleaning rules, digital-vs-scanned detection on generated PDFs, chunking, image preprocessing, analysis prompt and JSON parsing, ChromaDB indexing and scoped retrieval, RAG prompt, and the complete HTTP flow register, upload, extract, analyze, ask, history, delete, including cross-user isolation.

Frontend: `npm run build` type-checks and compiles all routes.

## 9. Configuration reference

All backend settings live in `backend/.env` (see `.env.example`).

| Variable | Default | Meaning |
|---|---|---|
| `GEMINI_API_KEY` | (required) | Google AI Studio key |
| `GEMINI_MODEL` | `gemini-2.5-flash` | analysis and Q&A model |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-001` | embedding model for RAG |
| `MONGODB_URI` | `mongodb://localhost:27017` | connection string |
| `MONGODB_DB` | `medisense` | database name |
| `JWT_SECRET` | (required) | HS256 signing secret, 32+ chars |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | token lifetime |
| `TESSERACT_CMD` | empty | absolute path to tesseract binary if not on PATH |
| `OCR_DPI` | `300` | rasterisation DPI for scanned PDFs |
| `MIN_CHARS_PER_PAGE_FOR_DIGITAL` | `40` | digital-PDF detection threshold |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `900` / `150` | RAG chunking, in characters |
| `RAG_TOP_K` | `5` | chunks retrieved per question |
| `MAX_UPLOAD_MB` | `25` | upload size limit |
| `UPLOAD_DIR` / `CHROMA_DIR` | `uploads` / `chroma_db` | storage folders |
| `FRONTEND_ORIGIN` | `http://localhost:3000` | CORS allow-list, comma-separated |

Frontend: `NEXT_PUBLIC_API_URL` in `frontend/.env.local`.

## 10. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Backend exits with "Cannot reach MongoDB" | Start `mongod`, or point `MONGODB_URI` at Atlas and allow your IP there. |
| 503 "GEMINI_API_KEY is not set" on analyze or ask | Paste the key into `backend/.env` and restart uvicorn. |
| 422 "Tesseract OCR binary was not found" | Install Tesseract and set `TESSERACT_CMD` or add it to PATH. Digital PDFs still work without it. |
| Extraction says `ocr` for a PDF you expected to be digital | The PDF has fewer than 40 text characters per page on most pages, so it was treated as a scan. Lower `MIN_CHARS_PER_PAGE_FOR_DIGITAL` if your reports are very short. |
| Poor OCR quality | Upload at higher resolution, raise `OCR_DPI` to 400, and make sure the photo is flat and evenly lit. |
| Frontend shows "Could not reach the server" | Backend is not running on the URL in `NEXT_PUBLIC_API_URL`, or CORS origin differs from `FRONTEND_ORIGIN`. |
| 502 from analyze | Gemini returned an empty or non-JSON response; check the uvicorn log. Re-running usually succeeds. |

## 11. Evaluation notes for research use

Points that may be useful when writing up the system:

- **Deterministic preprocessing** and a fixed low temperature (0.2) make analyses reproducible enough to compare across runs.
- **Structured output** via a JSON schema removes free-text parsing failures and yields a table (`findings`) that can be scored against ground truth per parameter.
- **Grounded Q&A** stores the retrieved chunks with each answer, so faithfulness (does the answer appear in the cited chunks?) can be evaluated offline from the `qa_history` collection.
- **Extraction method is recorded** per report (`digital` vs `ocr`), so accuracy can be broken down by input modality.
- The raw model output is preserved in `analyses.raw_response` for auditing.
- Suggested metrics: OCR character error rate against transcribed reports; precision/recall of abnormal flags; answer faithfulness and citation accuracy; end-to-end latency per stage (timestamps are on each document).

## 12. Limitations and safety

- MediSense AI **explains** reports; it does not diagnose or treat. Every analysis carries a disclaimer and the UI repeats it.
- Model output can be wrong. The extracted text is always shown so the reader can verify what the model saw.
- Only English OCR is configured. Add Tesseract language packs and change `lang` in `scanned.py` for others.
- Files are stored unencrypted on the server's disk; deploy behind HTTPS and on encrypted storage for real patient data, and review local regulations (HIPAA, GDPR) before any clinical use.
- The JWT lives in `localStorage` for simplicity; a production deployment should move it to an HttpOnly cookie.
