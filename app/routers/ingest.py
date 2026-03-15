import os
import uuid
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.database import get_supabase
from app.models import SOURCES, CHUNKS
from app.services.pdf_extractor import extract_from_pdf
from app.services.embeddings import get_embedding

router = APIRouter()

UPLOAD_DIR = "pdfs"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/ingest", summary="Ingest a PDF and extract content chunks")
async def ingest_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    sb = get_supabase()

    # Prevent re-ingesting the same file
    existing = sb.table(SOURCES).select("*").eq("filename", file.filename).execute()
    if existing.data:
        src = existing.data[0]
        chunks = sb.table(CHUNKS).select("chunk_id").eq("source_id", src["source_id"]).execute()
        return {
            "message": "File already ingested. Returning existing data.",
            "source_id": src["source_id"],
            "filename": src["filename"],
            "grade": src["grade"],
            "subject": src["subject"],
            "chunks_count": len(chunks.data),
        }

    # Save upload to disk
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    source_id = f"SRC_{uuid.uuid4().hex[:6].upper()}"
    extracted = extract_from_pdf(file_path, source_id)

    # Insert source row
    sb.table(SOURCES).insert({
        "id": str(uuid.uuid4()),
        "source_id": source_id,
        "filename": extracted["filename"],
        "grade": extracted["grade"],
        "subject": extracted["subject"],
    }).execute()

    # Insert all chunks with embeddings
    chunk_rows = []
    for c in extracted["chunks"]:
        try:
            embedding = get_embedding(c["text"])
        except Exception as e:
            print(f"[ingest] Embedding failed for {c['chunk_id']}: {e}")
            embedding = None
        chunk_rows.append({
            "id": str(uuid.uuid4()),
            "chunk_id": c["chunk_id"],
            "source_id": c["source_id"],
            "grade": c["grade"],
            "subject": c["subject"],
            "topic": c["topic"],
            "text": c["text"],
            "embedding": embedding,
        })
    sb.table(CHUNKS).insert(chunk_rows).execute()

    return {
        "message": "PDF ingested successfully.",
        "source_id": source_id,
        "filename": extracted["filename"],
        "grade": extracted["grade"],
        "subject": extracted["subject"],
        "chunks_extracted": len(extracted["chunks"]),
        "sample_chunks": extracted["chunks"][:2],
    }
