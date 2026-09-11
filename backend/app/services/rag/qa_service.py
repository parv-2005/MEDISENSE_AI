"""RAG question answering: retrieve relevant chunks, then ask Gemini with that context."""
from typing import Callable

from app.models.schemas import SourceChunk
from app.services.rag.vector_store import VectorStore

Generator = Callable[[str], str]


class RAGError(Exception):
    pass


QA_SYSTEM_INSTRUCTION = (
    "You are MediSense AI, answering a patient's follow-up questions about their own medical report. "
    "Answer ONLY from the provided context excerpts. If the context does not contain the answer, say so "
    "plainly and suggest asking their clinician. Cite the excerpt numbers you used like [1], [2]. "
    "Use plain language, keep it under 200 words, and never give a diagnosis or prescribe treatment."
)


def build_qa_prompt(question: str, context_chunks: list[str]) -> str:
    numbered = "\n\n".join(f"[{i + 1}] {chunk}" for i, chunk in enumerate(context_chunks))
    return (
        "Context excerpts from the patient's medical report:\n\n"
        f"{numbered}\n\n"
        f"Patient question: {question}\n\n"
        "Answer using only the excerpts above and cite them with [n]."
    )


def answer_question(
    store: VectorStore,
    user_id: str,
    report_id: str,
    question: str,
    generate: Generator,
    top_k: int = 5,
) -> tuple[str, list[SourceChunk]]:
    hits = store.query(user_id=user_id, report_id=report_id, question=question, top_k=top_k)
    if not hits:
        raise RAGError("This report has not been indexed yet. Run text extraction first.")
    prompt = build_qa_prompt(question, [h.text for h in hits])
    answer = generate(prompt).strip()
    sources = [SourceChunk(chunk_index=h.chunk_index, text=h.text, score=h.score) for h in hits]
    return answer, sources
