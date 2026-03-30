async function api(path, method = "GET", body = null) {
  const opt = { method };
  if (body !== null) {
    opt.headers = { "Content-Type": "application/json" };
    opt.body = JSON.stringify(body);
  }
  const r = await fetch(path, opt);
  const data = await r.json();
  if (!r.ok) {
    throw new Error(data.error || `HTTP ${r.status}`);
  }
  return data;
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
      reply: reply[1].trim(),
    };
  }
  return { reply: text.trim() };
}

function withButtonLoading(btn, loadingText, runTask) {
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.textContent = loadingText;
  return runTask().finally(() => {
    btn.disabled = false;
    btn.textContent = originalText;
  });
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
      window.location.href = `/chat?q=${encodeURIComponent("請用這個能力示範一個冰島旅行案例：" + x.topic)}`;
    };
    root.appendChild(div);
  });
}

async function setupChat() {
  const sendBtn = document.getElementById("sendBtn");
  const resetBtn = document.getElementById("resetBtn");
  const agentInput = document.getElementById("agentInput");
  const agentHistory = document.getElementById("agentHistory");
  const thinkingProcess = document.getElementById("thinkingProcess");
  const userId = document.getElementById("userId");

  const urlParams = new URLSearchParams(window.location.search);
  const query = urlParams.get("q");
  if (query && agentInput) {
    agentInput.value = query;
  }

  if (!sendBtn) return;

  if (resetBtn) {
    resetBtn.onclick = async () => {
      const uid = userId.value.trim();
      if (!uid) return;
      if (!window.confirm(`確定要清空 ${uid} 的記憶與對話紀錄嗎？`)) return;

      await withButtonLoading(resetBtn, "清空中...", async () => {
        const res = await api("/api/reset_user", "POST", { user_id: uid });
        agentHistory.innerHTML = "";
        const info = document.createElement("div");
        info.className = "message system";
        info.textContent = `已清空：記憶 ${res.memory_deleted} 筆、對話 ${res.chat_deleted} 筆`;
        agentHistory.appendChild(info);
        if (thinkingProcess) {
          thinkingProcess.classList.add("hidden");
        }
      });
    };
  }

  sendBtn.onclick = async () => {
    const message = agentInput.value.trim();
    const uid = userId.value.trim();
    if (!message) return;

    const userDiv = document.createElement("div");
    userDiv.className = "message user";
    userDiv.textContent = message;
    agentHistory.appendChild(userDiv);
    agentInput.value = "";

    if (thinkingProcess) {
      thinkingProcess.classList.add("hidden");
    }

    const loadingDiv = document.createElement("div");
    loadingDiv.className = "message system loading";
    agentHistory.appendChild(loadingDiv);
    agentHistory.scrollTop = agentHistory.scrollHeight;

    const loadingSteps = [
      "助理思考中：讀取偏好記憶...",
      "助理思考中：檢索知識文件...",
      "助理思考中：規劃回覆內容...",
    ];
    let step = 0;
    loadingDiv.innerHTML = `${loadingSteps[step]} <span class='spinner'>⏳</span>`;
    const timer = window.setInterval(() => {
      step = (step + 1) % loadingSteps.length;
      loadingDiv.innerHTML = `${loadingSteps[step]} <span class='spinner'>⏳</span>`;
    }, 1200);

    await withButtonLoading(sendBtn, "思考中...", async () => {
      try {
        const res = await api("/api/chat", "POST", { user_id: uid, message });
        window.clearInterval(timer);
        loadingDiv.remove();

        const parsed = parseAgentResponse(res.reply);
        if ((parsed.thoughts || parsed.sources) && thinkingProcess) {
          thinkingProcess.classList.remove("hidden");
          document.getElementById("thoughtContent").innerHTML = parsed.thoughts
            ? `<strong>推論與紀錄：</strong><pre>${parsed.thoughts}</pre>`
            : "";
          document.getElementById("sourceContent").innerHTML = parsed.sources
            ? `<strong>參考來源：</strong><br>${parsed.sources.replace(/\n/g, "<br>")}`
            : "";
        }

        const assistantDiv = document.createElement("div");
        assistantDiv.className = "message assistant";
        assistantDiv.innerHTML = (parsed.reply || "目前沒有回覆").replace(/\n/g, "<br>");
        agentHistory.appendChild(assistantDiv);
        agentHistory.scrollTop = agentHistory.scrollHeight;
      } catch (e) {
        window.clearInterval(timer);
        loadingDiv.remove();
        const errDiv = document.createElement("div");
        errDiv.className = "message system";
        errDiv.textContent = `錯誤：${e}`;
        agentHistory.appendChild(errDiv);
      }
    });
  };
}

async function setupUpload() {
  const fileInput = document.getElementById("fileInput");
  const dropZone = document.getElementById("dropZone");
  const refreshDocsBtn = document.getElementById("refreshDocsBtn");

  dropZone.onclick = () => fileInput.click();
  dropZone.ondragover = (e) => {
    e.preventDefault();
    dropZone.classList.add("drag-over");
  };
  dropZone.ondragleave = () => {
    dropZone.classList.remove("drag-over");
  };
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
    statusEl.textContent = "正在上傳、切片與建立 Embedding...";
    statusEl.classList.remove("hidden");

    try {
      const r = await fetch("/api/upload", { method: "POST", body: formData });
      const res = await r.json();
      if (res.ok) {
        statusEl.textContent = `✅ 上傳成功，建立 ${res.stats.chunks} 個 chunk。`;
        loadDocList();
      } else {
        statusEl.textContent = `❌ 處理失敗: ${res.error}`;
      }
    } catch (e) {
      statusEl.textContent = `❌ 連線錯誤: ${e}`;
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

    res.docs.forEach((d) => {
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

  rebuildBtn.onclick = async () =>
    withButtonLoading(rebuildBtn, "重建中...", async () => {
      print("docsOut", "重建中...（會呼叫 Gemini Embedding API）");
      print("docsOut", await api("/api/rebuild_knowledge", "POST", {}));
    });
  listBtn.onclick = async () => print("docsOut", await api("/api/docs"));

  askBtn.onclick = async () =>
    withButtonLoading(askBtn, "查詢中...", async () => {
      const query = document.getElementById("knowledgeQ").value.trim();
      const out = document.getElementById("knowledgeOut");
      out.innerHTML = "<div style='padding:10px;text-align:center;'>知識庫思考中... ⏳</div>";
      const res = await api("/api/knowledge_ask", "POST", { query });
      if (!res.matches || res.matches.length === 0) {
        out.textContent = "沒有找到對應片段，請改用更具體關鍵字。";
        return;
      }
      out.innerHTML = res.matches
        .map(
          (m) =>
            `<div style='margin-bottom:12px;'><b>${m.title} (Score: ${m.score.toFixed(2)})</b><br>${m.snippet}</div>`
        )
        .join("");
    });
}

async function setupMemory() {
  const memBtn = document.getElementById("memBtn");
  const hisBtn = document.getElementById("hisBtn");
  const resetMemBtn = document.getElementById("resetMemBtn");
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
  if (resetMemBtn) {
    resetMemBtn.onclick = async () => {
      const user_id = document.getElementById("userId").value.trim();
      if (!user_id) return;
      if (!window.confirm(`確定要清空 ${user_id} 的記憶與對話紀錄嗎？`)) return;
      const res = await api("/api/reset_user", "POST", { user_id });
      print("memoryOut", {
        ok: true,
        message: "已完成重置",
        user_id,
        memory_deleted: res.memory_deleted,
        chat_deleted: res.chat_deleted,
      });
    };
  }
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

const page = document.body.dataset.page;
if (page === "index") setupIndex();
if (page === "knowledge") setupKnowledge();
if (page === "chat") setupChat();
if (page === "memory") setupMemory();
if (page === "tools") setupTools();
if (page === "upload") setupUpload();
