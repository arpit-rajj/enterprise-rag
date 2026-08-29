import pytest
from app.services.chunker import RecursiveCharacterTextSplitter

def test_chunker_basic():
    chunker = RecursiveCharacterTextSplitter(chunk_size=10, chunk_overlap=2)
    text = "This is a simple text that we want to split."
    chunks = chunker.split_text(text)
    
    assert len(chunks) > 0
    # The first chunk should be roughly chunk_size, maybe a bit more depending on word boundaries
    # Actually our simple implementation tries to split by space.
    # "This is a" = 9 chars
    assert chunks[0] == "This is a"

def test_chunker_empty():
    chunker = RecursiveCharacterTextSplitter(chunk_size=10, chunk_overlap=2)
    chunks = chunker.split_text("")
    assert len(chunks) == 0

def test_chunker_no_spaces():
    chunker = RecursiveCharacterTextSplitter(chunk_size=5, chunk_overlap=0)
    text = "abcdefghij"
    chunks = chunker.split_text(text)
    
    assert len(chunks) == 2
    assert chunks[0] == "abcde"
    assert chunks[1] == "fghij"
