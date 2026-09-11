"""Stages 2-5 - Upload, OCR extraction, Gemini analysis, RAG follow-up questions."""
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import get_settings
from app.core.deps import get_current_user, to_object_id
from app.database import ANALYSES, QA_HISTORY, REPORTS, get_db
from app.models.schemas import AnalysisOut, AnswerOut, QuestionIn, ReportOut
from app.services import analysis_service, storage
from app.services.gemini_client import GeminiClient, get_gemini
from app.services.ocr.pipeline import extract_text_from_file
from app.services.rag import qa_service
from app.services.rag.chunker import chunk_text
from app.services.rag.vector_store import VectorStore, get_vector_store

router = APIRouter(prefix="/api/reports", tags=["reports"])


# ---------------------------------------------------------------- helpers
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _report_out(doc: dict, has_analysis: bool = False) -> ReportOut:
    return ReportOut(
        id=str(doc["_id"]),
        user_id=str(doc["user_id"]),
        original_filename=doc["original_filename"],
        stored_filename=doc["stored_filename"],
        content_type=doc["content_type"],
        size_bytes=doc["size_bytes"],
        status=doc["status"],
        extraction_method=doc.get("extraction_method"),
        page_count=doc.get("page_count"),
        extracted_text=doc.get("extracted_text"),
        has_analysis=has_analysis,
        error=doc.get("error"),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


def _analysis_out(doc: dict) -> AnalysisOut:
    return AnalysisOut(
        id=str(doc["_id"]), report_id=str(doc["report_id"]), user_id=str(doc["user_id"]),
        model=doc["model"], analysis=doc["analysis"], created_at=doc["created_at"],
    )


def _answer_out(doc: dict) -> AnswerOut:
    return AnswerOut(
        id=str(doc["_id"]), report_id=str(doc["report_id"]), question=doc["question"], answer=doc["answer"],
        sources=doc["sources"], model=doc["model"], created_at=doc["created_at"],
    )


async def _owned_report(report_id: str, user: dict, db: AsyncIOMotorDatabase) -> dict:
    doc = await db[REPORTS].find_one({"_id": to_object_id(report_id), "user_id": user["_id"]})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return doc


async def _set_status(db, report_id, status_value: str, **fields):
    await db[REPORTS].update_one(
        {"_id": report_id}, {"$set": {"status": status_value, "updated_at": _now(), **fields}}
    )


async def _has_analysis(db, report_id) -> bool:
    return await db[ANALYSES].count_documents({"report_id": report_id}, limit=1) > 0


# ---------------------------------------------------------------- Stage 2: upload
@router.post("/upload", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
async def upload_report(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    try:
        stored_name, _, size = await storage.save_upload(file)
    except storage.StorageError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    now = _now()
    doc = {
        "user_id": user["_id"],
        "original_filename": file.filename or stored_name,
        "stored_filename": stored_name,
        "content_type": (file.content_type or "").lower(),
        "size_bytes": size,
        "status": "uploaded",
        "created_at": now,
        "updated_at": now,
    }
    result = await db[REPORTS].insert_one(doc)
    doc["_id"] = result.inserted_id
    return _report_out(doc)


@router.get("", response_model=list[ReportOut])
async def list_reports(user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    cursor = db[REPORTS].find({"user_id": user["_id"]}, {"extracted_text": 0}).sort("created_at", -1)
    docs = await cursor.to_list(length=200)
    analysed = {a["report_id"] async for a in db[ANALYSES].find({"user_id": user["_id"]}, {"report_id": 1})}
    return [_report_out(d, has_analysis=d["_id"] in analysed) for d in docs]


@router.get("/{report_id}", response_model=ReportOut)
async def get_report(report_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    doc = await _owned_report(report_id, user, db)
    return _report_out(doc, has_analysis=await _has_analysis(db, doc["_id"]))


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    store: VectorStore = Depends(get_vector_store),
):
    doc = await _owned_report(report_id, user, db)
    storage.delete_stored(doc["stored_filename"])
    await db[ANALYSES].delete_many({"report_id": doc["_id"]})
    await db[QA_HISTORY].delete_many({"report_id": doc["_id"]})
    await db[REPORTS].delete_one({"_id": doc["_id"]})
    await run_in_threadpool(store.delete_report, str(user["_id"]), str(doc["_id"]))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- Stage 3: extraction
@router.post("/{report_id}/extract", response_model=ReportOut)
async def extract_report(
    report_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    store: VectorStore = Depends(get_vector_store),
):
    doc = await _owned_report(report_id, user, db)
    settings = get_settings()
    path = Path(settings.upload_dir) / doc["stored_filename"]
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Stored file is missing on the server")

    await _set_status(db, doc["_id"], "extracting", error=None)
    try:
        # OCR is CPU-bound: keep the event loop free.
        result = await run_in_threadpool(extract_text_from_file, path, doc["content_type"])
        if not result.text.strip():
            raise RuntimeError("No text could be extracted from this file.")
        chunks = chunk_text(result.text, settings.chunk_size, settings.chunk_overlap)
        await run_in_threadpool(store.index_report, str(user["_id"]), str(doc["_id"]), chunks)
    except (RuntimeError, ValueError) as exc:
        await _set_status(db, doc["_id"], "failed", error=str(exc))
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    await _set_status(
        db, doc["_id"], "extracted",
        extracted_text=result.text, extraction_method=result.method, page_count=result.page_count,
        chunk_count=len(chunks),
    )
    # A re-extraction invalidates any previous analysis.
    await db[ANALYSES].delete_many({"report_id": doc["_id"]})
    fresh = await db[REPORTS].find_one({"_id": doc["_id"]})
    return _report_out(fresh)


# ---------------------------------------------------------------- Stage 4: Gemini analysis
@router.post("/{report_id}/analyze", response_model=AnalysisOut)
async def analyze_report(
    report_id: str,
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    gemini: GeminiClient = Depends(get_gemini),
):
    doc = await _owned_report(report_id, user, db)
    text = doc.get("extracted_text") or ""
    if not text.strip():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Run text extraction before analysis")

    await _set_status(db, doc["_id"], "analyzing", error=None)

    def generate(prompt: str) -> str:
        return gemini.generate_text(
            prompt, system_instruction=analysis_service.SYSTEM_INSTRUCTION, json_schema=analysis_service.ANALYSIS_SCHEMA
        )

    try:
        analysis, raw = await run_in_threadpool(analysis_service.analyze_report, text, generate)
    except (analysis_service.AnalysisError, RuntimeError) as exc:
        await _set_status(db, doc["_id"], "extracted", error=str(exc))
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    record = {
        "report_id": doc["_id"],
        "user_id": user["_id"],
        "model": gemini.model_name,
        "analysis": analysis.model_dump(),
        "raw_response": raw,
        "created_at": _now(),
    }
    await db[ANALYSES].delete_many({"report_id": doc["_id"]})
    result = await db[ANALYSES].insert_one(record)
    record["_id"] = result.inserted_id
    await _set_status(db, doc["_id"], "analyzed")
    return _analysis_out(record)


@router.get("/{report_id}/analysis", response_model=AnalysisOut)
async def get_analysis(report_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    doc = await _owned_report(report_id, user, db)
    record = await db[ANALYSES].find_one({"report_id": doc["_id"]})
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No analysis yet for this report")
    return _analysis_out(record)


# ---------------------------------------------------------------- Stage 5: RAG Q&A
@router.post("/{report_id}/ask", response_model=AnswerOut)
async def ask_question(
    report_id: str,
    payload: QuestionIn,
    user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
    gemini: GeminiClient = Depends(get_gemini),
    store: VectorStore = Depends(get_vector_store),
):
    doc = await _owned_report(report_id, user, db)
    settings = get_settings()
    uid, rid = str(user["_id"]), str(doc["_id"])

    # Lazily (re)build the index if the vector store was wiped but Mongo still has the text.
    text = doc.get("extracted_text") or ""
    if text.strip() and not await run_in_threadpool(store.has_index, uid, rid):
        chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)
        await run_in_threadpool(store.index_report, uid, rid, chunks)

    def generate(prompt: str) -> str:
        return gemini.generate_text(prompt, system_instruction=qa_service.QA_SYSTEM_INSTRUCTION)

    try:
        answer, sources = await run_in_threadpool(
            qa_service.answer_question, store, uid, rid, payload.question.strip(), generate, settings.rag_top_k
        )
    except qa_service.RAGError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    record = {
        "report_id": doc["_id"],
        "user_id": user["_id"],
        "question": payload.question.strip(),
        "answer": answer,
        "sources": [s.model_dump() for s in sources],
        "model": gemini.model_name,
        "created_at": _now(),
    }
    result = await db[QA_HISTORY].insert_one(record)
    record["_id"] = result.inserted_id
    return _answer_out(record)


@router.get("/{report_id}/qa", response_model=list[AnswerOut])
async def qa_history(report_id: str, user: dict = Depends(get_current_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    doc = await _owned_report(report_id, user, db)
    docs = await db[QA_HISTORY].find({"report_id": doc["_id"]}).sort("created_at", 1).to_list(length=500)
    return [_answer_out(d) for d in docs]
