// Chat UI: chats live in localStorage; the server keeps the agent session for each chat.
const $ = (s) => document.querySelector(s);
const STORE = "helpdesk.chats.v1";
const SUGGESTIONS = [
  "What is the attendance requirement to sit in the Major exam?",
  "What is the slot for Autonomous Systems?",
  "How many Open Elective credits do I need for a B.Tech?",
  "Write an email to the instructor of CSL7650 that I need leave for 2 days",
];

let chats = load();
let activeId = (() => { try { return localStorage.getItem(STORE + ".active"); } catch { return null; } })();
let busy = false;
let baseGraph = null;
let graphScope = "local";
let panelTab = "sources";

function load() {
  try { return JSON.parse(localStorage.getItem(STORE)) || []; } catch { return []; }
}
function save() {
  try { localStorage.setItem(STORE, JSON.stringify(chats)); } catch {}
}
const active = () => chats.find((c) => c.id === activeId);
const uid = () => Math.random().toString(36).slice(2, 10);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const md = (s) => DOMPurify.sanitize(marked.parse(s || ""));

// ---------- sidebar ----------
function renderList() {
  const list = $("#chatList");
  list.innerHTML = "";
  [...chats].sort((a, b) => b.updated - a.updated).forEach((c) => {
    const el = document.createElement("div");
    el.className = "chat-item" + (c.id === activeId ? " active" : "");
    el.innerHTML = `<span>${esc(c.title)}</span><button class="del" title="Delete chat">×</button>`;
    el.onclick = () => openChat(c.id);
    el.querySelector(".del").onclick = (e) => {
      e.stopPropagation();
      chats = chats.filter((x) => x.id !== c.id);
      save();
      if (activeId === c.id) newChat(); else renderList();
    };
    list.appendChild(el);
  });
}

function newChat() {
  activeId = null;
  renderAll();
  $("#input").focus();
}

function openChat(id) {
  activeId = id;
  $("#sidebar").classList.remove("open");
  renderAll();
}

function renderAll() {
  try { localStorage.setItem(STORE + ".active", activeId || ""); } catch {}
  renderList();
  renderMessages();
  renderSources();
  renderGraph();
  $("#chatTitle").textContent = active()?.title || "New chat";
}

// ---------- messages ----------
function renderMessages() {
  const box = $("#messages");
  const chat = active();
  if (!chat) {
    box.innerHTML = `<div class="empty"><h1>Ask the academic helpdesk</h1>
      <p>Regulations, curricula, time table, exams and instructor emails. Every answer cites its document.</p>
      <div class="suggestions">${SUGGESTIONS.map((s) => `<button>${esc(s)}</button>`).join("")}</div></div>`;
    box.querySelectorAll(".suggestions button").forEach((b) => (b.onclick = () => send(b.textContent)));
    return;
  }
  box.innerHTML = "";
  chat.messages.forEach((m, i) => box.appendChild(messageEl(m, i)));
  if (busy) box.appendChild(typingEl());
  box.scrollTop = box.scrollHeight;
}

function messageEl(m, i) {
  const el = document.createElement("div");
  el.className = `msg ${m.role}` + (m.error ? " error" : "");
  el.dataset.index = i;
  if (m.role === "user") {
    el.innerHTML = `<div class="bubble">${esc(m.text)}</div>`;
    return el;
  }
  el.innerHTML = `<div class="body">${m.error ? esc(m.text) : md(m.text)}</div>`;
  const meta = document.createElement("div");
  meta.className = "meta";
  (m.sources || []).filter((s) => s.doc_id).forEach((s) => {
    const chip = document.createElement("button");
    chip.className = "chip" + (s.cited ? " cited" : "");
    chip.textContent = s.label;
    chip.title = s.label;
    chip.onclick = () => focusSource(i, s.doc_id);
    meta.appendChild(chip);
  });
  if (m.meta) {
    const info = document.createElement("span");
    info.textContent = `${m.meta.seconds}s · ${m.meta.agents.join(" → ")}`;
    meta.appendChild(info);
  }
  el.appendChild(meta);
  return el;
}

function typingEl() {
  const el = document.createElement("div");
  el.className = "msg bot";
  el.innerHTML = `<div class="typing"><i></i><i></i><i></i></div>`;
  return el;
}

async function send(text) {
  text = text.trim();
  if (!text || busy) return;
  let chat = active();
  if (!chat) {
    chat = { id: uid(), title: text.length > 48 ? text.slice(0, 46) + "…" : text, sessionId: null, messages: [], updated: Date.now() };
    chats.push(chat);
    activeId = chat.id;
  }
  chat.messages.push({ role: "user", text });
  chat.updated = Date.now();
  busy = true;
  $("#send").disabled = true;
  save();
  renderAll();
  try {
    const r = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: chat.sessionId }),
    });
    if (!r.ok) throw new Error(`Server error ${r.status}`);
    const d = await r.json();
    chat.sessionId = d.session_id;
    chat.messages.push(d.error && !d.answer
      ? { role: "bot", text: d.error, error: true }
      : { role: "bot", text: d.answer || "_(no answer)_", sources: d.sources, meta: { seconds: d.seconds, agents: d.agents } });
  } catch (e) {
    chat.messages.push({ role: "bot", text: `Could not reach the helpdesk: ${e.message}`, error: true });
  }
  busy = false;
  $("#send").disabled = false;
  chat.updated = Date.now();
  save();
  if (activeId === chat.id) renderAll(); else renderList();
}

// ---------- sources ----------
function renderSources(focus) {
  const box = $("#tab-sources");
  const chat = active();
  const groups = [];
  (chat?.messages || []).forEach((m, i) => {
    if (m.role === "bot" && m.sources?.length) groups.push({ i, q: chat.messages[i - 1]?.text || "", sources: m.sources });
  });
  if (!groups.length) {
    box.innerHTML = `<div class="src-empty">Documents the helpdesk used will show up here.</div>`;
    return;
  }
  const docs = baseGraph ? Object.fromEntries(baseGraph.nodes.map((n) => [n.id, n])) : {};
  box.innerHTML = groups.reverse().map((g) => `
    <div class="src-group">
      <div class="src-q" data-i="${g.i}" title="${esc(g.q)}">↳ ${esc(g.q)}</div>
      ${g.sources.map((s) => {
        const doc = docs[s.doc_id];
        const title = s.doc_id ? `<a href="/api/doc/${s.doc_id}" target="_blank" rel="noopener">${esc(s.label)}</a>` : esc(s.label);
        return `<div class="src${focus && focus.i === g.i && focus.doc === s.doc_id ? " focus" : ""}" data-doc="${s.doc_id || ""}">
          <div class="src-head">
            <span class="src-id">${s.doc_id || "csv"}</span>
            <span class="src-title">${title}</span>
            ${s.cited ? `<span class="badge cited">cited</span>` : ""}
            ${doc?.status === "superseded" ? `<span class="badge superseded">superseded</span>` : ""}
          </div>
          ${s.snippets.map((t) => `<div class="src-snip">${esc(t.replace(/^\[[^\]]*\]\s*/, ""))}</div>`).join("")}
        </div>`;
      }).join("")}
    </div>`).join("");
  box.querySelectorAll(".src-snip").forEach((el) => (el.onclick = () => el.classList.toggle("open")));
  box.querySelectorAll(".src-q").forEach((el) => (el.onclick = () => scrollToMessage(+el.dataset.i)));
  box.querySelector(".src.focus")?.scrollIntoView({ block: "center" });
}

function focusSource(i, docId) {
  setPanel(true);
  setTab("sources");
  renderSources({ i, doc: docId });
}

function scrollToMessage(i) {
  const el = document.querySelector(`.msg[data-index="${i}"]`);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.remove("highlight");
  void el.offsetWidth;
  el.classList.add("highlight");
}

// ---------- graph ----------
const graphSmall = new GraphView($("#graph"), { onClick: onGraphClick });
const graphBig = new GraphView($("#graphBig"), { onClick: onGraphClick, labels: true });

function graphData(scope) {
  if (!baseGraph) return null;
  const chat = active();
  const nodes = baseGraph.nodes.map((n) => ({ ...n }));
  const links = baseGraph.links.map((l) => ({ ...l }));
  const touched = new Set();
  (chat?.messages || []).forEach((m, i) => {
    const docs = (m.sources || []).filter((s) => s.doc_id);
    if (m.role !== "bot" || !docs.length) return;
    const q = chat.messages[i - 1]?.text || "question";
    nodes.push({ id: `q${i}`, type: "question", title: q, index: i });
    docs.forEach((s) => {
      touched.add(s.doc_id);
      links.push({ source: `q${i}`, target: s.doc_id, kind: s.cited ? "cites" : "retrieved" });
    });
  });
  if (scope === "global") return { nodes, links, touched };
  if (!touched.size) return { nodes: [], links: [], touched };
  // local graph (as in Quartz): the chat's questions, their documents, and one hop out from those
  const keep = new Set([...touched, ...nodes.filter((n) => n.type === "question").map((n) => n.id)]);
  links.forEach((l) => {
    if (touched.has(l.source)) keep.add(l.target);
    if (touched.has(l.target)) keep.add(l.source);
  });
  return {
    nodes: nodes.filter((n) => keep.has(n.id)),
    links: links.filter((l) => keep.has(l.source) && keep.has(l.target)),
    touched,
  };
}

function renderGraph() {
  if (panelTab === "graph") {
    const d = graphData(graphScope);
    graphSmall.render(d, graphScope === "local" ? "Ask a question and the documents behind the answer will appear here." : "");
  }
  if (!$("#overlay").classList.contains("hidden")) graphBig.render(graphData("global"));
}

function onGraphClick(node) {
  if (node.type === "question") {
    $("#overlay").classList.add("hidden");
    scrollToMessage(node.index);
  } else if (node.type === "doc") {
    window.open(`/api/doc/${node.id}`, "_blank", "noopener");
  }
}

function renderLegend() {
  $("#legend").innerHTML = Object.entries(GraphView.CATEGORY_COLORS)
    .map(([k, c]) => `<span><i style="background:${c}"></i>${k.replace("_", " ")}</span>`).join("")
    + `<span><i style="background:var(--accent);border-radius:2px"></i>question</span>`
    + `<span><i class="line"></i>amended by</span>`;
}

// ---------- panel ----------
function setPanel(open) {
  document.querySelector(".app").classList.toggle("panel-closed", !open);
  if (open) renderGraph();
}
function setTab(tab) {
  panelTab = tab;
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === tab));
  $("#tab-sources").classList.toggle("hidden", tab !== "sources");
  $("#tab-graph").classList.toggle("hidden", tab !== "graph");
  renderGraph();
}

// ---------- wiring ----------
$("#newChat").onclick = newChat;
$("#composer").onsubmit = (e) => {
  e.preventDefault();
  const v = $("#input").value;
  $("#input").value = "";
  autosize();
  send(v);
};
const autosize = () => {
  const t = $("#input");
  t.style.height = "auto";
  t.style.height = Math.min(t.scrollHeight, 180) + "px";
};
$("#input").oninput = autosize;
$("#input").onkeydown = (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    $("#composer").requestSubmit();
  }
};
document.querySelectorAll(".tab").forEach((t) => (t.onclick = () => setTab(t.dataset.tab)));
document.querySelectorAll(".seg-btn").forEach((b) => (b.onclick = () => {
  graphScope = b.dataset.scope;
  document.querySelectorAll(".seg-btn").forEach((x) => x.classList.toggle("active", x === b));
  renderGraph();
}));
$("#togglePanel").onclick = () => setPanel(document.querySelector(".app").classList.contains("panel-closed"));
$("#toggleSidebar").onclick = () => $("#sidebar").classList.toggle("open");
$("#expandGraph").onclick = () => {
  $("#overlay").classList.remove("hidden");
  graphBig.render(graphData("global"));
};
$("#closeOverlay").onclick = () => $("#overlay").classList.add("hidden");
$("#overlay").onclick = (e) => { if (e.target.id === "overlay") $("#overlay").classList.add("hidden"); };
document.addEventListener("keydown", (e) => { if (e.key === "Escape") $("#overlay").classList.add("hidden"); });
window.addEventListener("resize", () => renderGraph());

if (matchMedia("(max-width: 1000px)").matches) setPanel(false);
renderLegend();
renderAll();

fetch("/api/info").then((r) => r.json()).then((d) => {
  $("#modelInfo").textContent = `${d.mode} · ${d.model.replace("ollama_chat/", "")}`;
}).catch(() => ($("#modelInfo").textContent = "server offline"));
fetch("/api/graph").then((r) => r.json()).then((d) => {
  baseGraph = d;
  renderSources();
  renderGraph();
});
