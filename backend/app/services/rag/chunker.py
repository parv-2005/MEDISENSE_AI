"""Split extracted report text into overlapping chunks for the vector store."""
import re

_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")
    text = (text or "").strip()
    if not text:
        return []

    # First pass: greedy packing of paragraphs so chunks respect natural boundaries.
    paragraphs = [p.strip() for p in _PARAGRAPH_SPLIT.split(text) if p.strip()]
    packed: list[str] = []
    current = ""
    for para in paragraphs:
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                packed.append(current)
            current = para
    if current:
        packed.append(current)

    # Second pass: any paragraph longer than chunk_size is sliced by words with overlap.
    chunks: list[str] = []
    for block in packed:
        if len(block) <= chunk_size:
            chunks.append(block)
        else:
            chunks.extend(_slide_window(block, chunk_size, overlap))
    return chunks


def _slide_window(block: str, chunk_size: int, overlap: int) -> list[str]:
    words = block.split()
    out: list[str] = []
    start = 0
    while start < len(words):
        end = start
        length = 0
        while end < len(words) and length + len(words[end]) + (1 if length else 0) <= chunk_size:
            length += len(words[end]) + (1 if length else 0)
            end += 1
        if end == start:  # single word longer than chunk_size
            out.append(words[start][:chunk_size])
            start += 1
            continue
        out.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        # step back enough words to cover `overlap` characters
        back = end
        covered = 0
        while back > start and covered < overlap:
            back -= 1
            covered += len(words[back]) + 1
        start = max(back, start + 1)
    return out
