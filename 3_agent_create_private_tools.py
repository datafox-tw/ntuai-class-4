"""
如果你會寫code或者是vibe coding，也可以自己寫出一個工具來讓agent使用。agent會根據prompt來決定要不要呼叫這個工具。
"""

from agno.agent import Agent
from agno.models.google import Gemini
import os
from dotenv import load_dotenv

load_dotenv()
google_api_key = os.getenv('GOOGLE_API_KEY')

# 你可以自己寫一個函數！舉例來說這裡是一個計算BMI的函數，然後你可以把它註冊成一個工具，讓agent在需要的時候呼叫它來幫助回答問題。
def calculate_bmi(weight: float, height: float) -> dict:
    """計算BMI並提供健康建議    
    Args:
        weight: 體重（公斤）
        height: 身高（米）
    
    Returns:
        包含BMI值和健康建議的字典
    """
    # 教學友善：如果使用者傳入 180 這種公分值，自動轉成公尺
    if height > 3:
        height = height / 100

    bmi = weight / (height ** 2)
    
    if bmi < 18.5:
        category = "太瘦了"
        advice = "吃多一點，保持營養均衡"
    elif 18.5 <= bmi < 24:
        category = "正常"
        advice = "讚啦！繼續保持健康的生活方式"
    elif 24 <= bmi < 28:
        category = "偏胖"
        advice = "建議增加運動，注意飲食"
    else:
        category = "肥胖"
        advice = "建議減重，控制飲食並增加運動"
    
    return {
        "bmi": round(bmi, 2),
        "category": category,
        "advice": advice
    }

# 创建健康助手
health_agent = Agent(
    name="你是一個健康助手",
    model=Gemini(api_key=google_api_key, id="gemini-2.5-flash"),
    tools=[calculate_bmi],  # 直接把函數註冊成工具（最簡單）
    instructions=[
        "如果用戶詢問身高體重相關的問題，請使用calculate_bmi工具來計算BMI並提供健康建議",
        "提供專業的健康建議，但不要取代醫生的診斷"
    ],
    markdown=True
)

# 使用智能體
health_agent.print_response(
    "我身高180公分，體重70公斤，我的BMI是多少？",
    stream=True
)