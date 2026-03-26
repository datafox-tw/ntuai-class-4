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
    name="你是一個健康助手",
    model=Gemini(api_key=google_api_key, id="gemini-2.5-flash"),
    tools=[YouTubeTools()],
    description="You are a YouTube agent. Obtain the captions of a YouTube video and answer questions.",
)

# ---------------------------------------------------------------------------
# Run Agent
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    agent.print_response(
        "Summarize this video https://www.youtube.com/watch?v=Iv9dewmcFbs&t",
        markdown=True,
    )