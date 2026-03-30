from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from dotenv import load_dotenv

try:
    from agno.agent import Agent
    from agno.models.google import Gemini
    from agno.tools.youtube import YouTubeTools
except Exception:  # pragma: no cover
    Agent = None  # type: ignore
    Gemini = None  # type: ignore
    YouTubeTools = None  # type: ignore

try:
    from duckduckgo_search import DDGS
except Exception:  # pragma: no cover
    DDGS = None  # type: ignore

BASE_DIR = Path(__file__).resolve().parents[2]
PHOTO_DIR = BASE_DIR / "iceland_data_photo"
load_dotenv(BASE_DIR / ".env")
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def web_search(query: str) -> list[dict[str, str]]:
    if DDGS is None:
        return [{"title": "duckduckgo-search 未安裝", "url": "", "body": "請先 uv pip install -r requirements.txt"}]

    out: list[dict[str, str]] = []
    try:
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=5):
                out.append(
                    {
                        "title": item.get("title", ""),
                        "url": item.get("href", ""),
                        "body": item.get("body", ""),
                    }
                )
    except Exception as e:
        return [{"title": "搜尋失敗", "url": "", "body": str(e)}]
    return out


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


def youtube_summary(url: str) -> dict[str, Any]:
    video_id = extract_youtube_id(url)
    if not video_id:
        return {"ok": False, "message": "無法解析 YouTube URL"}

    if Agent is None or Gemini is None or YouTubeTools is None:
        return {"ok": False, "message": "agno YouTubeTools 未安裝或匯入失敗"}
    if not API_KEY:
        return {"ok": False, "message": "Gemini API key 未設定"}

    try:
        agent = Agent(
            model=Gemini(api_key=API_KEY, id="gemini-2.5-flash"),
            tools=[YouTubeTools()],
            description="取得 YouTube 字幕後，整理成教學友善的重點摘要",
            markdown=True,
        )
        prompt = (
            f"請摘要這支影片的重點：{url}\n"
            "請用繁中輸出 6 個條列重點，每點一句話。"
        )
        output = agent.run(prompt)
        text = str(output.content or "").strip()
        if not text:
            return {"ok": False, "message": "模型沒有回傳內容"}

        bullets = []
        for line in text.splitlines():
            cleaned = line.strip().lstrip("-•* ").strip()
            if cleaned:
                bullets.append(cleaned)
        if not bullets:
            bullets = [text]
        bullets = bullets[:8]
        return {"ok": True, "video_id": video_id, "summary": bullets, "length_chars": len(text)}
    except Exception as e:
        return {"ok": False, "message": f"讀取字幕失敗: {e}"}


def list_photos() -> list[dict[str, str]]:
    captions = {
        "blue_lagoon.jpg": "藍湖溫泉：到達或回程日安排最順。",
        "ice_beach.jpg": "冰灘風大，請準備防風防滑。",
        "kirkjufellsfoss.jpg": "草帽山瀑布：黃昏光線很漂亮。",
        "reykjavik.jpg": "雷克雅維克市區：餐廳與散步景點集中。",
    }
    items: list[dict[str, str]] = []
    for path in sorted(PHOTO_DIR.glob("*")):
        if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            items.append(
                {
                    "name": path.name,
                    "url": f"/photos/{path.name}",
                    "caption": captions.get(path.name, "冰島旅行素材"),
                }
            )
    return items
