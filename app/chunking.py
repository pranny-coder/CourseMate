def chunk_text(text: str, max_words: int = 120, overlap: int = 20) -> list[str]:
    """Split text into overlapping word windows.

    Overlap keeps sentences that straddle a boundary retrievable from either chunk.
    """
    if max_words <= 0:
        raise ValueError("max_words must be positive")
    if overlap < 0 or overlap >= max_words:
        raise ValueError("overlap must be >= 0 and < max_words")

    words = text.split()
    if not words:
        return []

    step = max_words - overlap
    chunks = []
    for start in range(0, len(words), step):
        chunks.append(" ".join(words[start : start + max_words]))
        if start + max_words >= len(words):
            break
    return chunks
