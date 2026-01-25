from __future__ import annotations


def estimate_token_count(text: str) -> int:
    return max(1, len(text) // 4)


def chunk_text(text: str, max_chunk_size: int = 3000, overlap: int = 200) -> list[str]:
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + max_chunk_size, text_length)
        chunk = text[start:end]
        chunks.append(chunk)
        if end == text_length:
            break
        start = max(0, end - overlap)

    return chunks
