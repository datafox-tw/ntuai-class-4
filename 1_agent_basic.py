from agno.agent import Agent
from agno.models.google import Gemini
import os
from dotenv import load_dotenv


load_dotenv()
google_api_key = os.getenv('GOOGLE_API_KEY')
# 創建一個ai agent
# name和instructions會讓ai知道他是誰、他能做什麼，這樣他就能更好地回答你的問題（類似system prompt）
agent = Agent(
    name="Alice",  #隨便幫agent取個名字
    model=Gemini(api_key=google_api_key, id="gemini-2.5-flash"), # 使用Google Gemini作為大腦
    #這就是instrunction System prompy
    instructions="我是Alice, 一個友好的AI助手，專門幫助解答問題和提供資訊。目前還沒有任何能力，只能單純回答你的問題",
    markdown=True #他回答時會使用markdown格式，這樣你就可以在回答中看到圖片、表格等豐富的內容
)

# 運行agent，讓他回答問題
agent.print_response("你好你是誰", stream=True)
