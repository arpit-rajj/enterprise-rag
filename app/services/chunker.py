from typing import List

class CharacterTextSplitter:
    """
    A simple implementation of recursive character text splitting.
    Splits text by double newlines, then newlines, then spaces, then characters
    to keep chunks within the specified size.
    """
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = ["\n\n", "\n", " ", ""]
        
    def split_text(self, text: str) -> List[str]:
        # Very basic placeholder implementation for simplicity
        # In a real scenario, use LangChain's RecursiveCharacterTextSplitter
        # For now, we will do a simple chunking by character length to avoid adding large dependencies
        
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = min(start + self.chunk_size, text_length)
            
            # If we're not at the end, try to find a sensible break point (e.g., a space)
            if end < text_length:
                # Look back up to half the chunk size for a space or newline
                break_point = text.rfind("\n\n", max(0, end - self.chunk_size // 2), end)
                if break_point == -1:
                    break_point = text.rfind("\n", max(0, end - self.chunk_size // 2), end)
                if break_point == -1:
                    break_point = text.rfind(" ", max(0, end - self.chunk_size // 2), end)
                    
                if break_point != -1:
                    end = break_point + 1 # Include the separator
            
            chunks.append(text[start:end].strip())
            start = end - self.chunk_overlap
            
            if start < 0:
                start = 0
                
        # Filter out empty chunks
        return [c for c in chunks if len(c) > 0]
