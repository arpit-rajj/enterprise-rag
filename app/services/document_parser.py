import PyPDF2
from app.core.logging import logger

def parse_document(file_path: str) -> str:
    """
    Extracts text from a given document path (PDF or TXT).
    """
    if file_path.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    
    elif file_path.endswith(".pdf"):
        text = ""
        try:
            with open(file_path, "rb") as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF {file_path}: {e}")
            raise ValueError(f"Failed to extract text from PDF: {e}")
            
    else:
        raise ValueError("Unsupported file format for extraction")
