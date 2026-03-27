#!/usr/bin/env python3
"""
Iceland Travel Agent Lab
========================
A local, zero-setup teaching web app that demonstrates how examples 1~9
can be composed into one practical multi-feature product.

Run:
    python iceland_travel_lab.py
Then open:
    http://127.0.0.1:8765
"""

from __future__ import annotations

import json
import re
import sqlite3
import textwrap
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler

# Optional dependencies already listed in requirements.txt
try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None  # type: ignore

try:
    from duckduckgo_search import DDGS
except Exception:  # pragma: no cover
    DDGS = None  # type: ignore

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except Exception:  # pragma: no cover
    YouTubeTranscriptApi = None  # type: ignore

BASE_DIR = Path(__file__).resolve().parent
PDF_DIR = BASE_DIR / "iceland_data_pdf"
PHOTO_DIR = BASE_DIR / "iceland_data_photo"
DB_PATH = BASE_DIR / "tmp" / "iceland_lab.db"
HOST = "127.0.0.1"
PORT = 8765

EXAMPLE_MAP = [
    {
        "example": "1_agent_basic.py",
        "topic": "Basic Agent",
        "in_product": "前台旅遊顧問聊天入口，提供一般 QA 與引導。",
    },
    {
        "example": "2_agent_finance_tools.py",
        "topic": "Tool Use (Web + Finance)",
        "in_product": "即時查詢天氣、匯率、路況風險，回覆時附來源。",
    },
    {
        "example": "3_agent_create_private_tools.py",
        "topic": "Private Tools",
        "in_product": "客製計算器（自駕預算、行李重量、行程風險分數）。",
    },
    {
        "example": "4_youtube_agent.py",
        "topic": "YouTube Tools",
        "in_product": "把冰島攻略影片自動轉成重點清單與待辦。",
    },
    {
        "example": "5_knowledge_agent.py",
        "topic": "Knowledge DB",
        "in_product": "旅行文件（機票、租車規範、景點 PDF）可搜尋問答。",
    },
    {
        "example": "6_agent_with_memory.py",
        "topic": "Long-term Memory",
        "in_product": "記住學生偏好（預算、飲食、出發日期）跨會話延續。",
    },
    {
        "example": "7_view_memory_db.py",
        "topic": "Memory Inspection",
        "in_product": "後台可檢查記憶資料，教學透明、可除錯。",
    },
    {
        "example": "8_audio_agent.py",
        "topic": "Audio Understanding",
        "in_product": "語音備忘錄轉文字，納入行程規劃與任務清單。",
    },
    {
        "example": "9_google_search.py",
        "topic": "Native Search",
        "in_product": "出發前 7 天自動更新當地天氣與新聞提醒。",
    },
]


def ensure_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS docs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, key)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


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


def rebuild_knowledge_index() -> dict[str, Any]:
    ensure_db()
    indexed = 0
    scanned = 0
    files = sorted(PDF_DIR.glob("*.pdf"))
    with sqlite3.connect(DB_PATH) as conn:
        for pdf_path in files:
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


def split_chunks(text: str, chunk_size: int = 400) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    return textwrap.wrap(text, width=chunk_size, break_long_words=False)


def keyword_score(query: str, text: str) -> int:
    terms = [t.lower() for t in re.findall(r"[\w\u4e00-\u9fff]+", query) if len(t) >= 2]
    lowered = text.lower()
    return sum(lowered.count(t) for t in terms)


def search_knowledge(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    ensure_db()
    rows: list[dict[str, Any]] = []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        for row in conn.execute("SELECT title, content FROM docs"):
            chunks = split_chunks(row["content"])
            for chunk in chunks:
                score = keyword_score(query, chunk)
                if score > 0:
                    rows.append(
                        {"title": row["title"], "snippet": chunk[:320], "score": score}
                    )
    rows.sort(key=lambda x: x["score"], reverse=True)
    return rows[:top_k]


def parse_travel_memory(message: str) -> dict[str, str]:
    found: dict[str, str] = {}
    patterns = {
        "budget": r"預算[:：\s]*([0-9,]+)",
        "days": r"([0-9]{1,2})\s*天",
        "departure_date": r"(20[0-9]{2}[/-][0-9]{1,2}[/-][0-9]{1,2})",
    }
    for key, pat in patterns.items():
        m = re.search(pat, message)
        if m:
            found[key] = m.group(1)

    if "素食" in message:
        found["food_preference"] = "素食"
    if "自駕" in message:
        found["transport"] = "自駕"
    if "藍湖" in message:
        found["must_visit"] = "藍湖"
    return found


def upsert_memory(user_id: str, kv: dict[str, str]) -> None:
    if not kv:
        return
    ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        for k, v in kv.items():
            conn.execute(
                """
                INSERT INTO memory(user_id, key, value, updated_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(user_id, key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=excluded.updated_at
                """,
                (user_id, k, v, now_iso()),
            )
        conn.commit()


def get_memory(user_id: str) -> dict[str, str]:
    ensure_db()
    result: dict[str, str] = {}
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        for row in conn.execute("SELECT key, value FROM memory WHERE user_id=?", (user_id,)):
            result[row["key"]] = row["value"]
    return result


def add_chat(user_id: str, role: str, message: str) -> None:
    ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO chat_log(user_id, role, message, created_at) VALUES(?, ?, ?, ?)",
            (user_id, role, message, now_iso()),
        )
        conn.commit()


def get_chat(user_id: str, limit: int = 20) -> list[dict[str, str]]:
    ensure_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT role, message, created_at
            FROM chat_log
            WHERE user_id=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    rows = list(reversed(rows))
    return [dict(r) for r in rows]


def simple_agent_reply(user_id: str, message: str) -> str:
    memories = parse_travel_memory(message)
    upsert_memory(user_id, memories)
    profile = get_memory(user_id)
    refs = search_knowledge(message, top_k=2)

    lines = ["這是你的冰島旅行助理回覆："]
    if profile:
        ptxt = "、".join([f"{k}={v}" for k, v in profile.items()])
        lines.append(f"- 我目前記得你的偏好：{ptxt}")
    if refs:
        lines.append("- 我在文件庫找到相關資訊：")
        for r in refs:
            lines.append(f"  - {r['title']}: {r['snippet']}")
    else:
        lines.append("- 目前文件庫沒有直接命中，建議改問更具體關鍵字（如租車、航班、藍湖）。")
    lines.append("- 下一步我可以幫你：整理 5 天自駕行程、列出行李清單、或產生每日預算。")
    return "\n".join(lines)


def run_web_search(query: str) -> list[dict[str, str]]:
    if DDGS is None:
        return [{"title": "duckduckgo-search 未安裝", "url": "", "body": "請先安裝 requirements.txt"}]

    results: list[dict[str, str]] = []
    try:
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=5):
                results.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("href", ""),
                        "body": item.get("body", ""),
                    }
                )
    except Exception as e:
        return [{"title": "搜尋失敗", "url": "", "body": str(e)}]
    return results


def extract_youtube_id(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.hostname in {"youtu.be"}:
        return parsed.path.lstrip("/") or None
    if parsed.hostname and "youtube.com" in parsed.hostname:
        q = parse_qs(parsed.query)
        if "v" in q:
            return q["v"][0]
        parts = parsed.path.split("/")
        if "shorts" in parts:
            idx = parts.index("shorts")
            if idx + 1 < len(parts):
                return parts[idx + 1]
    return None


def summarize_youtube(url: str) -> dict[str, Any]:
    if YouTubeTranscriptApi is None:
        return {"ok": False, "message": "youtube_transcript_api 未安裝"}

    video_id = extract_youtube_id(url)
    if not video_id:
        return {"ok": False, "message": "無法解析 YouTube URL"}

    try:
        data = YouTubeTranscriptApi.get_transcript(video_id, languages=["zh-Hant", "zh", "en"])
        text = " ".join([d.get("text", "") for d in data]).strip()
        short = text[:1200]
        bullets = split_chunks(short, chunk_size=110)[:6]
        return {
            "ok": True,
            "video_id": video_id,
            "summary": [b for b in bullets if b],
            "length_chars": len(text),
        }
    except Exception as e:
        return {"ok": False, "message": f"讀取字幕失敗: {e}"}


def list_photos() -> list[dict[str, str]]:
    captions = {
        "blue_lagoon.jpg": "藍湖溫泉：安排在抵達或回程當天最省體力。",
        "ice_beach.jpg": "黑沙灘與冰塊海灘：風大，需保暖與防滑鞋。",
        "kirkjufellsfoss.jpg": "草帽山瀑布：傍晚光線佳，攝影熱門點。",
        "reykjavik.jpg": "雷克雅維克市區：適合安排城市散步與餐廳探索。",
    }
    items: list[dict[str, str]] = []
    for path in sorted(PHOTO_DIR.glob("*")):
        if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            items.append(
                {
                    "name": path.name,
                    "url": f"/photos/{path.name}",
                    "caption": captions.get(path.name, "冰島旅行參考圖片"),
                }
            )
    return items


INDEX_HTML = """<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Iceland Agent Lab</title>
  <style>
    :root {
      --bg: #eef4f7;
      --panel: #ffffff;
      --ink: #16222a;
      --muted: #54616b;
      --accent: #0f766e;
      --accent-2: #f59e0b;
      --line: #d6e0e4;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Space Grotesk", "Noto Sans TC", "PingFang TC", sans-serif;
      color: var(--ink);
      background: radial-gradient(circle at 10% 10%, #d9edf6 0%, var(--bg) 40%, #f4f7f1 100%);
    }
    .hero {
      padding: 36px 20px;
      background: linear-gradient(130deg, #0f766e 0%, #155e75 55%, #1f2937 100%);
      color: #fff;
    }
    .hero h1 { margin: 0 0 8px; font-size: 34px; letter-spacing: 0.2px; }
    .hero p { margin: 0; max-width: 840px; line-height: 1.6; opacity: 0.95; }

    .container { max-width: 1120px; margin: 20px auto 40px; padding: 0 14px; }
    .tabs { display: grid; grid-template-columns: repeat(auto-fit, minmax(165px, 1fr)); gap: 8px; margin-bottom: 12px; }
    .tab-btn {
      border: 1px solid #8cb7b2;
      background: #f3fbfa;
      color: #11443f;
      border-radius: 11px;
      padding: 11px 10px;
      cursor: pointer;
      font-weight: 700;
      transition: all 0.18s ease;
    }
    .tab-btn.active, .tab-btn:hover { background: #0f766e; color: #fff; transform: translateY(-1px); }

    .panel {
      display: none;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      box-shadow: 0 8px 30px rgba(0,0,0,0.06);
      padding: 16px;
      animation: fade 0.24s ease;
    }
    .panel.active { display: block; }
    @keyframes fade { from { opacity: 0; transform: translateY(6px);} to { opacity: 1; transform: translateY(0);} }

    .grid { display: grid; gap: 12px; }
    .grid-2 { grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); }
    .card {
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px;
      background: linear-gradient(165deg, #fff 0%, #fbfdff 100%);
    }
    h2 { margin: 2px 0 12px; font-size: 22px; }
    h3 { margin: 4px 0 8px; font-size: 16px; }
    .muted { color: var(--muted); font-size: 14px; }

    .btn {
      border: 0;
      border-radius: 10px;
      background: var(--accent);
      color: #fff;
      font-weight: 700;
      padding: 9px 12px;
      cursor: pointer;
    }
    .btn.alt { background: var(--accent-2); color: #111827; }
    input, textarea {
      width: 100%;
      border: 1px solid #c4d4d8;
      border-radius: 10px;
      padding: 9px;
      font-size: 14px;
      background: #fff;
      color: #12242e;
    }
    textarea { min-height: 100px; resize: vertical; }
    .row { display: flex; gap: 8px; align-items: center; }
    .row > * { flex: 1; }

    .out {
      white-space: pre-wrap;
      background: #0b1f2e;
      color: #e6f1f7;
      border-radius: 10px;
      padding: 10px;
      min-height: 92px;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 13px;
      line-height: 1.45;
      border: 1px solid #2a4455;
    }
    .list { margin: 0; padding-left: 18px; }
    .example { margin-bottom: 9px; padding-bottom: 9px; border-bottom: 1px dashed #d1dde3; }
    .example:last-child { border-bottom: 0; }

    .photo-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px;
    }
    .photo-card img {
      width: 100%;
      aspect-ratio: 4/3;
      object-fit: cover;
      border-radius: 10px;
      border: 1px solid #d4e2e8;
    }
    .pill {
      font-size: 12px;
      padding: 2px 8px;
      border-radius: 999px;
      background: #e8f5f4;
      border: 1px solid #c6e5e2;
      color: #0f5d56;
      font-weight: 700;
    }
    footer {
      margin-top: 14px;
      padding-top: 10px;
      border-top: 1px dashed #d0dde4;
      color: var(--muted);
      font-size: 13px;
    }
  </style>
</head>
<body>
  <section class="hero">
    <h1>Iceland Travel Agent Lab</h1>
    <p>把課堂的 agent 範例 1~9 放進真實產品流程：文件管理、知識檢索、長期記憶、工具呼叫與多模態資源。這個版本可本地開箱即用，學生不必先配置複雜基礎設施。</p>
  </section>

  <main class="container">
    <div class="tabs" id="tabs"></div>

    <section class="panel active" id="panel-overview">
      <h2>範例到產品功能對照</h2>
      <div id="exampleMap"></div>
      <footer>目標：讓學生理解 agent 不只存在於問答框，而是系統中的多個模組協作。</footer>
    </section>

    <section class="panel" id="panel-docs">
      <h2>文件管理 + Knowledge</h2>
      <div class="grid grid-2">
        <div class="card">
          <h3>文件索引</h3>
          <p class="muted">掃描 `iceland_data_pdf` 後建立本地知識索引，可直接提問。</p>
          <div class="row">
            <button class="btn" id="rebuildBtn">重建索引</button>
            <button class="btn alt" id="listDocBtn">列出文件</button>
          </div>
          <div class="out" id="docsOut"></div>
        </div>
        <div class="card">
          <h3>知識問答</h3>
          <input id="knowledgeQ" placeholder="例如：租車保險要注意什麼？" />
          <div style="height:8px"></div>
          <button class="btn" id="askKnowledgeBtn">查詢</button>
          <div class="out" id="knowledgeOut"></div>
        </div>
      </div>
    </section>

    <section class="panel" id="panel-memory">
      <h2>長期記憶 + 對話</h2>
      <div class="grid grid-2">
        <div class="card">
          <h3>對話助手</h3>
          <input id="userId" value="student@example.com" />
          <div style="height:8px"></div>
          <textarea id="chatInput" placeholder="例如：我的預算 50000，我想自駕 6 天，想去藍湖"></textarea>
          <button class="btn" id="chatBtn">送出並記憶</button>
          <div class="out" id="chatOut"></div>
        </div>
        <div class="card">
          <h3>記憶檢視（Example 7 的網頁化）</h3>
          <button class="btn alt" id="profileBtn">查看記憶</button>
          <button class="btn" id="historyBtn">查看對話紀錄</button>
          <div class="out" id="memoryOut"></div>
        </div>
      </div>
    </section>

    <section class="panel" id="panel-tools">
      <h2>Tool Use 工作台</h2>
      <div class="grid grid-2">
        <div class="card">
          <h3>Web Search（Example 2 / 9）</h3>
          <input id="searchQ" value="Iceland weather next week driving risk" />
          <button class="btn" id="searchBtn">搜尋</button>
          <div class="out" id="searchOut"></div>
        </div>
        <div class="card">
          <h3>YouTube 摘要（Example 4）</h3>
          <input id="ytUrl" value="https://www.youtube.com/watch?v=dTkV9n4WbIQ" />
          <button class="btn" id="ytBtn">抓字幕並摘要</button>
          <div class="out" id="ytOut"></div>
        </div>
      </div>
      <div class="card" style="margin-top:12px">
        <h3>照片素材（可延伸成多模態 Agent）</h3>
        <div id="photoGrid" class="photo-grid"></div>
      </div>
    </section>

    <section class="panel" id="panel-teaching">
      <h2>課堂建議流程</h2>
      <ol class="list">
        <li>先讓學生看「範例對照」，理解每支 script 在產品中的責任邊界。</li>
        <li>重建文件索引，請學生提問租車/機票問題，觀察檢索結果。</li>
        <li>讓學生輸入自己的偏好，刷新記憶並查看資料庫內容。</li>
        <li>用 web search 比對即時資訊，再用 YouTube 摘要補充攻略。</li>
        <li>最後讓學生把這些模組串成「自己的冰島旅行管家」。</li>
      </ol>
      <footer>這個 Lab 有意把「聊天」降成其中一個功能，而不是整個產品本體。</footer>
    </section>
  </main>

  <script>
    const tabs = [
      ["overview", "1~9 對照"],
      ["docs", "文件與知識"],
      ["memory", "長期記憶"],
      ["tools", "工具工作台"],
      ["teaching", "教學腳本"],
    ];

    const tabsEl = document.getElementById("tabs");
    tabs.forEach(([id, label], i) => {
      const btn = document.createElement("button");
      btn.className = "tab-btn" + (i === 0 ? " active" : "");
      btn.textContent = label;
      btn.onclick = () => {
        document.querySelectorAll(".tab-btn").forEach((x) => x.classList.remove("active"));
        document.querySelectorAll(".panel").forEach((x) => x.classList.remove("active"));
        btn.classList.add("active");
        document.getElementById("panel-" + id).classList.add("active");
      };
      tabsEl.appendChild(btn);
    });

    async function api(path, method="GET", body=null) {
      const opt = { method, headers: { "Content-Type": "application/json" } };
      if (body !== null) opt.body = JSON.stringify(body);
      const r = await fetch(path, opt);
      return await r.json();
    }

    function print(el, data) {
      el.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);
    }

    async function loadExampleMap() {
      const d = await api("/api/example_map");
      const root = document.getElementById("exampleMap");
      root.innerHTML = "";
      d.items.forEach((x) => {
        const div = document.createElement("div");
        div.className = "example";
        div.innerHTML = `<div class="pill">${x.example}</div><h3>${x.topic}</h3><div>${x.in_product}</div>`;
        root.appendChild(div);
      });
    }

    async function loadPhotos() {
      const d = await api("/api/photos");
      const g = document.getElementById("photoGrid");
      g.innerHTML = "";
      d.items.forEach((x) => {
        const card = document.createElement("div");
        card.className = "photo-card card";
        card.innerHTML = `<img src="${x.url}" alt="${x.name}" /><h3>${x.name}</h3><div class="muted">${x.caption}</div>`;
        g.appendChild(card);
      });
    }

    const docsOut = document.getElementById("docsOut");
    const knowledgeOut = document.getElementById("knowledgeOut");
    const chatOut = document.getElementById("chatOut");
    const memoryOut = document.getElementById("memoryOut");
    const searchOut = document.getElementById("searchOut");
    const ytOut = document.getElementById("ytOut");

    document.getElementById("rebuildBtn").onclick = async () => print(docsOut, await api("/api/rebuild_knowledge", "POST", {}));
    document.getElementById("listDocBtn").onclick = async () => print(docsOut, await api("/api/docs"));
    document.getElementById("askKnowledgeBtn").onclick = async () => {
      const q = document.getElementById("knowledgeQ").value.trim();
      print(knowledgeOut, await api("/api/knowledge_ask", "POST", { query: q }));
    };

    document.getElementById("chatBtn").onclick = async () => {
      const user_id = document.getElementById("userId").value.trim();
      const message = document.getElementById("chatInput").value.trim();
      print(chatOut, await api("/api/chat", "POST", { user_id, message }));
    };
    document.getElementById("profileBtn").onclick = async () => {
      const user_id = document.getElementById("userId").value.trim();
      print(memoryOut, await api("/api/memory", "POST", { user_id }));
    };
    document.getElementById("historyBtn").onclick = async () => {
      const user_id = document.getElementById("userId").value.trim();
      print(memoryOut, await api("/api/history", "POST", { user_id }));
    };

    document.getElementById("searchBtn").onclick = async () => {
      const query = document.getElementById("searchQ").value.trim();
      print(searchOut, await api("/api/web_search", "POST", { query }));
    };
    document.getElementById("ytBtn").onclick = async () => {
      const url = document.getElementById("ytUrl").value.trim();
      print(ytOut, await api("/api/youtube_summary", "POST", { url }));
    };

    loadExampleMap();
    loadPhotos();
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, status: int = 200) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(404, "Not Found")
            return
        data = path.read_bytes()
        ctype = "application/octet-stream"
        if path.suffix.lower() in {".jpg", ".jpeg"}:
            ctype = "image/jpeg"
        elif path.suffix.lower() == ".png":
            ctype = "image/png"
        elif path.suffix.lower() == ".webp":
            ctype = "image/webp"
        elif path.suffix.lower() == ".pdf":
            ctype = "application/pdf"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _parse_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self) -> None:  # noqa: N802
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/":
                self._send_html(INDEX_HTML)
                return
            if path == "/api/example_map":
                self._send_json({"items": EXAMPLE_MAP})
                return
            if path == "/api/docs":
                files = [p.name for p in sorted(PDF_DIR.glob("*.pdf"))]
                self._send_json({"count": len(files), "files": files})
                return
            if path == "/api/photos":
                self._send_json({"items": list_photos()})
                return
            if path.startswith("/photos/"):
                name = path.split("/photos/", 1)[1]
                if "/" in name or ".." in name:
                    self.send_error(400, "Bad path")
                    return
                self._send_file(PHOTO_DIR / name)
                return
            if path.startswith("/pdf/"):
                name = path.split("/pdf/", 1)[1]
                if "/" in name or ".." in name:
                    self.send_error(400, "Bad path")
                    return
                self._send_file(PDF_DIR / name)
                return
            self.send_error(404, "Not Found")
        except Exception:
            self._send_json({"ok": False, "error": traceback.format_exc()}, status=500)

    def do_POST(self) -> None:  # noqa: N802
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            data = self._parse_json()

            if path == "/api/rebuild_knowledge":
                result = rebuild_knowledge_index()
                self._send_json({"ok": True, **result})
                return

            if path == "/api/knowledge_ask":
                q = (data.get("query") or "").strip()
                if not q:
                    self._send_json({"ok": False, "error": "query 不能是空的"}, status=400)
                    return
                results = search_knowledge(q, top_k=5)
                self._send_json({"ok": True, "query": q, "matches": results})
                return

            if path == "/api/chat":
                user_id = (data.get("user_id") or "student@example.com").strip()
                message = (data.get("message") or "").strip()
                if not message:
                    self._send_json({"ok": False, "error": "message 不能是空的"}, status=400)
                    return
                add_chat(user_id, "user", message)
                reply = simple_agent_reply(user_id, message)
                add_chat(user_id, "assistant", reply)
                self._send_json({"ok": True, "reply": reply})
                return

            if path == "/api/memory":
                user_id = (data.get("user_id") or "student@example.com").strip()
                self._send_json({"ok": True, "user_id": user_id, "memory": get_memory(user_id)})
                return

            if path == "/api/history":
                user_id = (data.get("user_id") or "student@example.com").strip()
                self._send_json({"ok": True, "user_id": user_id, "history": get_chat(user_id)})
                return

            if path == "/api/web_search":
                query = (data.get("query") or "").strip()
                if not query:
                    self._send_json({"ok": False, "error": "query 不能是空的"}, status=400)
                    return
                self._send_json({"ok": True, "query": query, "results": run_web_search(query)})
                return

            if path == "/api/youtube_summary":
                url = (data.get("url") or "").strip()
                if not url:
                    self._send_json({"ok": False, "error": "url 不能是空的"}, status=400)
                    return
                self._send_json({"ok": True, "url": url, "data": summarize_youtube(url)})
                return

            self.send_error(404, "Not Found")
        except Exception:
            self._send_json({"ok": False, "error": traceback.format_exc()}, status=500)


def run() -> None:
    ensure_db()
    server = HTTPServer((HOST, PORT), Handler)
    print(f"Iceland Agent Lab running at http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop")
    server.serve_forever()


if __name__ == "__main__":
    run()
