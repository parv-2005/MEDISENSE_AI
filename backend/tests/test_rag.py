import hashlib
import math

import pytest

from app.services.rag import qa_service
from app.services.rag.vector_store import VectorStore


def fake_embed(texts: list[str]) -> list[list[float]]:
    """Deterministic bag-of-words embedding: similar words -> similar vectors. No network."""
    dim = 64
    out = []
    for t in texts:
        vec = [0.0] * dim
        for word in t.lower().split():
            h = int(hashlib.md5(word.encode()).hexdigest(), 16)
            vec[h % dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        out.append([v / norm for v in vec])
    return out


@pytest.fixture
def store(tmp_path):
    return VectorStore(persist_dir=tmp_path / "chroma", embed=fake_embed)


CHUNKS = [
    "Hemoglobin 10.2 g/dL reference 12.0-16.0 status low",
    "Cholesterol total 240 mg/dL reference below 200 status high",
    "Patient name John Doe age 45 collected 2024-01-05",
]


def test_index_then_query_returns_most_relevant_chunk_first(store):
    store.index_report(user_id="u1", report_id="r1", chunks=CHUNKS)
    hits = store.query(user_id="u1", report_id="r1", question="what is the hemoglobin value", top_k=2)
    assert len(hits) == 2
    assert hits[0].chunk_index == 0
    assert "Hemoglobin" in hits[0].text


def test_query_is_scoped_to_report_and_user(store):
    store.index_report(user_id="u1", report_id="r1", chunks=CHUNKS)
    store.index_report(user_id="u1", report_id="r2", chunks=["Vitamin D 18 ng/mL low"])
    store.index_report(user_id="u2", report_id="r1", chunks=["Other user hemoglobin 15"])
    hits = store.query(user_id="u1", report_id="r2", question="hemoglobin", top_k=5)
    assert [h.text for h in hits] == ["Vitamin D 18 ng/mL low"]


def test_reindex_replaces_old_chunks(store):
    store.index_report(user_id="u1", report_id="r1", chunks=CHUNKS)
    store.index_report(user_id="u1", report_id="r1", chunks=["Fresh text only"])
    assert store.count(user_id="u1", report_id="r1") == 1


def test_has_index_reports_presence(store):
    assert store.has_index(user_id="u1", report_id="r1") is False
    store.index_report(user_id="u1", report_id="r1", chunks=CHUNKS)
    assert store.has_index(user_id="u1", report_id="r1") is True


def test_delete_report_removes_vectors(store):
    store.index_report(user_id="u1", report_id="r1", chunks=CHUNKS)
    store.delete_report(user_id="u1", report_id="r1")
    assert store.count(user_id="u1", report_id="r1") == 0


def test_qa_prompt_contains_question_and_numbered_context():
    prompt = qa_service.build_qa_prompt("Is my cholesterol high?", [CHUNKS[1], CHUNKS[0]])
    assert "Is my cholesterol high?" in prompt
    assert "[1]" in prompt and CHUNKS[1] in prompt
    assert "[2]" in prompt and CHUNKS[0] in prompt


def test_answer_question_retrieves_then_generates(store):
    store.index_report(user_id="u1", report_id="r1", chunks=CHUNKS)
    seen = {}

    def fake_generate(prompt: str) -> str:
        seen["prompt"] = prompt
        return "Your cholesterol is 240 mg/dL, above the 200 reference. [1]"

    answer, sources = qa_service.answer_question(
        store, user_id="u1", report_id="r1", question="Is my cholesterol high?", generate=fake_generate, top_k=2
    )
    assert "240" in answer
    assert sources[0].chunk_index == 1
    assert CHUNKS[1] in seen["prompt"]


def test_answer_question_without_index_raises(store):
    with pytest.raises(qa_service.RAGError):
        qa_service.answer_question(store, user_id="u1", report_id="nope", question="hi", generate=lambda p: "x")
