"""
Gemini Native Search - Real-Time News Agent
=============================================
Use Gemini's built-in Google Search. Just set search=True on the model.

Key concepts:
- search=True: Enables native Google Search on the Gemini model
- No extra dependencies: Unlike WebSearchTools (step 2), nothing to install
- Native search is seamless but less controllable than tool-based search

Example prompts to try:
- "What are the latest developments in AI this week?"
- "What happened in the stock market today?"
- "What are the top trending tech stories right now?"
"""

from agno.agent import Agent
from agno.models.google import Gemini
import os
from dotenv import load_dotenv

load_dotenv()
google_api_key = os.getenv('GOOGLE_API_KEY')

# ---------------------------------------------------------------------------
# Agent Instructions
# ---------------------------------------------------------------------------
instructions = """\
請盡力滿足用戶需求，查詢新聞、天氣、分析資訊等，並提供清晰、結構化的回答。
"""

# ---------------------------------------------------------------------------
# Create Agent
# ---------------------------------------------------------------------------
news_agent = Agent(
    name="News Agent",
    # search=True enables Gemini's native Google Search, no extra tools needed
    model=Gemini(id="gemini-2.5-flash", search=True, api_key=google_api_key),
    instructions=instructions,
    add_datetime_to_context=True,
    markdown=True,
)

# ---------------------------------------------------------------------------
# Run Agent
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    news_agent.print_response(
        "我下禮拜要去冰島玩，當地的天氣如何？想自駕的話有啥風險？",
        stream=True,
    )

# ---------------------------------------------------------------------------
# More Examples
# ---------------------------------------------------------------------------
"""
Native search vs tool-based search:

1. Native search (this example)
   model=Gemini(id="gemini-2.5-flash", search=True)
   - Seamless: model decides when to search
   - Less controllable: you can't see individual search calls
   - No extra packages needed

2. Tool-based search (step 2)
   tools=[WebSearchTools()]
   - Explicit: agent calls search as a tool
   - More controllable: you can see search queries in tool calls
   - Works with any model, not just Gemini

3. Grounding (step 5)
   model=Gemini(id="...", grounding=True)
   - Fact-based: responses include citations
   - Verifiable: grounding metadata shows sources
   - Best for factual accuracy

Choose based on your needs:
- Quick current info → Native search
- Full control over search → Tool-based
- Cited, verifiable facts → Grounding
"""