CHUNK_SIZE_CHARS = 2000
CHUNK_OVERLAP_CHARS = 200


def estimate_token_count(text: str) -> int:
    return max(1, len(text) // 4)


def chunk_text(text: str) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []

    chunks: list[str] = []
    start = 0
    length = len(cleaned)

    while start < length:
        end = min(start + CHUNK_SIZE_CHARS, length)
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start = max(end - CHUNK_OVERLAP_CHARS, start + 1)

    return chunks
