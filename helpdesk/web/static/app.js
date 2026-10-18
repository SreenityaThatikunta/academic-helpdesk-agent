// Chat UI: chats live in localStorage; the server keeps the agent session for each chat.
const $ = (s) => document.querySelector(s);
const STORE = "helpdesk.chats.v1";
const SUGGESTIONS = [
  "What is the attendance requirement to sit in the Major exam?",
  "What is the slot for Autonomous Systems?",
  "How many 400-level electives has the Humanities department floated this semester?",
  "Write an email to the instructor of CSL7650 that I need leave for 2 days",
];
const TOOL_LABELS = {
  search_documents: "Searching documents",
  search_documents_all: "Searching documents",
  get_slot: "Looking up the time table",
  lookup_course: "Looking up the course",
  list_courses: "Listing courses",
  get_instructor_email: "Finding the instructor",
  draft_email: "Drafting the email",
  log_unanswered_question: "Forwarding to a human",
};
const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"];

let chats = load();
let activeId = (() => { try { return localStorage.getItem(STORE + ".active"); } catch { return null; } })();
let busy = false;
let live = null; // the question being answered: {chatId, q, trace, docs, t0}
let baseGraph = null;
let graphScope = "local";
let mode = (() => { try { return localStorage.getItem(STORE + ".mode"); } catch { return null; } })();
let unanswered = [];
let unansweredFilter = "open";
let panelTab = "sources";

function load() {
  try { return JSON.parse(localStorage.getItem(STORE)) || []; } catch { return []; }
}
function save() {
  try { localStorage.setItem(STORE, JSON.stringify(chats)); } catch {}
}
const active = () => chats.find((c) => c.id === activeId);
const uid = () => Math.random().toString(36).slice(2, 10);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const md = (s) => DOMPurify.sanitize(marked.parse(s || ""));
const AGENT_NAMES = { helpdesk_orchestrator: "router", academic_helpdesk: "agent" };
const agentName = (a) => AGENT_NAMES[a] || String(a || "").replace(/_agent$/, "");

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
  let lastMode = null;
  chat.messages.forEach((m, i) => {
    // a divider where the chat switches between single and multi agent (each keeps its own memory)
    const next = m.role === "user" ? (chat.messages[i + 1]?.meta?.mode || (i === chat.messages.length - 1 && live ? live.mode : null)) : null;
    if (next && lastMode && next !== lastMode) box.appendChild(dividerEl(next));
    if (next) lastMode = next;
    box.appendChild(messageEl(m, i, i === chat.messages.length - 1));
  });
  if (live && live.chatId === chat.id) box.appendChild(liveEl());
  box.scrollTop = box.scrollHeight;
}

const MODE_LABELS = { single: "single agent", multi: "multi-agent" };

function dividerEl(m) {
  const el = document.createElement("div");
  el.className = "divider";
  el.innerHTML = `<span>Switched to ${MODE_LABELS[m] || m} · it has its own memory of this chat</span>`;
  return el;
}

function messageEl(m, i, isLast = false) {
  const el = document.createElement("div");
  el.className = `msg ${m.role}` + (m.error ? " error" : "");
  el.dataset.index = i;
  if (m.role === "user") {
    el.innerHTML = `<div class="bubble">${esc(m.text)}</div>`;
    return el;
  }
  const route = (m.meta?.agents || []).map(agentName).join(" → ");
  const n = (m.trace || []).filter((s) => !s.handoff).length;
  const head = [n ? `${n} step${n === 1 ? "" : "s"}` : "no tools", m.meta && `${m.meta.seconds}s`, route].filter(Boolean).map(esc).join(" · ");
  if (m.trace?.length) {
    const d = document.createElement("details");
    d.className = "trace";
    d.innerHTML = `<summary>${head}</summary>${traceHtml(m.trace)}`;
    el.appendChild(d);
  } else if (m.meta) {
    el.insertAdjacentHTML("beforeend", `<div class="trace trace-plain">${head}</div>`);
  }
  const body = document.createElement("div");
  body.className = "body";
  // the email card shows the draft (editable), so drop the same draft quoted in the answer text
  const text = (m.cards || []).some((c) => c.kind === "email")
    ? m.text.replace(/```[^\n]*\n(?:To|Subject):[\s\S]*?```\n?/g, "")
    : m.text;
  body.innerHTML = m.error ? esc(m.text) : md(text);
  el.appendChild(body);
  (m.cards || []).forEach((c) => {
    const card = cardEl(c, isLast);
    if (card) el.appendChild(card);
  });
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
  el.appendChild(meta);
  return el;
}

// ---------- live trace ----------
function traceHtml(trace) {
  return `<div class="steps">${trace.map((s) => {
    if (s.handoff) {
      return `<div class="step handoff"><span class="step-icon"></span><span class="step-agent">${esc(agentName(s.agent))}</span>
        <span class="step-label">Handing off to <b>${esc(agentName(s.to))}</b></span></div>`;
    }
    const extra = Object.entries(s.extra || {}).map(([k, v]) => `<span class="step-extra">${esc(k)}: ${esc(v)}</span>`).join("");
    return `<div class="step ${s.status}"><span class="step-icon"></span><span class="step-agent">${esc(agentName(s.agent))}</span>
      <span class="step-label">${esc(TOOL_LABELS[s.name] || s.name)}</span>${s.arg ? `<code>${esc(s.arg)}</code>` : ""}${extra}
      ${s.summary ? `<div class="step-sum">${esc(s.summary)}</div>` : ""}</div>`;
  }).join("")}</div>`;
}

function liveEl() {
  const el = document.createElement("div");
  el.className = "msg bot live";
  const status = !live.started ? "Waiting for the model…" : live.trace.length ? "Working" : "Thinking";
  el.innerHTML = `<div class="live-head"><span class="spinner"></span><span>${status}</span><span class="live-time"></span></div>
    ${live.trace.length ? traceHtml(live.trace) : ""}`;
  return el;
}

function updateLive() {
  const box = $("#messages");
  const old = box.querySelector(".msg.live");
  if (!old || !live) return;
  const stick = box.scrollHeight - box.scrollTop - box.clientHeight < 80;
  old.replaceWith(liveEl());
  tickLive();
  if (stick) box.scrollTop = box.scrollHeight;
}

function tickLive() {
  const t = document.querySelector(".msg.live .live-time");
  if (t && live) t.textContent = `${((performance.now() - live.t0) / 1000).toFixed(1)}s`;
}
setInterval(tickLive, 100);

function onStreamEvent(ev) {
  if (ev.type === "start") live.started = true;
  else if (ev.type === "call") {
    live.started = true;
    if (ev.step === "handoff") live.trace.push({ handoff: true, agent: ev.agent, to: ev.to });
    else live.trace.push({ agent: ev.agent, name: ev.name, arg: ev.arg, extra: ev.extra, status: "running" });
  } else if (ev.type === "result") {
    const step = [...live.trace].reverse().find((s) => s.name === ev.name && s.status === "running");
    if (step) Object.assign(step, { status: ev.ok ? "ok" : "fail", summary: ev.summary });
    (ev.docs || []).forEach((d) => live.docs.add(d));
    if (ev.docs?.length) renderGraph();
  }
  if (live.chatId === activeId) updateLive();
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
  live = { chatId: chat.id, q: text, trace: [], docs: new Set(), t0: performance.now(), started: false, mode };
  if (chat.sessionId && !chat.sessions) chat.sessions = { single: chat.sessionId }; // chats saved before modes
  $("#send").disabled = true;
  save();
  renderAll();
  let done = null;
  try {
    const r = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: chat.sessions?.[mode] || null, mode }),
    });
    if (!r.ok || !r.body) throw new Error(`Server error ${r.status}`);
    const reader = r.body.pipeThrough(new TextDecoderStream()).getReader();
    let buf = "";
    while (!done) {
      const { value, done: end } = await reader.read();
      if (end) break;
      buf += value;
      let cut;
      while ((cut = buf.indexOf("\n\n")) >= 0) {
        const line = buf.slice(0, cut).trim();
        buf = buf.slice(cut + 2);
        if (!line.startsWith("data:")) continue;
        const ev = JSON.parse(line.slice(5));
        if (ev.type === "done" || ev.type === "error") { done = ev; break; }
        onStreamEvent(ev);
      }
    }
    if (!done) throw new Error("connection closed before the answer arrived");
    if (done.type === "error") throw new Error(done.message);
    chat.sessions = { ...(chat.sessions || {}), [done.mode]: done.session_id };
    const trace = live.trace.map((s) => (s.status === "running" ? { ...s, status: "ok" } : s));
    chat.messages.push(done.error && !done.answer
      ? { role: "bot", text: done.error, error: true, trace }
      : { role: "bot", text: done.answer || "_(no answer)_", sources: done.sources, cards: done.cards, trace,
          meta: { seconds: done.seconds, agents: done.agents, mode: done.mode } });
    if (done.cards?.some((c) => c.kind === "ticket")) loadUnanswered();
  } catch (e) {
    chat.messages.push({ role: "bot", text: `Could not reach the helpdesk: ${e.message}`, error: true, trace: live.trace });
  }
  // the live question node becomes the answered one: keep its place in the graph
  const qi = chat.messages.length - 1;
  [graphSmall, graphBig].forEach((g) => g.positions.has("qlive") && g.positions.set(`q${qi}`, g.positions.get("qlive")));
  busy = false;
  live = null;
  $("#send").disabled = false;
  chat.updated = Date.now();
  save();
  if (activeId === chat.id) renderAll(); else renderList();
}

// ---------- answer cards ----------
function parseExamDate(s) {
  const d = new Date(String(s).split(",")[0]); // "22 November 2026, Sunday"
  return isNaN(d) ? null : d;
}
function countdown(d) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Math.round((d - today) / 86400000);
  return days < 0 ? "done" : days === 0 ? "today" : days === 1 ? "tomorrow" : `in ${days} days`;
}

function cardEl(c, isLast) {
  const el = document.createElement("div");
  el.className = `card card-${c.kind}`;
  if (c.kind === "ticket") {
    el.innerHTML = `
      <div class="ticket-icon">↗</div>
      <div class="ticket-text">
        <div class="card-title">Forwarded to the academic office</div>
        <div class="card-sub">${c.ticket_id ? `Ticket <span class="code">${esc(c.ticket_id)}</span> · ` : ""}a person will follow up instead of the helpdesk guessing</div>
      </div>
      <button class="btn">View queue</button>`;
    el.querySelector(".btn").onclick = () => { setPanel(true); setTab("unanswered"); };
    return el;
  }
  if (c.kind === "clarify") {
    const pick = { branch: null, year: null };
    el.innerHTML = `
      <div class="pick-row"><span class="pick-label">Programme</span>${c.branches.map((b) => `<button class="pick" data-k="branch" data-v="${esc(b)}">B.Tech ${esc(b)}</button>`).join("")}</div>
      <div class="pick-row"><span class="pick-label">Joined in</span>${c.years.map((y) => `<button class="pick" data-k="year" data-v="${y}">${y}</button>`).join("")}</div>
      <div class="card-actions"><button class="btn primary go" disabled>Answer</button><span class="muted">or type your answer below</span></div>`;
    const go = el.querySelector(".go");
    el.querySelectorAll(".pick").forEach((b) => (b.onclick = () => {
      pick[b.dataset.k] = b.dataset.v;
      el.querySelectorAll(`.pick[data-k="${b.dataset.k}"]`).forEach((x) => x.classList.toggle("on", x === b));
      go.disabled = !(pick.branch && pick.year);
    }));
    go.onclick = () => send(`I am in B.Tech ${pick.branch} and joined in ${pick.year}.`);
    if (!isLast || busy) el.querySelectorAll("button").forEach((b) => (b.disabled = true));
    return el;
  }
  if (c.kind === "suggest") {
    el.innerHTML = `<div class="pick-row"><span class="pick-label">Did you mean</span>${c.options.map((o) =>
      `<button class="pick" data-code="${esc(o.code)}" data-name="${esc(o.name)}"><span class="code">${esc(o.code)}</span> ${esc(o.name)}</button>`).join("")}</div>`;
    el.querySelectorAll(".pick").forEach((b) => (b.onclick = () => send(`Yes, I meant ${b.dataset.code} (${b.dataset.name}).`)));
    if (!isLast || busy) el.querySelectorAll("button").forEach((b) => (b.disabled = true));
    return el;
  }
  if (c.kind === "course") {
    const byDay = Object.fromEntries(DAYS.map((d) => [d, []]));
    (c.weekly_schedule || []).forEach((s) => {
      const [day, ...t] = s.split(" ");
      if (byDay[day]) byDay[day].push(t.join(" ").replace(/\s*-\s*/, "–"));
    });
    const facts = [
      c.credits && `${c.credits} credits`, c.ltp && `L-T-P ${c.ltp}`, c.slots?.length && `slot ${c.slots.join(", ")}`,
      c.classrooms?.length && c.classrooms.join(", "), c.ih_group,
    ].filter(Boolean);
    el.innerHTML = `
      <div class="card-head"><span class="code">${esc(c.course_code)}</span><span class="card-title">${esc(c.course_name)}</span></div>
      <div class="card-sub">${esc(c.department)}${c.instructors?.length ? ` · ${esc(c.instructors.join(", "))}` : ""}</div>
      <div class="facts">${facts.map((f) => `<span>${esc(f)}</span>`).join("")}</div>
      ${c.weekly_schedule ? `<div class="week">${DAYS.map((d) => `<div class="day${byDay[d].length ? " on" : ""}">
          <div class="day-name">${d}</div>${byDay[d].map((t) => `<div class="slot-time">${esc(t)}</div>`).join("") || `<div class="slot-none">·</div>`}
        </div>`).join("")}</div>` : ""}
      ${(c.exams || []).length ? `<div class="exams">${c.exams.map((x) => {
        const d = parseExamDate(x.date);
        const when = d ? countdown(d) : "";
        return `<div class="exam${when === "done" ? " past" : ""}"><span class="exam-name">${esc(x.exam)}</span>
          <span>${esc(x.date)}</span><span class="muted">${esc(x.time)}</span>
          ${when ? `<span class="when">${when}</span>` : ""}${x.status === "tentative" ? `<span class="muted">tentative</span>` : ""}</div>`;
      }).join("")}</div>` : ""}`;
    return el;
  }
  if (c.kind === "email") {
    el.innerHTML = `
      <div class="card-head"><span class="card-title">Email draft</span><span class="badge draft">not sent</span></div>
      <label>To<input class="f-to" value="${esc(c.to)}"></label>
      ${c.cc ? `<label>Cc<input class="f-cc" value="${esc(c.cc)}"></label>` : ""}
      <label>Subject<input class="f-subject" value="${esc(c.subject)}"></label>
      <textarea class="f-body" rows="8">${esc(c.body)}</textarea>
      <div class="card-actions">
        <button class="btn copy">Copy</button>
        <button class="btn primary mail">Open in mail app</button>
        ${c.path ? `<span class="muted">saved to ${esc(c.path)}</span>` : ""}
      </div>`;
    const val = (s) => el.querySelector(s)?.value || "";
    el.querySelector(".copy").onclick = async (e) => {
      const text = `To: ${val(".f-to")}\n${val(".f-cc") ? `Cc: ${val(".f-cc")}\n` : ""}Subject: ${val(".f-subject")}\n\n${val(".f-body")}`;
      try { await navigator.clipboard.writeText(text); e.target.textContent = "Copied"; } catch { e.target.textContent = "Copy failed"; }
      setTimeout(() => (e.target.textContent = "Copy"), 1500);
    };
    el.querySelector(".mail").onclick = () => {
      const q = new URLSearchParams({ subject: val(".f-subject"), body: val(".f-body"), ...(val(".f-cc") ? { cc: val(".f-cc") } : {}) });
      location.href = `mailto:${encodeURIComponent(val(".f-to"))}?${q.toString().replace(/\+/g, "%20")}`;
    };
    return el;
  }
  if (c.kind === "courses") {
    const filters = Object.values(c.filters || {}).join(" · ");
    el.innerHTML = `
      <div class="card-head"><span class="card-title">${c.count} course${c.count === 1 ? "" : "s"}</span>
        <input class="filter" placeholder="Filter…"></div>
      ${filters ? `<div class="card-sub">${esc(filters)}</div>` : ""}
      <div class="table-wrap"><table><thead><tr><th>Code</th><th>Course</th><th>Slot</th><th>Instructors</th></tr></thead>
        <tbody>${c.courses.map((r) => `<tr><td class="code">${esc(r.course_code)}</td>
          <td>${esc(r.course_name)}${r.ih_group ? ` <span class="badge">${esc(r.ih_group)}</span>` : ""}<div class="muted">${esc(r.department)}</div></td>
          <td>${esc((r.slots || []).join(", "))}</td><td>${esc((r.instructors || []).join(", "))}</td></tr>`).join("")}</tbody></table></div>`;
    el.querySelector(".filter").oninput = (e) => {
      const q = e.target.value.toLowerCase();
      el.querySelectorAll("tbody tr").forEach((tr) => (tr.style.display = tr.textContent.toLowerCase().includes(q) ? "" : "none"));
    };
    return el;
  }
  return null;
}

// ---------- unanswered ----------
async function loadUnanswered() {
  try { unanswered = await (await fetch("/api/unanswered")).json(); } catch { unanswered = []; }
  const open = unanswered.filter((e) => e.status === "open").length;
  $("#openCount").textContent = open;
  $("#openCount").classList.toggle("hidden", !open);
  if (panelTab === "unanswered") renderUnanswered();
}

function ago(iso) {
  const s = (Date.now() - new Date(iso)) / 1000;
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

function renderUnanswered() {
  const box = $("#tab-unanswered");
  const mine = new Set((active()?.messages || []).flatMap((m) => (m.cards || []).filter((c) => c.kind === "ticket").map((c) => c.ticket_id)));
  const counts = { open: 0, resolved: 0 };
  unanswered.forEach((e) => (counts[e.status] = (counts[e.status] || 0) + 1));
  const rows = unanswered.filter((e) => unansweredFilter === "all" || e.status === unansweredFilter);
  box.innerHTML = `
    <div class="uq-head">
      <div class="seg">${["open", "resolved", "all"].map((f) => `<button class="seg-btn${f === unansweredFilter ? " active" : ""}" data-f="${f}">
        ${f[0].toUpperCase() + f.slice(1)}${f !== "all" ? ` <span class="muted">${counts[f] || 0}</span>` : ""}</button>`).join("")}</div>
    </div>
    <p class="uq-note">Questions the helpdesk refused instead of guessing. They are logged to <code>logs/unanswered.jsonl</code> for the academic office.</p>
    ${rows.length ? rows.map((e) => `
      <div class="uq${mine.has(e.id) ? " mine" : ""}">
        <div class="uq-q">${esc(e.question)}</div>
        <div class="uq-meta"><span class="code">${esc(e.id)}</span><span>${ago(e.timestamp)}</span>
          <span class="badge ${e.status}">${esc(e.status)}</span>${mine.has(e.id) ? `<span class="badge cited">this chat</span>` : ""}</div>
        <div class="uq-reason">${esc(e.reason)}</div>
        ${e.resolution ? `<div class="uq-res">↳ ${esc(e.resolution)}</div>` : ""}
      </div>`).join("") : `<div class="src-empty">Nothing here.</div>`}`;
  box.querySelectorAll(".seg-btn").forEach((b) => (b.onclick = () => { unansweredFilter = b.dataset.f; renderUnanswered(); }));
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
  const pulse = new Set();
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
  // the question being answered right now, linked to documents as the tools return them
  if (live && chat && live.chatId === chat.id && live.docs.size) {
    nodes.push({ id: "qlive", type: "question", title: live.q, pending: true });
    pulse.add("qlive");
    live.docs.forEach((d) => {
      touched.add(d);
      pulse.add(d);
      links.push({ source: "qlive", target: d, kind: "retrieved" });
    });
  }
  if (scope === "global") return { nodes, links, touched, pulse };
  if (!touched.size) return { nodes: [], links: [], touched, pulse };
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
    pulse,
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
    if (node.pending) return;
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
  $("#tab-unanswered").classList.toggle("hidden", tab !== "unanswered");
  if (tab === "unanswered") loadUnanswered();
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
function setMode(m) {
  mode = m;
  try { localStorage.setItem(STORE + ".mode", m); } catch {}
  document.querySelectorAll("#modeSeg .seg-btn").forEach((b) => b.classList.toggle("active", b.dataset.mode === m));
}
document.querySelectorAll("#modeSeg .seg-btn").forEach((b) => (b.onclick = () => setMode(b.dataset.mode)));
document.querySelectorAll("#tab-graph .seg-btn").forEach((b) => (b.onclick = () => {
  graphScope = b.dataset.scope;
  document.querySelectorAll("#tab-graph .seg-btn").forEach((x) => x.classList.toggle("active", x === b));
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
  $("#modelInfo").textContent = d.model.replace("ollama_chat/", "");
  setMode(d.modes.includes(mode) ? mode : d.mode);
}).catch(() => ($("#modelInfo").textContent = "server offline"));
loadUnanswered();
fetch("/api/graph").then((r) => r.json()).then((d) => {
  baseGraph = d;
  renderSources();
  renderGraph();
});
