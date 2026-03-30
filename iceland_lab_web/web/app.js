async function api(path, method = "GET", body = null) {
  const opt = { method, headers: { "Content-Type": "application/json" } };
  if (body !== null) opt.body = JSON.stringify(body);
  const r = await fetch(path, opt);
  return await r.json();
}

function print(id, data) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);
}

function parseAgentResponse(text) {
  const thoughts = text.match(/<THOUGHTS>([\s\S]*?)<\/THOUGHTS>/);
  const sources = text.match(/<SOURCES>([\s\S]*?)<\/SOURCES>/);
  const reply = text.match(/<REPLY>([\s\S]*?)<\/REPLY>/);
  
  if (reply) {
    return {
      thoughts: thoughts ? thoughts[1].trim() : "",
      sources: sources ? sources[1].trim() : "",
      reply: reply[1].trim()
    };
  }
  
  return { reply: text };
}

async function setupIndex() {
  const data = await api("/api/example_map");
  const root = document.getElementById("exampleMap");
  if (!root) return;
  root.innerHTML = "";
  data.items.forEach((x) => {
    const div = document.createElement("div");
    div.className = "example";
    div.innerHTML = `<strong>Example ${x.example}</strong> · ${x.topic}<div class="muted">${x.in_product}</div>`;
    div.onclick = () => {
        window.location.href = `/chat?q=${encodeURIComponent(x.topic + " 相關問題...")}`;
    };
    root.appendChild(div);
  });
}

async function setupChat() {
  const sendBtn = document.getElementById("sendBtn");
  const agentInput = document.getElementById("agentInput");
  const agentHistory = document.getElementById("agentHistory");
  const thinkingProcess = document.getElementById("thinkingProcess");
  const userId = document.getElementById("userId");

  // Pre-fill query if coming from index page
  const urlParams = new URLSearchParams(window.location.search);
  const query = urlParams.get('q');
  if (query && agentInput) {
      agentInput.value = query;
  }

  if (sendBtn) {
    sendBtn.onclick = async () => {
        const message = agentInput.value.trim();
        const uid = userId.value.trim();
        if (!message) return;

        // User message UI update
        const userDiv = document.createElement("div");
        userDiv.className = "message user";
        userDiv.textContent = message;
        agentHistory.appendChild(userDiv);
        agentInput.value = "";
        
        // Disable input while fetching
        sendBtn.disabled = true;
        sendBtn.textContent = '...';
        
        const loadingDiv = document.createElement("div");
        loadingDiv.className = "message system loading";
        loadingDiv.innerHTML = "助理思考中，請稍候 <span class='spinner'>⏳</span>";
        agentHistory.appendChild(loadingDiv);
        agentHistory.scrollTop = agentHistory.scrollHeight;
        
        // Hide previous thoughts
        if (thinkingProcess) {
            thinkingProcess.classList.add("hidden");
        }

        // Send API Request
        const res = await api("/api/chat", "POST", { user_id: uid, message });
        
        loadingDiv.remove();
        sendBtn.disabled = false;
        sendBtn.textContent = '傳送';

        if (res.ok) {
            const parsed = parseAgentResponse(res.reply);
            
            // Show thoughts & sources if present
            if (parsed.thoughts || parsed.sources) {
                if (thinkingProcess) {
                    thinkingProcess.classList.remove("hidden");
                    document.getElementById("thoughtContent").innerHTML = parsed.thoughts ? `<strong>推論與紀錄：</strong><pre>${parsed.thoughts}</pre>` : "";
                    document.getElementById("sourceContent").innerHTML = parsed.sources ? `<strong>參考來源：</strong><br>${parsed.sources.replace(/\n/g, "<br>")}` : "";
                }
            }

            // Assistant message UI update
            const assistantDiv = document.createElement("div");
            assistantDiv.className = "message assistant";
            assistantDiv.innerHTML = parsed.reply.replace(/\n/g, "<br>");
            agentHistory.appendChild(assistantDiv);

            // Auto-scroll
            agentHistory.scrollTop = agentHistory.scrollHeight;
        } else {
            alert("Error: " + res.error);
        }
    };
  }
}

async function setupUpload() {
  const fileInput = document.getElementById("fileInput");
  const dropZone = document.getElementById("dropZone");
  const refreshDocsBtn = document.getElementById("refreshDocsBtn");

  dropZone.onclick = () => fileInput.click();
  dropZone.ondragover = (e) => { e.preventDefault(); dropZone.classList.add("drag-over"); };
  dropZone.ondragleave = () => { dropZone.classList.remove("drag-over"); };
  dropZone.ondrop = (e) => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    handleFiles(e.dataTransfer.files);
  };

  fileInput.onchange = () => handleFiles(fileInput.files);

  async function handleFiles(files) {
    if (files.length === 0) return;
    const file = files[0];
    const formData = new FormData();
    formData.append("file", file);

    const statusEl = document.getElementById("uploadStatus");
    statusEl.textContent = "正在上傳並切割文件建立 Embedding 中 (需呼叫 Gemini API)...";
    statusEl.classList.remove("hidden");

    try {
      const r = await fetch("/api/upload", { method: "POST", body: formData });
      const res = await r.json();
      if (res.ok) {
        statusEl.textContent = `✅ 成功上傳並解析！共切分出 ${res.stats.chunks} 個文件片段存入向量資料庫。`;
        loadDocList();
      } else {
        statusEl.textContent = `❌ 處理失敗: ${res.error}`;
      }
    } catch (e) {
      statusEl.textContent = `❌ 連線或伺服器錯誤: ${e}`;
    }
  }

  async function loadDocList() {
    const res = await api("/api/docs");
    const docList = document.getElementById("docList");
    if (!docList) return;
    docList.innerHTML = "";
    
    if (res.docs.length === 0) {
        docList.innerHTML = "<li class='muted'>目前沒有任何文件</li>";
        return;
    }
    
    res.docs.forEach(d => {
       const li = document.createElement("li");
       li.textContent = `📄 ${d}`;
       docList.appendChild(li);
    });
  }

  refreshDocsBtn.onclick = loadDocList;
  loadDocList();
}

async function setupKnowledge() {
  const rebuildBtn = document.getElementById("rebuildBtn");
  const listBtn = document.getElementById("listBtn");
  const askBtn = document.getElementById("askBtn");
  if (!rebuildBtn) return;

  rebuildBtn.onclick = async () => {
    print("docsOut", "重建中... (需要呼叫 Gemini API，可能需要數秒鐘) ⏳");
    print("docsOut", await api("/api/rebuild_knowledge", "POST", {}));
  };
  listBtn.onclick = async () => print("docsOut", await api("/api/docs"));
  askBtn.onclick = async () => {
    const query = document.getElementById("knowledgeQ").value.trim();
    const out = document.getElementById("knowledgeOut");
    out.innerHTML = "<div style='padding:10px;text-align:center;'>知識庫檢索中... ⏳</div>";
    const res = await api("/api/knowledge_ask", "POST", { query });
    out.innerHTML = res.matches.map(m => `<div style='margin-bottom:10px;'><b>${m.title} (Score: ${m.score.toFixed(2)})</b><br>${m.snippet}</div>`).join("");
  };
}

async function setupMemory() {
  const memBtn = document.getElementById("memBtn");
  const hisBtn = document.getElementById("hisBtn");
  if (!memBtn) return;
  memBtn.onclick = async () => {
    const user_id = document.getElementById("userId").value.trim();
    const res = await api("/api/memory", "POST", { user_id });
    print("memoryOut", res);
  };
  hisBtn.onclick = async () => {
    const user_id = document.getElementById("userId").value.trim();
    const res = await api("/api/history", "POST", { user_id });
    print("memoryOut", res);
  };
}

async function setupTools() {
  const searchBtn = document.getElementById("searchBtn");
  const ytBtn = document.getElementById("ytBtn");
  if (!searchBtn) return;

  searchBtn.onclick = async () => {
    const query = document.getElementById("searchQ").value.trim();
    print("searchOut", "網路搜尋中... ⏳");
    print("searchOut", await api("/api/web_search", "POST", { query }));
  };

  ytBtn.onclick = async () => {
    const url = document.getElementById("ytUrl").value.trim();
    print("ytOut", "讀取字幕與摘要中... ⏳");
    print("ytOut", await api("/api/youtube_summary", "POST", { url }));
  };

  const photos = await api("/api/photos");
  const root = document.getElementById("photoGrid");
  if (!root) return;
  root.innerHTML = "";
  photos.items.forEach((x) => {
    const card = document.createElement("div");
    card.className = "photo-card";
    card.innerHTML = `<img src="${x.url}" alt="${x.name}"/><h3>${x.name}</h3><div class="muted">${x.caption}</div>`;
    root.appendChild(card);
  });
}

// Router
const page = document.body.dataset.page;
if (page === "index") setupIndex();
if (page === "knowledge") setupKnowledge();
if (page === "chat") setupChat();
if (page === "memory") setupMemory();
if (page === "tools") setupTools();
if (page === "upload") setupUpload();
