from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv
from google import genai

from .db import ensure_db, get_conn

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None  # type: ignore

# Setup
BASE_DIR = Path(__file__).resolve().parents[2]
PDF_DIR = BASE_DIR / "iceland_data_pdf"
load_dotenv(BASE_DIR / ".env")

API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=API_KEY) if API_KEY else None

EMBED_MODEL = "models/gemini-embedding-001"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def extract_pdf_text(path: Path) -> str:
    if PdfReader is None:
        return "[pypdf not installed, cannot parse PDF]"
    try:
        reader = PdfReader(str(path))
        chunks: list[str] = []
        for page in reader.pages:
            text = page.extract_text() or ""
            chunks.append(text.strip())
        return "\n\n".join([c for c in chunks if c])
    except Exception:
        return "[failed to parse PDF]"


def split_chunks(text: str, chunk_size: int = 600, overlap: int = 100) -> list[str]:
    """Simple chunking with overlap."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        if end >= len(text):
            break
        start += chunk_size - overlap
    return chunks


def get_embedding(text: str) -> list[float]:
    if not client:
        return [0.0] * 768
    try:
        res = client.models.embed_content(model=EMBED_MODEL, contents=text)
        return res.embeddings[0].values
    except Exception as e:
        print(f"Embedding error: {e}")
        return [0.0] * 768


def rebuild_knowledge_index() -> dict[str, int]:
    ensure_db()
    indexed_files = 0
    total_chunks = 0
    with get_conn() as conn:
        for pdf_path in sorted(PDF_DIR.glob("*.pdf")):
            # Check if updated
            row = conn.execute("SELECT id, updated_at FROM docs WHERE path=?", (str(pdf_path),)).fetchone()
            # For simplicity in lab, we always rebuild or skip if same timestamp.
            # But here let's just clear and rebuild for the specific file if we want accuracy.
            
            content = extract_pdf_text(pdf_path)
            if not content.strip():
                continue

            # Upsert doc
            conn.execute(
                """
                INSERT INTO docs(path, title, content, updated_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    title=excluded.title,
                    content=excluded.content,
                    updated_at=excluded.updated_at
                """,
                (str(pdf_path), pdf_path.name, content, now_iso()),
            )
            doc_id = conn.execute("SELECT id FROM docs WHERE path=?", (str(pdf_path),)).fetchone()["id"]

            # Clear old chunks
            conn.execute("DELETE FROM doc_chunks WHERE doc_id=?", (doc_id,))

            # Generate chunks and embeddings
            chunks = split_chunks(content)
            for i, chunk_text in enumerate(chunks):
                emb = get_embedding(chunk_text)
                emb_blob = np.array(emb, dtype=np.float32).tobytes()
                conn.execute(
                    "INSERT INTO doc_chunks(doc_id, chunk_index, content, embedding) VALUES(?, ?, ?, ?)",
                    (doc_id, i, chunk_text, emb_blob),
                )
                total_chunks += 1
            
            indexed_files += 1
        conn.commit()
    return {"files": indexed_files, "chunks": total_chunks}


def index_file(pdf_path: Path) -> dict[str, int]:
    ensure_db()
    total_chunks = 0
    if not pdf_path.exists():
        return {"chunks": 0}
    
    content = extract_pdf_text(pdf_path)
    if not content.strip():
        return {"chunks": 0}

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO docs(path, title, content, updated_at)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
                title=excluded.title,
                content=excluded.content,
                updated_at=excluded.updated_at
            """,
            (str(pdf_path), pdf_path.name, content, now_iso()),
        )
        doc_id = conn.execute("SELECT id FROM docs WHERE path=?", (str(pdf_path),)).fetchone()["id"]
        conn.execute("DELETE FROM doc_chunks WHERE doc_id=?", (doc_id,))

        chunks = split_chunks(content)
        for i, chunk_text in enumerate(chunks):
            emb = get_embedding(chunk_text)
            emb_blob = np.array(emb, dtype=np.float32).tobytes()
            conn.execute(
                "INSERT INTO doc_chunks(doc_id, chunk_index, content, embedding) VALUES(?, ?, ?, ?)",
                (doc_id, i, chunk_text, emb_blob),
            )
            total_chunks += 1
        conn.commit()
    return {"chunks": total_chunks}


def list_docs() -> list[str]:
    return [p.name for p in sorted(PDF_DIR.glob("*.pdf"))]


def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    mag1 = np.linalg.norm(v1)
    mag2 = np.linalg.norm(v2)
    if mag1 == 0 or mag2 == 0:
        return 0
    return np.dot(v1, v2) / (mag1 * mag2)


def search_knowledge(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    ensure_db()
    if not client:
        return [{"title": "Error", "snippet": "Gemini API key not configured", "score": 0}]

    query_emb = np.array(get_embedding(query), dtype=np.float32)
    results = []

    with get_conn() as conn:
        cursor = conn.execute(
            """
            SELECT d.title, c.content, c.embedding 
            FROM doc_chunks c
            JOIN docs d ON c.doc_id = d.id
            """
        )
        for row in cursor:
            if not row["embedding"]:
                continue
            chunk_emb = np.frombuffer(row["embedding"], dtype=np.float32)
            score = float(cosine_similarity(query_emb, chunk_emb))
            if score > 0.3:  # Threshold
                results.append(
                    {"title": row["title"], "snippet": row["content"], "score": score}
                )

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]
