# Decision log

Every major choice made while building MediSense AI, with the alternatives considered and the reason for the pick. Entries are numbered in the order the decisions were taken. Dates are the day of implementation (2026-09-09).

---

## D1. Python + FastAPI for the backend

**Options**: Node/Express (same language as the Next.js frontend); Django; FastAPI.

**Decision**: FastAPI.

**Why**: every processing stage in the flowchart has its strongest, first-party library in Python: PyMuPDF for PDFs, pytesseract for Tesseract, OpenCV for image preprocessing, ChromaDB (a Python-native vector store) and the official `google-genai` SDK. A Node backend would have needed child processes or weaker ports for OCR and Chroma. FastAPI over Django because the service is a thin API with no server-rendered pages, and FastAPI's dependency injection made the Gemini, Mongo and Chroma boundaries trivially replaceable in tests (see D12).

## D2. MongoDB via Motor (async driver)

**Options**: PyMongo (sync) inside FastAPI; Motor (async); an ORM layer such as Beanie/ODMantic.

**Decision**: Motor with plain dictionaries and Pydantic response models.

**Why**: the flowchart fixes MongoDB. Motor keeps the event loop free during I/O. An ODM was skipped because the four collections are simple and the extra layer would hide the exact documents stored, which the README needs to describe precisely for the paper.

## D3. JWT (HS256) with bcrypt password hashing

**Options**: server-side sessions; JWT HS256; JWT RS256; passlib vs. the `bcrypt` package directly.

**Decision**: stateless HS256 JWTs signed with one secret, 24-hour expiry, bcrypt via the `bcrypt` package.

**Why**: the flowchart specifies "Generate JWT Token". HS256 is sufficient for a single-service deployment; RS256 only pays off when several services must verify tokens without sharing a secret. `bcrypt` is used directly because `passlib` is unmaintained and breaks with bcrypt 4.x on Python 3.13. The `sub` claim holds the MongoDB user id so no extra lookup table is needed.

## D4. Digital-vs-scanned detection by counting text-layer characters per page

**Options**: trust the file extension; check whether pages contain images; count extractable characters.

**Decision**: PyMuPDF extracts text per page; a page with at least 40 non-whitespace characters is "digital"; the PDF is digital if at least half its pages qualify. The threshold is configurable.

**Why**: image presence is a poor signal (digital reports embed logos; scans sometimes carry an OCR layer). Character count directly measures what the digital branch would produce. The majority rule protects against scanned reports that start with a digital cover page. A test fixture initially had only 26 characters and was misrouted, which confirmed the threshold does what it should and led to realistic fixtures rather than lowering the threshold.

## D5. PyMuPDF renders scanned pages (no Poppler / pdf2image)

**Options**: pdf2image + Poppler; PyMuPDF `get_pixmap`.

**Decision**: PyMuPDF rasterises pages at 300 DPI.

**Why**: it removes a native dependency that is painful to install on Windows, and PyMuPDF is already present for the digital branch. One library handles both branches.

## D6. OpenCV preprocessing chain: grayscale, upscale, bilateral + median denoise, Otsu threshold

**Options**: feed raw images to Tesseract; adaptive (Gaussian) threshold; deskewing.

**Decision**: fixed chain ending in Otsu's global threshold, with upscaling to at least 1200 px width.

**Why**: Tesseract's accuracy on printed lab tables improves most from resolution and clean binarisation. Otsu is deterministic and parameter-free, which suits reproducible experiments. Adaptive thresholding was rejected as the default because it amplifies paper texture on flat, evenly lit scans; it can be added as an option later. Deskewing was left out for now (YAGNI) since most uploads are scanner output, not skewed photos.

## D7. Tesseract configuration `--oem 3 --psm 6`, English only

**Decision**: LSTM engine, page-segmentation mode 6 ("assume a single uniform block of text").

**Why**: mode 6 keeps table rows together and reads left-to-right across columns, which preserves "parameter value range" ordering. Automatic layout analysis (psm 3) often splits columns into separate blocks and scrambles row associations. Language packs beyond English are a configuration change, not a code change.

## D8. Deterministic text cleaning, including digit-only OCR corrections

**Decision**: normalise whitespace and line endings, rejoin hyphenated line breaks, strip control characters, and replace `O`/`o` with `0` and `l`/`I` with `1` only when the character sits next to digits.

**Why**: these two confusions are the most frequent in numeric lab values and are unambiguous inside a number. Broader spell-correction was rejected because it risks altering drug names and abbreviations. The rules are pure functions with tests so their effect can be quantified.

## D9. Gemini 2.5 Flash with structured JSON output and a schema

**Options**: free-text summary; ask for JSON in the prompt only; use `response_schema` (constrained decoding).

**Decision**: `response_mime_type="application/json"` plus a JSON schema, temperature 0.2, then Pydantic validation.

**Why**: the flowchart calls for "Analysis / Insights / Summary" to be stored. A schema turns the model output into a table that can be scored per parameter, which matters for evaluation. Flash was picked over Pro for latency and cost; the model name is a setting so it can be swapped for a comparison study. Pydantic validation is kept even with constrained decoding because it normalises casing and inserts the disclaimer if missing.

## D10. Gemini embeddings for RAG instead of a local embedding model

**Options**: `sentence-transformers` (local, needs PyTorch, roughly 500 MB); OpenAI embeddings (second vendor and key); Gemini `gemini-embedding-001`.

**Decision**: Gemini embeddings at 768 dimensions.

**Why**: one vendor, one key, no PyTorch install, and strong multilingual quality. The cost is a network call during extraction; the store abstraction accepts any `embed(texts)` function so a local model can be dropped in without touching callers.

## D11. ChromaDB persistent client, one collection per user, `report_id` metadata filter

**Options**: one global collection with metadata filters; one collection per report; per-user collections.

**Decision**: per-user collections with `report_id` in metadata; cosine distance.

**Why**: per-user collections give a hard isolation boundary in the vector store to match the MongoDB ownership rule. Per-report collections would create thousands of tiny collections. A single global collection would rely solely on filters for privacy. Vectors carry ids `<report_id>:<chunk>` so re-indexing can delete and replace exactly one report's chunks.

## D12. Inject external dependencies (Mongo, Gemini, Chroma) through FastAPI `Depends`

**Decision**: `get_db`, `get_gemini`, `get_vector_store` are dependencies overridden in tests; services take `generate` and `embed` callables.

**Why**: this is what makes the 55-test suite run in about ten seconds with no MongoDB, no API key and no Tesseract, while still exercising the real HTTP layer, real ChromaDB and the real OCR code paths. It also keeps `gemini_client.py` the single module aware of the vendor SDK.

## D13. Index for RAG at extraction time, with lazy re-indexing on first question

**Options**: index only when the first question arrives; index at extraction.

**Decision**: chunk and embed immediately after text is saved (matching the flowchart's arrow from the reports collection into RAG), and re-index lazily if the vector store is empty for a report.

**Why**: the first question then answers without an embedding delay, and the lazy path makes the `chroma_db` folder disposable: MongoDB remains the source of truth, vectors are a derived cache.

## D14. Paragraph-aware chunking, 900 characters with 150 overlap

**Decision**: pack whole paragraphs up to the limit, and only slide a word window with overlap inside oversized paragraphs.

**Why**: lab reports are naturally sectioned; keeping a section together keeps a parameter with its reference range. Overlap prevents an answer from being cut at a boundary. Character-based sizes were chosen over token counts to avoid a tokenizer dependency; 900 characters is roughly 200 tokens, comfortably small for top-5 retrieval.

## D15. Store Q&A history in its own collection with the retrieved sources

**Decision**: a `qa_history` collection (not in the original flowchart) holding question, answer, source chunks with scores, and model name.

**Why**: the UI needs to show prior questions when a report is reopened, and storing sources with each answer allows faithfulness evaluation offline. This is the only addition beyond the flowchart's collections and is documented as such.

## D16. Re-extraction invalidates the analysis; re-analysis replaces the previous one

**Decision**: `analyses` has a unique index on `report_id`; extracting again deletes the old analysis.

**Why**: an analysis is a function of the extracted text. Keeping a stale analysis next to new text would be misleading. History of analyses was considered and rejected for now; the raw model response is kept for auditing.

## D17. Ownership returns 404, never 403

**Decision**: a report belonging to another user is reported as "not found".

**Why**: a 403 would confirm the id exists. Every report query is filtered by `user_id` at the database level rather than checked after fetching.

## D18. Next.js App Router, client components, JWT in `localStorage`

**Options**: server components with HttpOnly cookie sessions; client-side auth context.

**Decision**: client-rendered pages with an auth context; token in `localStorage`, attached by one API client module.

**Why**: the frontend is a pure consumer of the FastAPI service; server components would have duplicated auth plumbing across two runtimes. The trade-off (XSS exposure of the token) is recorded in the README's limitations with the recommended production fix.

## D19. Run the whole pipeline automatically after upload, with manual re-run buttons

**Decision**: the dashboard uploads, then hands off to the report page with `?run=1`, which runs extract then analyze once and shows progress on the pipeline rail.

**Why**: the flowchart describes a linear flow; users should not have to press three buttons. Manual "Re-extract" and "Re-run analysis" remain for recovery and experimentation (for example, after installing Tesseract).

## D20. Visual design: lab-paper palette, pipeline rail as the signature element

**Decision**: cool off-white ground, ink navy, one cobalt action colour, semantic status colours only (amber low, crimson high, green normal). Bricolage Grotesque for headings, IBM Plex Sans for body and numbers (tabular figures). The report page's pipeline rail mirrors the flowchart stages and fills live.

**Why**: the product's job is to make dense clinical data legible, so colour is reserved for meaning. The rail makes the architecture visible to the user and doubles as a live status indicator, which is useful in demos and in paper figures. Generic patterns (identical rounded cards, gradient accents, uppercase labels, entrance animations) were deliberately avoided.

## D21. Test-first development for all business logic

**Decision**: every module was written after a failing test: security, cleaner, PDF detection, chunker, preprocessing, extractors and pipeline, analysis parsing, vector store, Q&A, and the HTTP API.

**Why**: the pipeline has many small deterministic rules whose behaviour must be stated precisely for a research write-up; the tests are that statement. Watching each test fail first caught one real issue (the fixture-size threshold in D4) before any code depended on it.

## D22. Relaxed dependency pins

**Decision**: `requirements.txt` uses minimum versions rather than exact pins.

**Why**: exact pins for `fastapi` and `chromadb` conflicted on install day (ChromaDB pins its own FastAPI range). Minimum bounds let pip resolve a compatible set; the exact resolved set that passed the test suite is frozen in `backend/requirements.lock.txt` for a reproducibility appendix (`pip install -r requirements.lock.txt`).
