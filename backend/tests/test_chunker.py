from app.services.rag.chunker import chunk_text


def test_short_text_becomes_single_chunk():
    chunks = chunk_text("Hemoglobin 13.5 g/dL", chunk_size=100, overlap=20)
    assert chunks == ["Hemoglobin 13.5 g/dL"]


def test_long_text_is_split_with_overlap():
    text = " ".join(f"word{i}" for i in range(400))  # ~2800 chars
    chunks = chunk_text(text, chunk_size=500, overlap=100)
    assert len(chunks) > 1
    assert all(len(c) <= 500 for c in chunks)
    # consecutive chunks share content (overlap) so answers spanning a boundary aren't lost
    tail = chunks[0][-50:]
    assert tail.split()[-1] in chunks[1]


def test_chunks_prefer_paragraph_boundaries():
    para_a = "Section A. " * 30
    para_b = "Section B. " * 30
    chunks = chunk_text(f"{para_a.strip()}\n\n{para_b.strip()}", chunk_size=400, overlap=0)
    assert chunks[0].startswith("Section A")
    assert not chunks[0].startswith("Section B") and any(c.startswith("Section B") for c in chunks)


def test_empty_text_yields_no_chunks():
    assert chunk_text("", chunk_size=100, overlap=10) == []
    assert chunk_text("   \n  ", chunk_size=100, overlap=10) == []


def test_overlap_must_be_smaller_than_chunk_size():
    import pytest
    with pytest.raises(ValueError):
        chunk_text("abc", chunk_size=10, overlap=10)
