# MediSense AI architecture

This document describes how the system is put together: the runtime components, the modules inside each, the data that flows between them, and the exact sequence of operations for every user action. It follows the six stages of the working flowchart.

## 1. System context

```
┌────────────┐   HTTPS/JSON    ┌──────────────────────┐   driver    ┌────────────┐
│  Browser   │ ─────────────▶  │  FastAPI backend     │ ──────────▶ │  MongoDB   │
│  Next.js   │ ◀─────────────  │  (Python, Uvicorn)   │ ◀────────── │  users     │
│  dashboard │                 │                      │             │  reports   │
└────────────┘                 │  ┌────────────────┐  │             │  analyses  │
                               │  │ OCR pipeline   │  │             │  qa_history│
                               │  │ PyMuPDF        │  │             └────────────┘
                               │  │ OpenCV         │  │
                               │  │ Tesseract ─────┼──┼──▶ local binary
                               │  └────────────────┘  │
                               │  ┌────────────────┐  │   embedded   ┌────────────┐
                               │  │ RAG            │──┼────────────▶ │ ChromaDB   │
                               │  │ chunk/embed/   │  │              │ (on disk)  │
                               │  │ retrieve       │  │              └────────────┘
                               │  └────────────────┘  │
                               │  ┌────────────────┐  │   HTTPS      ┌────────────┐
                               │  │ Gemini client  │──┼────────────▶ │ Google     │
                               │  └────────────────┘  │              │ Gemini API │
                               │  uploads/ (files)    │              └────────────┘
                               └──────────────────────┘
```

Three processes run locally: the Next.js server (port 3000), the FastAPI server (port 8000) and MongoDB (port 27017). ChromaDB runs embedded inside the FastAPI process and persists to `backend/chroma_db`. Tesseract is invoked as a subprocess by `pytesseract`. Gemini is the only remote API.

## 2. Backend modules and responsibilities

| Module | Responsibility | Depends on |
|---|---|---|
| `app/main.py` | builds the FastAPI app, CORS, lifespan (connect Mongo, ensure indexes, create folders) | config, database, routers |
| `app/config.py` | typed settings from `.env` (`pydantic-settings`), cached | |
| `app/database.py` | Motor client factory, collection names, index creation, `get_db` dependency | config |
| `app/core/security.py` | bcrypt hashing, JWT create/decode, `TokenError` | config |
| `app/core/deps.py` | `get_current_user` (Bearer token to user document), `to_object_id` | security, database |
| `app/models/schemas.py` | Pydantic models for requests and responses, including `ReportAnalysis` with normalising validators | |
| `app/routers/auth.py` | register, login, me | security, database |
| `app/routers/reports.py` | upload, list, get, delete, extract, analyze, get analysis, ask, Q&A history | storage, ocr.pipeline, analysis_service, rag.*, gemini_client |
| `app/services/storage.py` | validates MIME type and size, streams the upload to `uploads/<uuid>.<ext>` | config, ocr.pipeline (for the supported-type set) |
| `app/services/ocr/pdf_detect.py` | digital-vs-scanned decision | PyMuPDF |
| `app/services/ocr/digital.py` | text layer extraction per page | PyMuPDF |
| `app/services/ocr/scanned.py` | rasterise PDF pages, run Tesseract | PyMuPDF, pytesseract, preprocess |
| `app/services/ocr/preprocess.py` | grayscale, upscale, denoise, Otsu threshold | OpenCV, NumPy, Pillow |
| `app/services/ocr/cleaner.py` | deterministic text normalisation | |
| `app/services/ocr/pipeline.py` | routes a file through the right branch, cleans, returns `ExtractionResult` | all of the above |
| `app/services/analysis_service.py` | prompt construction, JSON schema, parsing and validation of the Gemini reply | schemas |
| `app/services/gemini_client.py` | the only module importing `google.genai`; `generate_text` and `embed`; `get_gemini` dependency | config |
| `app/services/rag/chunker.py` | paragraph-aware overlapping chunking | |
| `app/services/rag/vector_store.py` | ChromaDB wrapper: index, delete, count, query; `get_vector_store` dependency | chromadb, gemini_client (for the embedder) |
| `app/services/rag/qa_service.py` | retrieve, build cited prompt, generate answer | vector_store, schemas |

Dependency direction is strictly downward: routers call services, services never import routers, and only `gemini_client.py` knows about the vendor SDK.

### Dependency injection points

Three FastAPI dependencies are the seams used by tests and available for deployment changes:

- `get_db` returns the Motor database stored on `app.state` (tests substitute an in-memory `mongomock` database).
- `get_gemini` returns a cached `GeminiClient` or raises 503 if the key is missing (tests substitute a fake with deterministic output).
- `get_vector_store` returns a process-wide `VectorStore` whose embedder is `GeminiClient.embed` (tests substitute a store with a hashing embedder).

Services below the routers accept plain callables (`generate: Callable[[str], str]`, `embed: Callable[[list[str]], list[list[float]]]`) so they are testable with no framework at all.

## 3. Data model

### MongoDB

```
users
  _id            ObjectId
  name           str
  email          str  (lower-cased, unique index)
  password_hash  str  (bcrypt)
  created_at     datetime (UTC)

reports
  _id                ObjectId
  user_id            ObjectId  -> users._id
  original_filename  str
  stored_filename    str       (uuid + extension, file under uploads/)
  content_type       str       (MIME)
  size_bytes         int
  status             "uploaded" | "extracting" | "extracted" | "analyzing" | "analyzed" | "failed"
  extracted_text     str | absent
  extraction_method  "digital" | "ocr" | absent
  page_count         int | absent
  chunk_count        int | absent
  error              str | null
  created_at, updated_at  datetime
  index: (user_id, created_at desc)

analyses
  _id           ObjectId
  report_id     ObjectId  -> reports._id   (unique index: one analysis per report)
  user_id       ObjectId
  model         str        (e.g. "gemini-2.5-flash")
  analysis      ReportAnalysis object (see below)
  raw_response  str        (exact model output, for audit)
  created_at    datetime

qa_history
  _id        ObjectId
  report_id  ObjectId
  user_id    ObjectId
  question   str
  answer     str
  sources    [{chunk_index:int, text:str, score:float|null}]
  model      str
  created_at datetime
  index: (report_id, created_at)
```

`ReportAnalysis` (validated by Pydantic before storage):

```
report_type      str
summary          str
findings[]       {parameter, value, reference_range, status: low|normal|high|abnormal|unknown, explanation}
abnormal_flags[] str
insights[]       str
recommendations[] str
urgency          routine|soon|urgent|unknown
disclaimer       str  (defaulted if the model omits it)
```

### ChromaDB

- Persistent client at `backend/chroma_db`.
- Collection per user: `user_<user_id>`, distance metric cosine.
- Vector id `"<report_id>:<chunk_index>"`, document = chunk text, metadata `{report_id, chunk_index}`, embedding = 768-dim Gemini embedding.
- ChromaDB is a derived cache. If wiped, the ask endpoint rebuilds a report's vectors from `reports.extracted_text`.

### Disk

- `backend/uploads/<uuid>.<ext>`: original files. Deleted with the report.

## 4. Request flows

### 4.1 Authentication

```
Browser                FastAPI                         MongoDB
  │ POST /auth/register  │                               │
  │─────────────────────▶│ validate body (Pydantic)      │
  │                      │ find_one({email}) ───────────▶│
  │                      │ bcrypt.hashpw(password)       │
  │                      │ insert_one(user) ────────────▶│
  │                      │ jwt.encode({sub:user_id,exp}) │
  │◀─────────────────────│ 201 {access_token, user}      │
  │                      │                               │
  │ GET /reports         │                               │
  │ Authorization: Bearer│                               │
  │─────────────────────▶│ decode token, load user ─────▶│
  │◀─────────────────────│ 200 [...] or 401              │
```

### 4.2 Upload

1. `POST /api/reports/upload` (multipart). `storage.save_upload` checks the MIME type against the supported set, streams to disk in 1 MB chunks and enforces the size limit.
2. A `reports` document is inserted with `status: "uploaded"`.
3. Response 201 with the report; the frontend navigates to `/reports/{id}?run=1`.

### 4.3 Text extraction (OCR pipeline)

```
POST /api/reports/{id}/extract
  │
  ├─ load report (owner-scoped) ; status := extracting
  │
  ├─ run_in_threadpool(extract_text_from_file(path, content_type))
  │     │
  │     ├─ content_type == application/pdf ?
  │     │     ├─ is_digital_pdf(path)      # >=40 chars on >=50% of pages
  │     │     │     yes ─▶ digital.extract_pages   (PyMuPDF get_text)
  │     │     │     no  ─▶ scanned.render_pdf_pages (PyMuPDF, 300 DPI)
  │     │     │             └─▶ for each page: preprocess_for_ocr ─▶ pytesseract.image_to_string
  │     └─ image/* ─▶ Pillow open ─▶ preprocess_for_ocr ─▶ Tesseract
  │
  │     └─ clean_text(page) for each page ; join with blank lines
  │        ▶ ExtractionResult(text, method, page_count, pages)
  │
  ├─ chunk_text(text, 900, 150)
  ├─ run_in_threadpool(store.index_report(user_id, report_id, chunks))   # Gemini embeddings -> ChromaDB
  ├─ update report: extracted_text, extraction_method, page_count, chunk_count ; status := extracted
  ├─ delete any previous analysis for this report
  └─ 200 report
     (on failure: status := failed, error saved, 422 with the reason)
```

Preprocessing detail (`preprocess_for_ocr`):

1. RGB to grayscale.
2. If width < 1200 px, cubic upscale by max(2, 1200/width).
3. Bilateral filter (d=9, sigmaColor=75, sigmaSpace=75).
4. Median blur 3x3.
5. Otsu threshold to a binary image (0/255), returned as an 8-bit grayscale PIL image.

Cleaning detail (`clean_text`): CRLF and form feed to LF; strip C0 control characters; join `word-\nword`; `O/o` to `0` and `l/I` to `1` when adjacent to digits; collapse spaces/tabs; trim lines; collapse 3+ blank lines to one.

### 4.4 AI analysis

```
POST /api/reports/{id}/analyze
  ├─ load report ; require extracted_text (else 409) ; status := analyzing
  ├─ prompt = build_analysis_prompt(extracted_text)
  ├─ Gemini.generate_content(model, prompt,
  │        system_instruction=SYSTEM_INSTRUCTION,
  │        response_mime_type="application/json",
  │        response_json_schema=ANALYSIS_SCHEMA, temperature=0.2)
  ├─ parse_analysis(raw): strip fences -> json.loads -> ReportAnalysis.model_validate
  ├─ replace analyses[report_id] with {analysis, raw_response, model}
  ├─ status := analyzed
  └─ 200 AnalysisOut
     (Gemini/parse failure: status := extracted, error saved, 502)
```

### 4.5 RAG follow-up question

```
POST /api/reports/{id}/ask  {question}
  ├─ load report
  ├─ if store has no vectors for report and text exists: re-chunk + re-index
  ├─ q_vec = Gemini.embed([question])
  ├─ hits = Chroma.query(collection=user_<uid>, where report_id, n=5, cosine)
  ├─ prompt = "[1] chunk … [k] chunk … Patient question: … cite [n]"
  ├─ answer = Gemini.generate_content(prompt, system=QA_SYSTEM_INSTRUCTION)
  ├─ insert qa_history {question, answer, sources[{chunk_index,text,score}], model}
  └─ 200 AnswerOut
```

### 4.6 Delete

`DELETE /api/reports/{id}` removes the file on disk, the report, its analysis, its Q&A history and its vectors in ChromaDB, in that order. Returns 204.

## 5. Frontend structure

```
app/layout.tsx          fonts (Bricolage Grotesque, IBM Plex Sans), AuthProvider
app/page.tsx            redirect -> /dashboard
app/login, app/register AuthCard layout with the product explanation on the left
app/dashboard           report list + upload panel (drag and drop)
app/reports/[id]        header + PipelineRail + tabs (AI analysis | Extracted text | Ask)
components/PipelineRail live flowchart: done/active/failed per stage
components/AnalysisView summary, counters, findings sheet, insights, recommendations, disclaimer
components/AskPanel     Q&A history, suggestions, source passages toggle
components/ui.tsx       Shell, Button, Input, Notice, StatusDot, colour mapping helpers
lib/api.ts              fetch wrapper: attaches JWT, normalises FastAPI error bodies, typed endpoints
lib/auth.tsx            AuthProvider, useAuth, useRequireAuth (redirects to /login)
```

State handling: the report page owns `report`, `analysis`, `working` (which stage is running) and `questionsAsked`; the rail is a pure function of those. After an upload the page arrives with `?run=1`, runs extraction then analysis exactly once, and clears the flag from the URL so a refresh does not re-run the pipeline.

## 6. Cross-cutting concerns

- **Concurrency**: OCR, embedding and Gemini calls are CPU- or network-bound and run in `run_in_threadpool`, so one slow extraction does not block other requests.
- **Errors**: every failure returns a JSON `detail` with an actionable message (for example how to install Tesseract, or that the Gemini key is missing). Report status records failures so the dashboard can show them.
- **Security**: bcrypt passwords, signed short-lived JWTs, owner-scoped queries, random stored filenames, MIME and size validation, CORS restricted to the configured frontend origin. Known gap: token in `localStorage` (see README limitations).
- **Configuration**: everything tunable is an environment variable read once through `pydantic-settings`.
- **Testing**: 55 tests; external systems replaced at the dependency seams, everything else real. See README section 8.

## 7. Deployment shape

For a single-machine deployment: run MongoDB as a service, `uvicorn app.main:app --host 0.0.0.0 --port 8000` behind a reverse proxy with HTTPS, and `npm run build && npm run start` for the frontend with `NEXT_PUBLIC_API_URL` pointing at the proxy. Persist `backend/uploads` and `backend/chroma_db` on durable storage. Horizontal scaling of the backend requires moving uploads to object storage and ChromaDB to its client-server mode; both are isolated behind `storage.py` and `vector_store.py`.
