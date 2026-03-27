"""
Youtube Tools
=============================

Demonstrates youtube tools.
"""

from agno.agent import Agent
from agno.tools.youtube import YouTubeTools
from agno.models.google import Gemini
import os
from dotenv import load_dotenv

load_dotenv()
google_api_key = os.getenv('GOOGLE_API_KEY')

# ---------------------------------------------------------------------------
# 玩玩看youtube agent
# ---------------------------------------------------------------------------


agent = Agent(
    name="你是一個影片助手",
    model=Gemini(api_key=google_api_key, id="gemini-2.5-flash"),
    tools=[YouTubeTools()],
    description="請嘗試取得 YouTube 影片的字幕並回答問題",
)

# ---------------------------------------------------------------------------
# Run Agent
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    agent.print_response(
        "幫我分析這部影片好看嗎 https://www.youtube.com/watch?v=dTkV9n4WbIQ&t",
        markdown=True,
    )