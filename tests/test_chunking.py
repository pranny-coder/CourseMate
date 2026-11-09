import pytest

from app.chunking import chunk_text


def test_empty_text():
    assert chunk_text("   ") == []


def test_short_text_single_chunk():
    assert chunk_text("one two three", max_words=10, overlap=2) == ["one two three"]


def test_overlap_between_chunks():
    text = " ".join(str(i) for i in range(30))
    chunks = chunk_text(text, max_words=10, overlap=3)
    assert chunks[0].split()[-3:] == chunks[1].split()[:3]


def test_covers_all_words_without_empty_tail():
    words = [str(i) for i in range(25)]
    chunks = chunk_text(" ".join(words), max_words=10, overlap=0)
    assert " ".join(chunks).split() == words
    assert all(c for c in chunks)


def test_invalid_params():
    with pytest.raises(ValueError):
        chunk_text("a b c", max_words=5, overlap=5)
    with pytest.raises(ValueError):
        chunk_text("a b c", max_words=0)
