"""
Agentic Memory Management
=========================

This example shows how to use agentic memory with an Agent.
During each run, the Agent can create, update, and delete user memories.
"""
import asyncio
from uuid import uuid4
from agno.agent.agent import Agent
from agno.db.postgres import PostgresDb
from rich.pretty import pprint
from agno.knowledge.embedder.google import GeminiEmbedder 
from agno.models.google import Gemini

import os
from dotenv import load_dotenv

load_dotenv()
google_api_key = os.getenv('GOOGLE_API_KEY')

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
db_url = "postgresql+psycopg://ai:ai@localhost:5532/ai"
db = PostgresDb(db_url=db_url)




# ---------------------------------------------------------------------------
# Create Agent
# ---------------------------------------------------------------------------
agent = Agent(
    model=Gemini(api_key=google_api_key, id="gemini-2.5-flash"),
    db=db,
    enable_agentic_memory=True,
    update_memory_on_run=True,
)

if __name__ == "__main__":
    #如果你想要保留舊的記憶的話就把下面那一句給刪掉，或者註解掉（最前面加上井字號）
    db.clear_memories() # Clear existing memories for a clean slate

    session_id = str(uuid4())
    koyuchi_id = "koyuchi@example.com"
    #進行一段對話，讓agent對柯宥圻有一些基本的認識，這些認識就會被存在agent的memory裡面，這樣agent就能在後續的對話中使用這些資訊了
    asyncio.run(
        agent.aprint_response(
            "我是柯宥圻，是ai社的講師，也是台大資科碩士學生，我喜歡游泳和畫畫",
            stream=True,
            user_id=koyuchi_id,
            session_id=session_id,
        )
    )
    #有設定memory的話，就算這兩次問答是獨立的，agent也能記得之前說過的話，這樣就能在後續的對話中使用這些資訊了
    agent.print_response(
        "柯宥圻的興趣是什麼?", stream=True, user_id=koyuchi_id, session_id=session_id
    )

    #關於柯宥圻的興趣的記憶就會被存在agent的memory裡面，這樣agent就能在後續的對話中使用這些資訊了
    memories = agent.get_user_memories(user_id=koyuchi_id)
    print("柯宥圻的記憶 :")
    pprint(memories)
    
    #嘗試刪除agent對柯宥圻的記憶，看看agent會不會忘記柯宥圻的興趣
    agent.print_response(
        "我最近發現游泳好累我改成喜歡爬山了.",
        stream=True,
        user_id=koyuchi_id,
        session_id=session_id,
    )
    memories = agent.get_user_memories(user_id=koyuchi_id)
    print("柯宥圻的記憶 :")
    pprint(memories)

    #我們可以持續跟他對話讓他記得更多細節
    agent.print_response(
        "我的生日是2003/06/22，當天是夏至",
        stream=True,
        user_id=koyuchi_id,
        session_id=session_id,
    )
    memories = agent.get_user_memories(user_id=koyuchi_id)
    print("柯宥圻的記憶 :")
    pprint(memories)


    #嘗試取得記憶，展示剛剛有沒有記得兩個重要記憶
    agent.print_response(
        "柯宥圻想要在台北於他的生日去從事他喜歡的運動你推薦他去台北哪裡",
        stream=True,
        user_id=koyuchi_id,
        session_id=session_id,
    )



