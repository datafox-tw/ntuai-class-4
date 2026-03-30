from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

from .db import ensure_db, get_conn
from .knowledge import search_knowledge
from .tools import web_search, youtube_summary

# Setup
BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=API_KEY) if API_KEY else None

MODEL_ID = "gemini-2.0-flash"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def upsert_memory(user_id: str, kv: dict[str, str]) -> None:
    if not kv:
        return
    ensure_db()
    with get_conn() as conn:
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
    out: dict[str, str] = {}
    with get_conn() as conn:
        for row in conn.execute("SELECT key, value FROM memory WHERE user_id=?", (user_id,)):
            out[row["key"]] = row["value"]
    return out


def add_chat(user_id: str, role: str, message: str) -> None:
    ensure_db()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO chat_log(user_id, role, message, created_at) VALUES(?, ?, ?, ?)",
            (user_id, role, message, now_iso()),
        )
        conn.commit()


def get_chat_history(user_id: str, limit: int = 20) -> list[dict[str, str]]:
    ensure_db()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT role, message
            FROM chat_log
            WHERE user_id=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    # Convert to Gemini format
    history = []
    for r in reversed(rows):
        history.append({"role": "user" if r["role"] == "user" else "model", "parts": [{"text": r["message"]}]})
    return history


def generate_reply(user_id: str, message: str) -> str:
    if not client:
        return "Gemini API key not configured."

    # 1. RAG
    hits = search_knowledge(message, top_k=3)
    context_docs = "\n".join([f"[{h['title']}] {h['snippet']}" for h in hits])

    # 2. Memory
    profile = get_memory(user_id)
    memory_str = json.dumps(profile, ensure_ascii=False)

    # 3. History
    history = get_chat_history(user_id)

    # 4. System Prompt
    system_instruction = f"""你是一位專業的冰島旅行助理。
你的目標是根據現有資訊提供最準確的建議。

[用戶記憶/偏好]
{memory_str}

[參考文件內容]
{context_docs}

請遵循以下規則：
1. 優先使用參考文件的內容。
2. 尊重用戶已知的偏好（如預算、天數、飲食）。
3. 如果用戶提到新的偏好，請在回覆中以 [MEMORY_UPDATE: key=value] 格式標註，我會幫你存起來。
4. 你的回覆必須包含三個部分，並使用指定的標籤包裹：
   <THOUGHTS> 你的思考過程、使用的工具或查閱了哪些文件/記憶。 </THOUGHTS>
   <SOURCES> 列出你參考的文件標題和片段關鍵字。 </SOURCES>
   <REPLY> 正式的建議回覆。 </REPLY>
"""

    try:
        # We define tools for the agent
        tools = [web_search, youtube_summary]
        
        # Currently, the google-genai library supports tools in chat
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[{"role": "user", "parts": [{"text": message}]}],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                tools=tools,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False),
            ),
        )
        
        full_text = response.text
        
        # Extract memory updates
        updates = re.findall(r"\[MEMORY_UPDATE:\s*([^\]]+)\]", full_text)
        kv_updates = {}
        for up in updates:
            if "=" in up:
                k, v = up.split("=", 1)
                kv_updates[k.strip()] = v.strip()
        if kv_updates:
            upsert_memory(user_id, kv_updates)
            # Remove updates from display if needed, but keeping them for now is fine
        
        return full_text
    except Exception as e:
        return f"產生回覆失敗: {e}"

import re
