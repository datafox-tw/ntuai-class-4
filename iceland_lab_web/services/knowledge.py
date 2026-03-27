from __future__ import annotations

import re
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any

from .db import ensure_db, get_conn

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None  # type: ignore

BASE_DIR = Path(__file__).resolve().parents[2]
PDF_DIR = BASE_DIR / "iceland_data_pdf"


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


def rebuild_knowledge_index() -> dict[str, int]:
    ensure_db()
    indexed = 0
    scanned = 0
    with get_conn() as conn:
        for pdf_path in sorted(PDF_DIR.glob("*.pdf")):
            scanned += 1
            content = extract_pdf_text(pdf_path)
            if not content.strip():
                continue
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
            indexed += 1
        conn.commit()
    return {"scanned": scanned, "indexed": indexed}


def list_docs() -> list[str]:
    return [p.name for p in sorted(PDF_DIR.glob("*.pdf"))]


def split_chunks(text: str, chunk_size: int = 420) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    return textwrap.wrap(text, width=chunk_size, break_long_words=False)


def keyword_score(query: str, text: str) -> int:
    terms = [t.lower() for t in re.findall(r"[\w\u4e00-\u9fff]+", query) if len(t) >= 2]
    lowered = text.lower()
    return sum(lowered.count(t) for t in terms)


def search_knowledge(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    ensure_db()
    rows: list[dict[str, Any]] = []
    qlow = query.lower()
    with get_conn() as conn:
        for row in conn.execute("SELECT title, content FROM docs"):
            title = row["title"]
            if qlow in title.lower():
                rows.append({"title": title, "snippet": "[title hit]", "score": 10})
            for chunk in split_chunks(row["content"]):
                score = keyword_score(query, chunk)
                if score > 0:
                    rows.append({"title": title, "snippet": chunk[:320], "score": score})

    rows.sort(key=lambda x: x["score"], reverse=True)
    return rows[:top_k]
