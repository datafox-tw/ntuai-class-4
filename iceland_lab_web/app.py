#!/usr/bin/env python3
from __future__ import annotations

import json
import mimetypes
import sys
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from iceland_lab_web.services.db import ensure_db
    from iceland_lab_web.services.knowledge import index_file, list_docs, rebuild_knowledge_index, search_knowledge
    from iceland_lab_web.services.memory import add_chat, generate_reply, get_chat_history, get_memory
    from iceland_lab_web.services.tools import list_photos, web_search, youtube_summary
except ModuleNotFoundError:
    # Allow running with: python iceland_lab_web/app.py
    ROOT_DIR = Path(__file__).resolve().parents[1]
    if str(ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(ROOT_DIR))
    from iceland_lab_web.services.db import ensure_db
    from iceland_lab_web.services.knowledge import index_file, list_docs, rebuild_knowledge_index, search_knowledge
    from iceland_lab_web.services.memory import add_chat, generate_reply, get_chat_history, get_memory
    from iceland_lab_web.services.tools import list_photos, web_search, youtube_summary

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
PHOTO_DIR = BASE_DIR.parent / "iceland_data_photo"
HOST = "127.0.0.1"
PORT = 8765

EXAMPLE_MAP = [
    {"example": "1", "topic": "Basic Agent", "in_product": "聊天室入口"},
    {"example": "2", "topic": "Tool Use", "in_product": "即時 web search"},
    {"example": "3", "topic": "Private Tool", "in_product": "客製旅遊計算器"},
    {"example": "4", "topic": "YouTube", "in_product": "影片字幕摘要"},
    {"example": "5", "topic": "Knowledge", "in_product": "PDF 文件問答"},
    {"example": "6", "topic": "Memory", "in_product": "跨對話偏好記憶"},
    {"example": "7", "topic": "Memory DB", "in_product": "後台記憶檢視"},
    {"example": "8", "topic": "Audio", "in_product": "可擴充語音摘要流程"},
    {"example": "9", "topic": "Native Search", "in_product": "出發前風險更新"},
]

PAGES = {
    "/": "index.html",
    "/chat": "chat.html",
    "/knowledge": "knowledge.html",
    "/upload": "upload.html",
    "/memory": "memory.html",
    "/tools": "tools.html",
}

import cgi


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(404, "Not Found")
            return
        data = path.read_bytes()
        ctype, _ = mimetypes.guess_type(str(path))
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _parse_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self) -> None:  # noqa: N802
        try:
            path = urlparse(self.path).path
            if path in PAGES:
                return self._send_file(WEB_DIR / PAGES[path])

            if path.startswith("/assets/"):
                name = path.replace("/assets/", "", 1)
                if "/" in name or ".." in name:
                    self.send_error(400, "Bad path")
                    return
                return self._send_file(WEB_DIR / name)

            if path.startswith("/photos/"):
                name = path.replace("/photos/", "", 1)
                if "/" in name or ".." in name:
                    self.send_error(400, "Bad path")
                    return
                return self._send_file(PHOTO_DIR / name)

            if path == "/api/example_map":
                return self._send_json({"items": EXAMPLE_MAP})
            if path == "/api/docs":
                docs = list_docs()
                return self._send_json({"count": len(docs), "docs": docs})
            if path == "/api/photos":
                return self._send_json({"items": list_photos()})

            self.send_error(404, "Not Found")
        except Exception:
            self._send_json({"ok": False, "error": traceback.format_exc()}, status=500)

    def do_POST(self) -> None:  # noqa: N802
        try:
            path = urlparse(self.path).path
            if path == "/api/upload":
                # Handle multipart
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": self.headers["Content-Type"]},
                )
                if "file" not in form:
                    return self._send_json({"ok": False, "error": "No file uploaded"}, status=400)
                
                file_item = form["file"]
                if not file_item.filename:
                    return self._send_json({"ok": False, "error": "Empty filename"}, status=400)
                
                # Use PDF_DIR from knowledge if possible, or define it here
                pdf_path = BASE_DIR.parent / "iceland_data_pdf" / file_item.filename
                pdf_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(pdf_path, "wb") as f:
                    f.write(file_item.file.read())
                
                # Index in background (or foreground for simplicity now)
                stats = index_file(pdf_path)
                return self._send_json({"ok": True, "filename": file_item.filename, "stats": stats})

            data = self._parse_json()

            if path == "/api/rebuild_knowledge":
                return self._send_json({"ok": True, **rebuild_knowledge_index()})

            if path == "/api/knowledge_ask":
                query = (data.get("query") or "").strip()
                if not query:
                    return self._send_json({"ok": False, "error": "query 不能為空"}, status=400)
                return self._send_json({"ok": True, "matches": search_knowledge(query)})

            if path == "/api/chat":
                user_id = (data.get("user_id") or "student@example.com").strip()
                message = (data.get("message") or "").strip()
                if not message:
                    return self._send_json({"ok": False, "error": "message 不能為空"}, status=400)
                add_chat(user_id, "user", message)
                reply = generate_reply(user_id, message)
                add_chat(user_id, "assistant", reply)
                return self._send_json({"ok": True, "reply": reply})

            if path == "/api/memory":
                user_id = (data.get("user_id") or "student@example.com").strip()
                return self._send_json({"ok": True, "memory": get_memory(user_id)})

            if path == "/api/history":
                user_id = (data.get("user_id") or "student@example.com").strip()
                return self._send_json({"ok": True, "history": get_chat_history(user_id)})

            if path == "/api/web_search":
                query = (data.get("query") or "").strip()
                if not query:
                    return self._send_json({"ok": False, "error": "query 不能為空"}, status=400)
                return self._send_json({"ok": True, "results": web_search(query)})

            if path == "/api/youtube_summary":
                url = (data.get("url") or "").strip()
                if not url:
                    return self._send_json({"ok": False, "error": "url 不能為空"}, status=400)
                return self._send_json({"ok": True, "data": youtube_summary(url)})

            self.send_error(404, "Not Found")
        except Exception:
            self._send_json({"ok": False, "error": traceback.format_exc()}, status=500)


def run() -> None:
    ensure_db()
    server = HTTPServer((HOST, PORT), Handler)
    print(f"Iceland Lab Web running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run()
