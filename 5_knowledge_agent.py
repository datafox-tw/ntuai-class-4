from agno.agent import Agent
"""
#如果你不會rag的話沒關係，這裡的重點是讓agent能夠使用knowledge來回答問題，
# knowledge就像是agent的記憶庫一樣，你可以把文件、網頁等資訊放進去，
# 然後agent就能從裡面找到答案來回答你的問題。
"""
from agno.knowledge.embedder.google import GeminiEmbedder 
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.qdrant import Qdrant, SearchType
from agno.models.google import Gemini

import os
from dotenv import load_dotenv

load_dotenv()
google_api_key = os.getenv('GOOGLE_API_KEY')
knowledge = Knowledge(
    vector_db=Qdrant(
        collection="my_docs",
        url="http://localhost:6333",
        search_type=SearchType.hybrid,
        embedder=GeminiEmbedder(id="gemini-embedding-001", api_key=google_api_key),
    ),
)

# 你可以1. 換url連接，只需要是pdf的網站都可以 
# 2. 新增多個文件，讓agent有更多資訊可以回答問題
# 3. 甚至可以塞網站 但是不要太大會跑很久
# 4. 你也可以把一些重要的資訊直接寫成文字，然後塞進knowledge裡面，這樣agent就能知道這些資訊了
knowledge.insert(url="https://ee.ncnu.edu.tw/var/file/74/1074/img/421594310.pdf")
knowledge.insert(url="https://datafox.tw")



agent = Agent(
    name="文件管理助手",
    model=Gemini(api_key=google_api_key, id="gemini-2.5-flash"),
    knowledge=knowledge,
    description="請嘗試獲得文件中的資訊來回答問題，如果沒找到的話誠實回答「我不知道」",
    search_knowledge=True, #增加這行讓agent在回答問題的時候會先去knowledge裡面找相關的資訊，這樣他就能回答一些需要背景知識的問題了
    markdown=True,
)

# agent.print_response("特殊符號：若在論文中需要插入特殊符號時，請使用什麼字型？", stream=True)
agent.print_response("datafox.tw是誰", stream=True)