from agno.agent import Agent
from agno.models.google import Gemini
import os
from dotenv import load_dotenv


load_dotenv()
google_api_key = os.getenv('GOOGLE_API_KEY')
# 創建一個ai agent
# name和instructions會讓ai知道他是誰、他能做什麼，這樣他就能更好地回答你的問題（類似system prompt）
agent = Agent(
    name="catmaid",  #隨便幫agent取個名字
    model=Gemini(api_key=google_api_key, id="gemini-2.5-flash"), # 使用Google Gemini作為大腦
    #這就是instrunction System prompy
    instructions="你現在是一隻超可愛的貓娘，你會稱user為主人，每句話結尾都會加上一聲「喵～～」",
    markdown=True #他回答時會使用markdown格式，這樣你就可以在回答中看到圖片、表格等豐富的內容
)

# 運行agent，讓他回答問題
agent.print_response("請跟我介紹深度學習是什麼", stream=True)
