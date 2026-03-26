## 跟我做一模一樣的事情，簡單跑得動這次的課程教學！
- 用Docker那個方法，我最後會分享給大家該怎麼用最好

## 1. 用一個IDE介面(vscode, antigravity, pycharm...) 開起terminal
- 理論上你就會在你的專案資料夾 (aka你放code的地方)，在這裡執行code
- ls: 看你現在在哪一個資料夾
- `cd 資料夾名`：前往某個資料夾
- `cd ..`: 回到上一頁

## 2. 新增私密的api key
- 把`.env.example`改名成`.env`
- 在`GEMINI_API_KEY=`和`GOOGLE_API_KEY`輸入你的api key 不要有空格 （兩個api key是一樣的）

## 3.  安裝uv與建立虛擬環境
pip install uv
uv venv --python 3.12
source .venv/bin/activate
uv pip install -r requirements.txt

## 4.運行 python code
`python 1_agent_basic.py`
- 你可以做的事情：
- 更改name跟instruction，幫agent煥明和性格
- 舉例來說：改成「name="貓娘", instruction="你現在是一隻超可愛的貓娘，你會稱user為主人，每句話結尾都會加上一聲「喵～～」"」

==========到這裡停下來等講師繼續帶大家往下走============
## 指南
可以自己玩的東西：agent 1號到六號
不要亂動的東西：7號，.sh檔案
## 5. 嘗試用用看tools
`python 2_agent_finance_tools.py`
- 你可以做的事情：
- 更改instructions和name，讓他搜尋其他東西（例如：新聞）
- 問他「過往的今天發生過什麼事情」，看agent知不知道今天幾號
- 把tools裡面的`YFinanceTools(all=True)`刪除，看有沒有什麼結果

## 6. 嘗試自己寫tools
`python 3_agent_create_private_tools.py`
- 你可以做的事情：
- 嘗試問這個agent跟身高體重無關的問題，看他會回答什麼，你會發現，tools是需要的時候才跑，不是一定要跑。
- 嘗試叫coding agent幫你寫新的tools，舉例來說一個剪刀石頭布機器，如果你輸入剪刀或石頭或布，agent自動選一個拳然後看你有沒有贏。

## 7. 玩玩看其他tools
`python 4_youtube_agent.py`
- 你可以做的事情：
- 換不同的youtube網址看會不會理你（提示：有字幕的會更完整）
- 到這個網址看有沒有你喜歡的tools: https://github.com/agno-agi/agno/tree/main/cookbook/91_tools


## 8. 跑長期記憶（Knowledge）
- 先打開docker，然後跑 `./run_qdrant.sh`
- 如果這步驟失敗，先跑 `chmod +x ./run_qdrant.sh`
- 最後跑 `python 5_knowledge_agent.py`
- 你可以做的事情：
- 1. 換url連接，只需要是pdf的網站都可以
- 2. 新增多個文件，讓agent有更多資訊可以回答問題
- 3. 甚至可以塞網站 但是不要太大會跑很久
- 4. 你也可以把一些重要的資訊直接寫成文字，然後塞進knowledge裡面，這樣agent就能知道這些資訊了

- 注意：預設情況下他可能很笨請見諒

## 9. 跑對話記憶（Memory DB）
- 先打開docker，然後跑 `./run_pgvector.sh`
- 如果這步驟失敗，先跑 `chmod +x ./run_pgvector.sh`
- 最後跑 `python 6_agent_with_memory.py`
- 想看資料庫到底記了什麼：再跑 `python 7_view_memory_db.py --user-id=koyuchi@example.com`

如果你看到 `connection refused`（localhost:5532），代表資料庫沒啟動，回來重跑 `./run_pgvector.sh` 就好。

- 你可以做的事情：
- 1. 嘗試跟他用不同組合互動
- 2. 看db後台看資料庫怎麼記憶（用  `python 7_view_memory_db.py --user-id=koyuchi@example.com` ）


## faq
- 記得用uv pip install xxx 而不是 pip install xxx
## 參考資源
- 各種可能的玩法花樣可以參考這裡： https://github.com/agno-agi/agno/tree/main/cookbook/gemini_3
- 或者是：https://github.com/agno-agi/agno/tree/main/cookbook
- 你們可以照者上面的code依樣畫葫蘆，組合出你喜歡的agent樣式
- 反正看不懂要怎麼修改的話就把這個github裡面的內容都丟給coding agent叫他幫你新增一個python code檔案# ntuai-class-4
