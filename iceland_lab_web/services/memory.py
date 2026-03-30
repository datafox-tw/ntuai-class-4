from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

from agno.agent import Agent
from agno.models.google import Gemini
from dotenv import load_dotenv

from .db import ensure_db, get_conn
from .knowledge import search_knowledge
from .tools import web_search, youtube_summary

# Setup
BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
MODEL_ID = "gemini-2.5-flash"


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


def reset_user_data(user_id: str) -> dict[str, int]:
    ensure_db()
    with get_conn() as conn:
        mem_deleted = conn.execute("DELETE FROM memory WHERE user_id=?", (user_id,)).rowcount or 0
        chat_deleted = conn.execute("DELETE FROM chat_log WHERE user_id=?", (user_id,)).rowcount or 0
        conn.commit()
    return {"memory_deleted": mem_deleted, "chat_deleted": chat_deleted}


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


def parse_travel_memory(message: str) -> dict[str, str]:
    found: dict[str, str] = {}

    patterns = {
        "budget_twd": r"預算[:：\s]*([0-9,]+)",
        "days": r"([0-9]{1,2})\s*天",
    }
    for key, pat in patterns.items():
        m = re.search(pat, message)
        if m:
            found[key] = m.group(1).replace(",", "")

    if "藍湖" in message:
        found["must_visit"] = "藍湖"
    if "自駕" in message:
        found["transport"] = "自駕"
    if "素食" in message:
        found["food_preference"] = "素食"
    return found


def _format_history_for_prompt(history: list[dict[str, str]], max_items: int = 8) -> str:
    if not history:
        return "（尚無歷史對話）"
    rows: list[str] = []
    for item in history[-max_items:]:
        role = "使用者" if item["role"] == "user" else "助理"
        text = item["parts"][0]["text"].strip()
        rows.append(f"- {role}: {text}")
    return "\n".join(rows)


def _format_hits_for_prompt(hits: list[dict[str, str]]) -> str:
    if not hits:
        return "（知識庫暫無命中）"
    lines: list[str] = []
    for idx, hit in enumerate(hits, start=1):
        snippet = (hit.get("snippet") or "").strip().replace("\n", " ")
        lines.append(f"{idx}. [{hit.get('title', 'unknown')}] {snippet[:260]}")
    return "\n".join(lines)


def _build_agent(profile: dict[str, str], history: list[dict[str, str]], hits: list[dict[str, str]]) -> Agent:
    additional_context = f"""
[使用者偏好]
{json.dumps(profile, ensure_ascii=False)}

[最近對話]
{_format_history_for_prompt(history)}

[知識庫檢索片段]
{_format_hits_for_prompt(hits)}
""".strip()

    return Agent(
        name="冰島旅行教學助理",
        model=Gemini(api_key=API_KEY, id=MODEL_ID),
        tools=[web_search, youtube_summary],
        instructions=[
            "你是課堂示範用的冰島旅行 Agent，回覆要能直接被學生看懂並模仿。",
            "先直接回答需求，不要只講『請提供更多關鍵字』。",
            "當使用者要行程時，至少提供每天早午晚與移動建議。",
            "若知識庫沒有資料，明確說明缺口，再給出可執行的暫定方案。",
            "回覆最後可附上 2~3 個下一步建議。",
            "如果偵測到新的偏好，額外輸出 [MEMORY_UPDATE: key=value]。",
        ],
        markdown=True,
        reasoning=True,
        add_datetime_to_context=True,
        additional_context=additional_context,
    )


def generate_reply(user_id: str, message: str) -> str:
    if not API_KEY:
        return "Gemini API key not configured."

    # Update memory from explicit user input first.
    detected = parse_travel_memory(message)
    if detected:
        upsert_memory(user_id, detected)

    # Build context for agno agent.
    hits = search_knowledge(message, top_k=4)
    profile = get_memory(user_id)
    history = get_chat_history(user_id)
    agent = _build_agent(profile=profile, history=history, hits=hits)

    try:
        output = agent.run(
            message,
            user_id=user_id,
            session_id=f"iceland-lab-{user_id}",
            add_history_to_context=True,
        )
        full_text = str(output.content or "").strip()
        if not full_text:
            full_text = "我有點卡住了，請再說一次需求，我會重新規劃。"

        # Extract memory updates from model output.
        updates = re.findall(r"\[MEMORY_UPDATE:\s*([^\]]+)\]", full_text, flags=re.IGNORECASE)
        kv_updates = {}
        for up in updates:
            if "=" in up:
                k, v = up.split("=", 1)
                kv_updates[k.strip()] = v.strip()

        if kv_updates:
            upsert_memory(user_id, kv_updates)

        clean_text = re.sub(r"\s*\[MEMORY_UPDATE:[^\]]+\]\s*", "\n", full_text, flags=re.IGNORECASE).strip()
        return clean_text
    except Exception as e:
        return f"產生回覆失敗: {e}"
