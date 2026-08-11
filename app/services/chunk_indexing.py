"""Build and persist document chunks for chat retrieval."""
from app.services.chunking import build_chunks
from app.db.chunk_store import insert_chunks, delete_chunks_for_doc


async def index_document_chunks(doc_id: str, text: str, user_id: str, category: str):
    """Delete old chunks and insert fresh chunks for a document."""
    delete_chunks_for_doc(doc_id)
    chunks = build_chunks(doc_id, category, text)
    insert_chunks(chunks, user_id)
