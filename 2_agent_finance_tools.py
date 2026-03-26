"""
智能體工具 - 金融研究智能體
===========================================
為智能體提供工具，使其能夠搜尋網路並執行實際操作。
關鍵概念：
- tools：智能體可以呼叫的 Toolkit 實例列表
- instructions：系統層級指導，用於塑造智能體的行為
- add_datetime_to_context：注入目前日期/時間，以便智能體知道“今天”
- WebSearchTools：內建工具包，用於透過 DuckDuckGo 進行網路搜尋（無需 API 金鑰）
範例提示：
- “比較本月 AI 新創公司的最新融資輪次”
- “本周利率走勢如何？”
- “尋找英偉達 (Nvidia) 的最新財報”
- “本季計劃進行的頂級科技公司 IPO 有哪些？”
"""

from agno.agent import Agent
from agno.models.google import Gemini
from agno.tools.websearch import WebSearchTools #改變1:增加一個web search工具，讓agent能夠搜尋網路上的資訊
from agno.tools.yfinance import YFinanceTools
import os
from dotenv import load_dotenv


load_dotenv()
google_api_key = os.getenv('GOOGLE_API_KEY')

# ---------------------------------------------------------------------------
# Agent Instructions(和ai說你有什麼功能、你應該怎麼做)
# ---------------------------------------------------------------------------
instructions = """\
You are a finance research agent. You find and analyze current financial news.

## Workflow

1. Search the web for the requested financial information
2. Analyze and compare findings
3. Present a clear, structured summary

## Rules

- Always cite your sources
- Use tables for comparisons
- Include dates for all data points\
"""

# ---------------------------------------------------------------------------
# Create Agent
# ---------------------------------------------------------------------------
finance_agent = Agent(
    name="Finance Agent",
    model=Gemini(api_key=google_api_key, id="gemini-2.5-flash"),
    instructions=instructions,
    tools=[WebSearchTools(), YFinanceTools(all=True)], #改變2: 讓ai獲得搜尋網路的能力，這樣他就能找到最新的資訊來回答你的問題
    add_datetime_to_context=True, #改變3: 和ai説明今天的日期，這樣他就知道“今天”是什麼時候了
    markdown=True, 
)

finance_agent.print_response(
   "尋找英偉達 (Nvidia) 的最新股價和財報，並分析它們的趨勢",
   stream=True,
)