from __future__ import annotations

import re
from datetime import datetime

from .db import ensure_db, get_conn
from .knowledge import search_knowledge


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


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


def get_chat_history(user_id: str, limit: int = 30) -> list[dict[str, str]]:
    ensure_db()
    with get_conn() as conn:
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
    return [dict(r) for r in reversed(rows)]


def generate_reply(user_id: str, message: str) -> str:
    kv = parse_travel_memory(message)
    upsert_memory(user_id, kv)
    profile = get_memory(user_id)
    hits = search_knowledge(message, top_k=2)

    lines = ["冰島旅行助理回覆："]
    if profile:
        lines.append("- 記憶中的偏好：" + "、".join(f"{k}={v}" for k, v in profile.items()))
    if hits:
        lines.append("- 我在文件找到這些片段：")
        for h in hits:
            lines.append(f"  - {h['title']}: {h['snippet']}")
    else:
        lines.append("- 目前文件沒有直接命中，建議用更明確關鍵字（租車、機票、餐廳）。")
    lines.append("- 你可以繼續要我：排 5 天自駕行程 / 產生預算 / 做行李清單。")
    return "\n".join(lines)
