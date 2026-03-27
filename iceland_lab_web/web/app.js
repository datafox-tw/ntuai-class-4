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

async function setupIndex() {
  const data = await api("/api/example_map");
  const root = document.getElementById("exampleMap");
  if (!root) return;
  root.innerHTML = "";
  data.items.forEach((x) => {
    const div = document.createElement("div");
    div.className = "example";
    div.innerHTML = `<strong>Example ${x.example}</strong> · ${x.topic}<div class="muted">${x.in_product}</div>`;
    root.appendChild(div);
  });
}

async function setupKnowledge() {
  const rebuildBtn = document.getElementById("rebuildBtn");
  const listBtn = document.getElementById("listBtn");
  const askBtn = document.getElementById("askBtn");
  if (!rebuildBtn) return;

  rebuildBtn.onclick = async () => print("docsOut", await api("/api/rebuild_knowledge", "POST", {}));
  listBtn.onclick = async () => print("docsOut", await api("/api/docs"));
  askBtn.onclick = async () => {
    const query = document.getElementById("knowledgeQ").value.trim();
    print("knowledgeOut", await api("/api/knowledge_ask", "POST", { query }));
  };
}

async function setupChat() {
  const chatBtn = document.getElementById("chatBtn");
  if (!chatBtn) return;
  chatBtn.onclick = async () => {
    const user_id = document.getElementById("userId").value.trim();
    const message = document.getElementById("chatInput").value.trim();
    print("chatOut", await api("/api/chat", "POST", { user_id, message }));
  };
}

async function setupMemory() {
  const memBtn = document.getElementById("memBtn");
  const hisBtn = document.getElementById("hisBtn");
  if (!memBtn) return;
  memBtn.onclick = async () => {
    const user_id = document.getElementById("userId").value.trim();
    print("memoryOut", await api("/api/memory", "POST", { user_id }));
  };
  hisBtn.onclick = async () => {
    const user_id = document.getElementById("userId").value.trim();
    print("memoryOut", await api("/api/history", "POST", { user_id }));
  };
}

async function setupTools() {
  const searchBtn = document.getElementById("searchBtn");
  const ytBtn = document.getElementById("ytBtn");
  if (!searchBtn) return;

  searchBtn.onclick = async () => {
    const query = document.getElementById("searchQ").value.trim();
    print("searchOut", await api("/api/web_search", "POST", { query }));
  };

  ytBtn.onclick = async () => {
    const url = document.getElementById("ytUrl").value.trim();
    print("ytOut", await api("/api/youtube_summary", "POST", { url }));
  };

  const photos = await api("/api/photos");
  const root = document.getElementById("photoGrid");
  if (!root) return;
  root.innerHTML = "";
  photos.items.forEach((x) => {
    const card = document.createElement("div");
    card.className = "card photo-card";
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
