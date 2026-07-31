// Genel yapılandırma
let config = {
  USER_NAME: localStorage.getItem("meil-user-name") || "Kullanıcı",
};

let state = {
  emails: [],
  counts: {},
  categories: [],
  accounts: [],
  calendars: [],
  selectedId: null,
  activeCategory: "",
  activeAccount: "",
  activeView: "inbox",
  views: {},
  search: "",
  cal: {
    year: new Date().getFullYear(),
    month: new Date().getMonth(),      // 0-11
    selected: null,                    // "YYYY-MM-DD"
    events: [],
  },
};

const $ = (sel) => document.querySelector(sel);

const AVATAR_COLORS = ["#0f8a6d", "#d64550", "#2563eb", "#b06d0a", "#7c3aed", "#0e7490", "#be5a0e"];

function avatarColor(text) {
  let h = 0;
  for (const ch of text || "?") h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return AVATAR_COLORS[h % AVATAR_COLORS.length];
}

function initials(name, email) {
  const src = (name || email || "?").trim();
  const parts = src.split(/\s+/).map((p) => p.replace(/[^\p{L}\p{N}]/gu, "")).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return "?";
}

function avatarHtml(name, email, cls = "") {
  return `<div class="avatar ${cls}" style="background:${avatarColor(email || name)}">${esc(initials(name, email))}</div>`;
}


// Posta SVG ikonları (Lucide tarzı — emoji yerine, skill kuralı)
const MI = {
  chevron: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="m6 9 6 6 6-6"/></svg>',
  inbox: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5 5h14l3 7v6a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1v-6l3-7Z"/></svg>',
  star: (on) => `<svg width="13" height="13" viewBox="0 0 24 24" fill="${on ? "currentColor" : "none"}" stroke="currentColor" stroke-width="2"><path d="m12 3 2.7 5.6 6.3.9-4.5 4.4 1 6.1L12 17.2 6.5 20l1-6.1L3 9.5l6.3-.9L12 3Z"/></svg>`,
  hourglass: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 3h12M6 21h12M8 3v4l4 5 4-5V3M8 21v-4l4-5 4 5v4"/></svg>',
  clock: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>',
  archive: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8M10 12h4"/></svg>',
  unarchive: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5 5h14l3 7v6a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1v-6l3-7Z"/></svg>',
  mailUnread: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 8 9 6 9-6"/><circle cx="19" cy="6" r="3" fill="currentColor" stroke="none"/></svg>',
  send: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m3 3 18 9-18 9 4-9-4-9ZM7 12h14"/></svg>',
  refresh: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-2.6-6.3"/><path d="M21 3v6h-6"/></svg>',
  paperclip: '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m21 12-8.5 8.5a5 5 0 0 1-7-7L14 5a3.5 3.5 0 0 1 5 5l-8.5 8.5a2 2 0 0 1-3-3L16 7"/></svg>',
  calendar: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>',
  pin: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-1px"><path d="M12 21s-7-5.5-7-11a7 7 0 0 1 14 0c0 5.5-7 11-7 11Z"/><circle cx="12" cy="10" r="2.5"/></svg>',
  sparkle: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3v3m0 12v3m9-9h-3M6 12H3m14.5-6.5-2 2m-9 9-2 2m13 0-2-2m-9-9-2-2"/><circle cx="12" cy="12" r="3"/></svg>',
  moon: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/></svg>',
  sun: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
  x: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M18 6 6 18M6 6l12 12"/></svg>',
  thread: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 9a2 2 0 0 1-2 2H6l-4 4V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2Z"/><path d="M18 9h2a2 2 0 0 1 2 2v11l-4-4h-6a2 2 0 0 1-2-2v-1"/></svg>',
};

function toast(msg, isError = false) {
  const el = $("#toast");
  el.textContent = msg;
  el.className = "show" + (isError ? " error" : "");
  setTimeout(() => (el.className = ""), 4500);
}

const RESTART_MSG =
  "Sunucu eski sürümde çalışıyor — uvicorn'u durdurup yeniden başlatın " +
  "(veya ./start.sh kullanın).";

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (res.status === 405) throw new Error(RESTART_MSG);
  if (res.status === 401 && !path.startsWith("/api/auth/")) {
    showAuthOverlay("login");           // oturum düşmüş — giriş ekranını aç
    throw new Error("Giriş gerekli");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Hata: ${res.status}`);
  return data;
}

function esc(s) {
  const div = document.createElement("div");
  div.textContent = s ?? "";
  return div.innerHTML;
}

function formatDate(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    const now = new Date();
    if (d.toDateString() === now.toDateString())
      return d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
    return d.toLocaleDateString("tr-TR", { day: "2-digit", month: "short" });
  } catch { return iso; }
}

function formatDateFull(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString("tr-TR", {
      day: "2-digit", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
}

/* Mail gövdesini okunur HTML'e çevirir:
   - metin kaçışlanır (XSS yok), bağlantılar tıklanabilir olur
   - alıntılanan kısım (">" ile başlayan satırlar ve "-----Original Message-----"
     benzeri ayraçtan sonrası) katlanır — gerçek mail uygulamalarındaki gibi */
function formatBody(text) {
  const raw = (text || "").trim();
  if (!raw) return '<p class="mail-empty">(içerik yok)</p>';

  const linkify = (s) => esc(s).replace(
    /\b(https?:\/\/[^\s<]+)/g,
    '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
  );

  const lines = raw.split("\n");
  const sepRe = /^\s*(-{2,}\s*(original message|forwarded message|iletilen ileti|özgün ileti)\s*-{2,}|_{5,})/i;
  const onRe = /^\s*(On .+ wrote:|.+ tarihinde .+ (yazdı|şunu yazdı):)\s*$/i;

  let cut = -1;
  for (let i = 0; i < lines.length; i++) {
    if (sepRe.test(lines[i]) || onRe.test(lines[i])) { cut = i; break; }
    if (lines[i].startsWith(">") && i > 0) { cut = i; break; }
  }

  const main = (cut === -1 ? lines : lines.slice(0, cut)).join("\n").trim();
  const quoted = cut === -1 ? "" : lines.slice(cut).join("\n").trim();

  let html = `<div class="mb-main">${linkify(main)}</div>`;
  if (quoted) {
    html += `<details class="mb-quote"><summary>Alıntılanan yazışmayı göster</summary>
      <div class="mb-quote-body">${linkify(quoted)}</div></details>`;
  }
  return html;
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1048576).toFixed(1) + " MB";
}

// ---- Tema ----

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  $("#theme-toggle").innerHTML = theme === "dark" ? MI.sun : MI.moon;
  localStorage.setItem("meil-theme", theme);
}
$("#theme-toggle").onclick = () => {
  applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
};
applyTheme(
  localStorage.getItem("meil-theme") ||
  (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
);

// ---- Klavye kısayolu: / ile arama ----

document.addEventListener("keydown", (e) => {
  if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) {
    e.preventDefault();
    $("#search-input").focus();
  }
});

// ---- Görünüm geçişi ----

document.querySelectorAll(".rail-btn").forEach((btn) => {
  btn.onclick = () => {
    document.querySelectorAll(".rail-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const view = btn.dataset.view;
    ["inbox", "calendar", "dataroom", "bulk", "accounts"].forEach((v) => {
      const elem = $(`#view-${v}`);
      if (!elem) { console.error(`View element not found: #view-${v}`); return; }
      elem.style.display = v === view ? "flex" : "none";
    });
    if (view === "calendar") loadCalendar();
    if (view === "dataroom") loadDataroom();
    if (view === "bulk") loadBulk();
    if (view === "accounts") loadAccounts();
  };
});

// ---- Posta ----

const VIEW_LABELS = {
  inbox: [MI.inbox, "Gelen"], starred: [MI.star(false), "Yıldızlı"], awaiting: [MI.hourglass, "Bekleyen"],
  snoozed: [MI.clock, "Ertelenen"], archived: [MI.archive, "Arşiv"],
};
const VIEW_TITLES = {
  inbox: "Gelen Kutusu", starred: "Yıldızlı", awaiting: "Yanıt Bekleyen",
  snoozed: "Ertelenen", archived: "Arşiv",
};

async function loadEmails() {
  const params = new URLSearchParams();
  if (state.activeCategory) params.set("category", state.activeCategory);
  if (state.activeAccount) params.set("account_id", state.activeAccount);
  params.set("view", state.activeView || "inbox");
  const data = await api(`/api/emails?${params}`);
  state.emails = data.emails;
  state.counts = data.counts;
  state.views = data.views || {};
  state.categories = data.categories;
  renderViewTabs();
  renderFilters();
  renderList();
  renderUnreadBadge();
}

function renderViewTabs() {
  const holder = $("#view-tabs");
  const active = state.activeView || "inbox";
  $("#view-title").textContent = VIEW_TITLES[active];
  holder.innerHTML = Object.entries(VIEW_LABELS).map(([view, [icon, label]]) => {
    const n = state.views[view] || 0;
    return `<button class="view-tab${view === active ? " active" : ""}" data-vt="${view}" title="${VIEW_TITLES[view]}">
      ${icon} ${label}${n ? ` <span class="vn">${n}</span>` : ""}
    </button>`;
  }).join("");
  holder.querySelectorAll(".view-tab").forEach((tab) => {
    tab.onclick = () => { state.activeView = tab.dataset.vt; loadEmails(); };
  });
}

function renderUnreadBadge() {
  const railBtn = document.querySelector('.rail-btn[data-view="inbox"] .rail-tile');
  if (!railBtn) return;
  let badge = railBtn.querySelector(".rail-badge");
  const n = state.views.unread || 0;
  if (!n) { if (badge) badge.remove(); return; }
  if (!badge) {
    badge = document.createElement("span");
    badge.className = "rail-badge";
    railBtn.style.position = "relative";
    railBtn.appendChild(badge);
  }
  badge.textContent = n > 99 ? "99+" : n;
}

function renderFilters() {
  const total = Object.values(state.counts).reduce((a, b) => a + b, 0);
  const chips = $("#category-chips");
  const chipHtml = (value, label, n) =>
    `<button class="chip${state.activeCategory === value ? " active" : ""}" data-cat="${esc(value)}">${esc(label)}${n ? `<span class="n">${n}</span>` : ""}</button>`;
  chips.innerHTML =
    chipHtml("", "Tümü", total) +
    state.categories
      .filter((c) => state.counts[c] || state.activeCategory === c)
      .map((c) => chipHtml(c, c, state.counts[c] || 0))
      .join("");
  chips.querySelectorAll(".chip").forEach((chip) => {
    chip.onclick = () => { state.activeCategory = chip.dataset.cat; loadEmails(); };
  });

  const accSel = $("#account-filter");
  accSel.innerHTML =
    `<option value="">Tüm hesaplar</option>` +
    state.accounts
      .map((a) => `<option value="${a.id}" ${String(state.activeAccount) === String(a.id) ? "selected" : ""}>${esc(a.display_name || a.email)}</option>`)
      .join("");
}

$("#account-filter").onchange = (e) => { state.activeAccount = e.target.value; loadEmails(); };
$("#search-input").oninput = (e) => { state.search = e.target.value.toLowerCase(); renderList(); };

function visibleEmails() {
  if (!state.search) return state.emails;
  return state.emails.filter((e) =>
    [e.sender_name, e.sender_email, e.subject, e.summary]
      .join(" ").toLowerCase().includes(state.search)
  );
}

function renderList() {
  const list = $("#email-list");
  const emails = visibleEmails();
  if (!emails.length) {
    list.innerHTML = `<div class="placeholder" style="margin-top:60px">
      ${state.emails.length ? "Aramayla eşleşen mail yok." : 'Mail yok. Sağ üstten "Eşitle"ye tıklayın.'}
    </div>`;
    return;
  }
  const showAcct = !state.activeAccount && state.accounts.length > 1;
  list.innerHTML = emails
    .map((e) => {
      const active = e.id === state.selectedId ? " active" : "";
      const replied = e.status === "replied" ? `<span class="badge replied">✓ yanıtlandı</span>` : "";
      const att = e.attachments.length ? `<span class="badge">${MI.paperclip} ${e.attachments.length}</span>` : "";
      const acct = showAcct && e.account_email ? `<span class="badge acct">${esc(e.account_name || e.account_email)}</span>` : "";
      const isUnread = (e.thread_unread || 0) > 0 || !e.is_read;
      const unread = isUnread ? " unread" : "";
      const threadBadge = (e.thread_count || 1) > 1
        ? `<span class="badge thread">${MI.thread} ${e.thread_count}</span>` : "";
      const snoozed = state.activeView === "snoozed" && e.snooze_until
        ? `<span class="badge">${MI.clock} ${formatDateFull(e.snooze_until)}</span>` : "";
      const prio = (e.priority || "").toLowerCase() === "yüksek" ? " prio" : "";
      return `
      <article class="email-item${active}${unread}${prio}" data-id="${e.id}" tabindex="0">
        ${avatarHtml(e.sender_name, e.sender_email)}
        <div class="item-body">
          <div class="row1">
            <span class="from">${esc(e.sender_name || e.sender_email)}</span>
            <span class="time">${formatDate(e.date)}</span>
          </div>
          <div class="subject">${esc(e.subject)}</div>
          <div class="summary">${esc(e.summary || (e.body_text || "").replace(/\s+/g, " ").slice(0, 120))}</div>
          <div class="meta">
            <span class="badge cat">${esc(e.category || "")}</span>
            ${(e.priority || "").toLowerCase() === "yüksek" ? '<span class="badge p-yüksek">yüksek</span>' : ""}
            ${threadBadge}${att}${acct}${replied}${snoozed}
          </div>
        </div>
        <div class="item-tools">
          <button class="star-btn${e.starred ? " on" : ""}" data-star="${e.id}" title="Yıldızla (s)" aria-label="Yıldızla">${MI.star(e.starred)}</button>
          <button class="quick-btn" data-arch="${e.id}" title="Arşivle (e)" aria-label="Arşivle">${MI.archive}</button>
        </div>
      </article>`;
    })
    .join("");
  document.querySelectorAll(".email-item").forEach((item) => {
    const open = (ev) => {
      if (ev.target.closest(".item-tools")) return;
      selectEmail(parseInt(item.dataset.id));
    };
    item.onclick = open;
    item.onkeydown = (ev) => { if (ev.key === "Enter") open(ev); };
  });
  document.querySelectorAll(".star-btn[data-star]").forEach((btn) => {
    btn.onclick = () => toggleStar(parseInt(btn.dataset.star));
  });
  document.querySelectorAll(".quick-btn[data-arch]").forEach((btn) => {
    btn.onclick = () => archiveEmail(parseInt(btn.dataset.arch));
  });
  const cnt = $("#list-count");
  if (cnt) {
    const unreadN = emails.filter((e) => (e.thread_unread || 0) > 0 || !e.is_read).length;
    cnt.textContent = unreadN ? `${unreadN} okunmamış` : `${emails.length} mail`;
  }
}

async function archiveEmail(id) {
  try {
    await api(`/api/emails/${id}/archive`, { method: "POST" });
    toast("Arşivlendi");
    if (state.selectedId === id) state.selectedId = null;
    loadEmails();
  } catch (e) { toast(e.message, true); }
}

async function toggleStar(id) {
  const email = state.emails.find((e) => e.id === id);
  if (!email) return;
  await api(`/api/emails/${id}/star`, { method: "POST",
    body: JSON.stringify({ value: !email.starred }) });
  email.starred = !email.starred;
  renderList();
}

async function selectEmail(id) {
  state.selectedId = id;
  const t = await api(`/api/emails/${id}/thread`);
  const msgs = t.messages;
  const e = msgs.find((m) => m.id === id) || msgs[msgs.length - 1];
  const local = state.emails.find((x) => x.id === id);
  if (local) {
    const wasUnread = local.thread_unread || (!local.is_read ? 1 : 0);
    if (wasUnread) {
      local.is_read = true;
      local.thread_unread = 0;
      state.views.unread = Math.max(0, (state.views.unread || 0) - wasUnread);
      renderUnreadBadge();
    }
  }
  renderList();
  renderDetail(e, msgs);
}

function renderDetail(e, threadMsgs = []) {
  const thread = threadMsgs.length > 1 ? threadMsgs : null;
  const attachments = e.attachments.length
    ? `<div class="card"><h3>${MI.paperclip} Ekler — dataroom'a kaydedildi</h3><div class="attachment-list">
        ${e.attachments.map((a) => `<a href="/api/dataroom/download?path=${encodeURIComponent(a.path)}">${esc(a.filename)} <span class="size">${formatSize(a.size)}</span></a>`).join("")}
       </div></div>`
    : "";

  const acctInfo = e.account_email
    ? `<span class="badge acct">${esc(e.account_name || e.account_email)}</span>`
    : "";

  const writableCals = state.calendars.filter((c) => c.type === "icloud");
  const eventCard = e.event && e.event.exists && e.event.date
    ? `<div class="card event-card">
        <h3>${MI.calendar} Tespit Edilen Etkinlik</h3>
        <div class="ev-line"><strong>${esc(e.event.title || e.subject)}</strong></div>
        <div class="ev-line">${esc(e.event.date)}${e.event.time ? " · " + esc(e.event.time) : " · tüm gün"}${e.event.location ? " · " + MI.pin + " " + esc(e.event.location) : ""}</div>
        <div class="ev-actions">
          <select id="event-cal-select">
            <option value="">Meil (yerel takvim)</option>
            ${writableCals.map((c) => `<option value="${c.id}">${esc(c.name)} (iCloud)</option>`).join("")}
          </select>
          <button class="pill accent" id="add-event-btn">${MI.calendar} Takvime Ekle</button>
        </div>
      </div>`
    : "";

  $("#detail-panel").innerHTML = `
    <header class="mv-head">
      <div class="mv-title-row">
        <h1 class="mv-subject">${esc(e.subject)}</h1>
        <div class="mv-tools">
          <button class="icon-btn${e.starred ? " on" : ""}" id="d-star" title="Yıldızla (s)" aria-label="Yıldızla">${MI.star(e.starred)}</button>
          <button class="icon-btn" id="d-snooze" title="Ertele" aria-label="Ertele">${MI.clock}</button>
          <button class="icon-btn" id="d-unread" title="Okunmadı işaretle" aria-label="Okunmadı işaretle">${MI.mailUnread}</button>
          <button class="icon-btn" id="d-archive" title="${e.status === "archived" ? "Gelen kutusuna taşı" : "Arşivle (e)"}" aria-label="Arşivle">${e.status === "archived" ? MI.unarchive : MI.archive}</button>
        </div>
      </div>
      <div class="mv-from">
        ${avatarHtml(e.sender_name, e.sender_email)}
        <div class="mv-who">
          <div class="mv-name">${esc(e.sender_name || e.sender_email)}
            <span class="mv-addr">&lt;${esc(e.sender_email)}&gt;</span></div>
          <div class="mv-sub">${formatDateFull(e.date)}${acctInfo ? " · " + acctInfo : ""}</div>
        </div>
        <div class="mv-tags">
          ${e.category ? `<span class="badge cat">${esc(e.category)}</span>` : ""}
          ${e.priority ? `<span class="badge p-${esc(e.priority)}">${esc(e.priority)}</span>` : ""}
          ${e.status === "replied" ? '<span class="badge replied">✓ yanıtlandı</span>' : ""}
        </div>
      </div>
    </header>

    <div class="mv-scroll">
      ${e.summary ? `<div class="mv-ai">
        <span class="mv-ai-ico">${MI.sparkle}</span>
        <div class="mv-ai-text"><p>${esc(e.summary)}</p>
          ${thread ? `<div id="thread-sum-holder"><button class="mv-ai-more" id="thread-sum-btn">Tüm yazışmayı özetle (${thread.length} mail)</button></div>` : ""}
        </div>
      </div>` : ""}

      ${e.attachments.length ? `<div class="mv-attach">
        ${e.attachments.map((a) => `<a class="mv-file" href="/api/dataroom/download?path=${encodeURIComponent(a.path)}" title="${esc(a.filename)}">
          <span class="mv-file-ico">${MI.paperclip}</span>
          <span class="mv-file-name">${esc(a.filename)}</span>
          <span class="mv-file-size">${formatSize(a.size)}</span></a>`).join("")}
      </div>` : ""}

      ${eventCard}

      ${thread
        ? `<div class="mv-thread">
            ${thread.map((m, i) => {
              const open = i === thread.length - 1 ? " open" : "";
              const mine = state.accounts.some((a) => a.email === m.sender_email);
              return `<div class="tm${open}${mine ? " mine" : ""}">
                <div class="tm-head" role="button" tabindex="0">
                  ${avatarHtml(m.sender_name, m.sender_email)}
                  <div class="tm-who">
                    <span class="tm-from">${esc(m.sender_name || m.sender_email)}</span>
                    <span class="tm-snippet">${esc((m.body_text || "").replace(/\s+/g, " ").slice(0, 120))}</span>
                  </div>
                  <span class="tm-time">${formatDate(m.date)}</span>
                  <span class="tm-caret">${MI.chevron || "⌄"}</span>
                </div>
                <div class="tm-body"><div class="mail-body">${formatBody(m.body_text)}</div></div>
              </div>`;
            }).join("")}
          </div>`
        : `<div class="mail-body">${formatBody(e.body_text)}</div>`}
    </div>

    <footer class="mv-reply${e.status === "replied" ? " sent" : ""}" id="mv-reply">
      <div class="mvr-collapsed" id="mvr-collapsed">
        <button class="mvr-open" id="mvr-open">
          ${MI.send} ${e.suggested_reply ? "Hazır yanıtı gözden geçir" : "Yanıtla"}
        </button>
        ${e.status === "replied" ? '<span class="mvr-note">✓ Bu maile yanıt gönderildi</span>'
          : e.suggested_reply ? '<span class="mvr-note">AI bir taslak hazırladı</span>' : ""}
      </div>
      <div class="mvr-form" id="mvr-form" hidden>
        <div class="mvr-to">Kime: <b>${esc(e.sender_name || e.sender_email)}</b></div>
        <textarea id="reply-text" placeholder="Yanıtınızı yazın…">${esc(e.suggested_reply || "")}</textarea>
        <div class="mvr-instr">
          <input id="regen-instruction" placeholder="AI'ya talimat: daha resmi yaz, toplantı öner…">
          <button class="pill ghost" id="regen-btn" title="Yeniden öner">${MI.refresh}</button>
        </div>
        <div class="mvr-actions">
          <button class="pill ghost" id="mvr-close">Kapat</button>
          <button class="pill ghost" id="archive-btn">Arşivle</button>
          <button class="pill accent" id="send-btn" ${e.status === "replied" ? "disabled" : ""}>${MI.send} Onayla ve Gönder</button>
        </div>
      </div>
    </footer>
  `;

  // Yanıt alanı: kapalı başlar, tıklayınca açılır (gerçek mail uygulaması gibi)
  const openReply = () => {
    $("#mvr-collapsed").hidden = true;
    $("#mvr-form").hidden = false;
    $("#mv-reply").classList.add("expanded");
    $("#reply-text").focus();
  };
  $("#mvr-open").onclick = openReply;
  $("#mvr-close").onclick = () => {
    $("#mvr-form").hidden = true;
    $("#mvr-collapsed").hidden = false;
    $("#mv-reply").classList.remove("expanded");
  };

  document.querySelectorAll(".thread-msg .tm-head").forEach((head) => {
    const toggle = () => head.parentElement.classList.toggle("open");
    head.onclick = toggle;
    head.onkeydown = (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); toggle(); } };
  });

  const tsBtn = $("#thread-sum-btn");
  if (tsBtn) tsBtn.onclick = async () => {
    tsBtn.disabled = true;
    tsBtn.textContent = "Özetleniyor...";
    try {
      const s = await api(`/api/emails/${e.id}/thread-summary`, { method: "POST" });
      $("#thread-sum-holder").innerHTML = `<div class="thread-summary">
        <p>${esc(s.summary)}</p>
        ${s.action_needed ? `<p class="ts-action">${MI.hourglass} ${esc(s.action_needed)}</p>` : ""}
      </div>`;
    } catch (err) {
      toast(err.message, true);
      tsBtn.disabled = false;
      tsBtn.innerHTML = MI.thread + ` Tüm Yazışmayı Özetle (${thread.length} mail)`;
    }
  };

  $("#send-btn").onclick = async () => {
    const text = $("#reply-text").value.trim();
    if (!text) return toast("Yanıt metni boş", true);
    const from = e.account_email ? ` (${e.account_email} hesabından)` : "";
    if (!confirm(`${e.sender_email} adresine${from} bu yanıt gönderilsin mi?`)) return;
    $("#send-btn").disabled = true;
    try {
      await api(`/api/emails/${e.id}/send`, { method: "POST", body: JSON.stringify({ reply_text: text }) });
      toast("Yanıt gönderildi ✓");
      await loadEmails();
      selectEmail(e.id);
    } catch (err) {
      toast(err.message, true);
      $("#send-btn").disabled = false;
    }
  };

  $("#regen-btn").onclick = async () => {
    const btn = $("#regen-btn");
    btn.disabled = true;
    btn.textContent = "Üretiliyor...";
    try {
      const data = await api(`/api/emails/${e.id}/regenerate`, {
        method: "POST",
        body: JSON.stringify({ instruction: $("#regen-instruction").value }),
      });
      $("#reply-text").value = data.suggested_reply;
      toast("Yeni taslak hazır");
    } catch (err) {
      toast(err.message, true);
    } finally {
      btn.disabled = false;
      btn.innerHTML = MI.refresh + " Yeniden Öner";
    }
  };

  $("#archive-btn").onclick = async () => {
    await api(`/api/emails/${e.id}/archive`, { method: "POST" });
    toast("Arşivlendi");
    loadEmails();
  };

  $("#d-star").onclick = async () => {
    await api(`/api/emails/${e.id}/star`, { method: "POST",
      body: JSON.stringify({ value: !e.starred }) });
    e.starred = !e.starred;
    $("#d-star").innerHTML = MI.star(e.starred);
    $("#d-star").classList.toggle("on", e.starred);
    loadEmails();
  };
  $("#d-unread").onclick = async () => {
    await api(`/api/emails/${e.id}/read`, { method: "POST",
      body: JSON.stringify({ value: false }) });
    toast("Okunmadı olarak işaretlendi");
    state.selectedId = null;
    loadEmails();
  };
  $("#d-archive").onclick = async () => {
    const action = e.status === "archived" ? "unarchive" : "archive";
    await api(`/api/emails/${e.id}/${action}`, { method: "POST" });
    toast(action === "archive" ? "Arşivlendi" : "Gelen kutusuna taşındı");
    loadEmails();
  };
  $("#d-snooze").onclick = () => openSnoozeModal(e);

  const addEventBtn = $("#add-event-btn");
  if (addEventBtn) {
    addEventBtn.onclick = async () => {
      addEventBtn.disabled = true;
      try {
        const calId = $("#event-cal-select").value;
        const data = await api(`/api/emails/${e.id}/add-to-calendar`, {
          method: "POST",
          body: JSON.stringify({ calendar_id: calId ? parseInt(calId) : null }),
        });
        toast(`Etkinlik "${data.calendar}" takvimine eklendi ✓`);
      } catch (err) {
        toast(err.message, true);
        addEventBtn.disabled = false;
      }
    };
  }
}

// ---- Erteleme (snooze) ----

function snoozePresets() {
  const now = new Date();
  const at = (d, h) => { const x = new Date(d); x.setHours(h, 0, 0, 0); return x; };
  const today18 = at(now, 18);
  const tomorrow = at(new Date(now.getTime() + 86400000), 9);
  const in3days = at(new Date(now.getTime() + 3 * 86400000), 9);
  const nextMonday = new Date(now);
  nextMonday.setDate(now.getDate() + ((8 - now.getDay()) % 7 || 7));
  return [
    ["Bu akşam 18:00", today18 > now ? today18 : null],
    ["Yarın 09:00", tomorrow],
    ["3 gün sonra", in3days],
    ["Pazartesi 09:00", at(nextMonday, 9)],
  ].filter(([, d]) => d);
}

function isoLocal(d) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

function openSnoozeModal(e) {
  const presets = snoozePresets();
  openModal(`
    <h3>Ertele — ${esc(e.subject)}</h3>
    <div class="modal-sub">Mail seçilen zamana kadar gelen kutusundan gizlenir; "Ertelenen" sekmesinde durur.</div>
    <div class="modal-list">
      ${presets.map(([label, d], i) => `<button class="pill ghost" data-snooze="${isoLocal(d)}">${label} <span style="color:var(--muted)">· ${d.toLocaleDateString("tr-TR", { day: "2-digit", month: "short" })}</span></button>`).join("")}
      ${e.snooze_until ? `<button class="pill danger-ghost" data-snooze="">Ertelemeyi kaldır</button>` : ""}
    </div>
    <div class="form-col" style="margin-top:10px">
      <input id="snooze-custom" type="datetime-local">
    </div>
    <div class="modal-actions">
      <button class="pill ghost" onclick="closeModal()">Vazgeç</button>
      <button class="pill accent" id="snooze-custom-btn">Seçilen Tarihe Ertele</button>
    </div>`);
  const doSnooze = async (until) => {
    await api(`/api/emails/${e.id}/snooze`, { method: "POST",
      body: JSON.stringify({ until }) });
    toast(until ? "Mail ertelendi" : "Erteleme kaldırıldı");
    closeModal();
    state.selectedId = null;
    loadEmails();
  };
  document.querySelectorAll("[data-snooze]").forEach((btn) => {
    btn.onclick = () => doSnooze(btn.dataset.snooze);
  });
  $("#snooze-custom-btn").onclick = () => {
    const v = $("#snooze-custom").value;
    if (!v) return toast("Tarih seçin", true);
    doSnooze(v);
  };
}

// ---- Yeni mail (compose) ----

function openComposeModal(prefill = {}) {
  if (!state.accounts.length) {
    return toast("Önce Hesaplar sekmesinden bir mail hesabı ekleyin", true);
  }
  const accountOptions = state.accounts
    .map((a) => `<option value="${a.id}">${esc(a.display_name || a.email)}</option>`)
    .join("");
  openModal(`
    <h3>Yeni Mail</h3>
    <div class="form-col">
      <select id="c-account">${accountOptions}</select>
      <input id="c-to" type="email" placeholder="Alıcı" value="${esc(prefill.to || "")}">
      <input id="c-cc" placeholder="CC (isteğe bağlı, virgülle ayırın)">
      <input id="c-subject" placeholder="Konu" value="${esc(prefill.subject || "")}">
      <textarea id="c-body" style="min-height:180px" placeholder="Mesajınız...">${esc(prefill.body || "")}</textarea>
      <div class="form-row">
        <input id="c-ai" placeholder="AI'ya anlatın: 'yarınki toplantıyı iptal et, kibarca'">
        <button class="pill ghost" id="c-ai-btn" style="flex:0 0 auto">${MI.sparkle} AI ile Yaz</button>
      </div>
    </div>
    <div class="modal-actions">
      <button class="pill ghost" onclick="closeModal()">Vazgeç</button>
      <button class="pill accent" id="c-send">${MI.send} Gönder</button>
    </div>`);
  $("#c-ai-btn").onclick = async () => {
    const instruction = $("#c-ai").value.trim();
    if (!instruction) return toast("AI'ya ne yazacağını kısaca anlatın", true);
    const btn = $("#c-ai-btn");
    btn.disabled = true; btn.textContent = "Yazılıyor...";
    try {
      const draft = await api("/api/compose/draft", { method: "POST",
        body: JSON.stringify({ instruction, to: $("#c-to").value, subject: $("#c-subject").value }) });
      $("#c-body").value = draft.body;
      if (!$("#c-subject").value) $("#c-subject").value = draft.subject;
      toast("Taslak hazır — düzenleyip gönderebilirsiniz");
    } catch (err) { toast(err.message, true); }
    finally { btn.disabled = false; btn.innerHTML = MI.sparkle + " AI ile Yaz"; }
  };
  $("#c-send").onclick = async () => {
    const btn = $("#c-send");
    btn.disabled = true; btn.textContent = "Gönderiliyor...";
    try {
      await api("/api/compose", { method: "POST",
        body: JSON.stringify({
          account_id: parseInt($("#c-account").value),
          to: $("#c-to").value.trim(),
          cc: $("#c-cc").value.trim(),
          subject: $("#c-subject").value.trim(),
          body: $("#c-body").value,
        }) });
      toast("Mail gönderildi ✓");
      closeModal();
    } catch (err) {
      toast(err.message, true);
      btn.disabled = false; btn.innerHTML = MI.send + " Gönder";
    }
  };
}

$("#compose-btn").onclick = () => openComposeModal();

// ---- Gelen kutusuyla sohbet (AI'ya Sor) ----

const chatState = { messages: [] };  // {role, content, sources?} — sayfa açık kaldıkça sürer

const CHAT_SUGGESTIONS = [
  "Yanıt bekleyen maillerim hangileri?",
  "Bu hafta hangi faturalar geldi, son ödeme tarihleri ne?",
  "Son gelen mail kimden ve ne hakkında?",
];

function renderChatLog() {
  const log = $("#chat-log");
  if (!log) return;
  if (!chatState.messages.length) {
    log.innerHTML = `<div class="chat-empty">
      <p>Gelen kutunuz hakkında istediğinizi sorun — yanıtlar yalnızca maillerinize dayanır.</p>
      ${CHAT_SUGGESTIONS.map((s) => `<button class="chat-suggestion" data-q="${esc(s)}">${esc(s)}</button>`).join("")}
    </div>`;
    log.querySelectorAll(".chat-suggestion").forEach((b) => {
      b.onclick = () => { $("#chat-input").value = b.dataset.q; sendChatMessage(); };
    });
    return;
  }
  log.innerHTML = chatState.messages.map((m) => {
    if (m.role === "user")
      return `<div class="chat-msg user">${esc(m.content)}</div>`;
    if (m.pending)
      return `<div class="chat-msg assistant pending">Mailleriniz taranıyor...</div>`;
    const sources = (m.sources || []).map((s) =>
      `<button class="chat-source" data-mail="${s.id}" title="${esc(s.subject)}">${MI.inbox} ${esc(s.sender)} — ${esc((s.subject || "").slice(0, 40))}</button>`
    ).join("");
    return `<div class="chat-msg assistant">${esc(m.content)}${sources ? `<div class="chat-sources">${sources}</div>` : ""}</div>`;
  }).join("");
  log.querySelectorAll("[data-mail]").forEach((btn) => {
    btn.onclick = () => {
      closeModal();
      document.querySelector('.rail-btn[data-view="inbox"]').click();
      selectEmail(parseInt(btn.dataset.mail));
    };
  });
  log.scrollTop = log.scrollHeight;
}

async function sendChatMessage() {
  const input = $("#chat-input");
  const question = input.value.trim();
  if (!question) return;
  input.value = "";
  const history = chatState.messages
    .filter((m) => !m.pending)
    .map((m) => ({ role: m.role, content: m.content }));
  chatState.messages.push({ role: "user", content: question });
  chatState.messages.push({ role: "assistant", content: "", pending: true });
  renderChatLog();
  try {
    const data = await api("/api/inbox/chat", { method: "POST",
      body: JSON.stringify({ question, history }) });
    chatState.messages.pop();
    chatState.messages.push({ role: "assistant", content: data.answer, sources: data.sources });
  } catch (err) {
    chatState.messages.pop();
    chatState.messages.push({ role: "assistant", content: "Hata: " + err.message });
  }
  renderChatLog();
}

function openChatModal() {
  openModal(`
    <h3>${MI.sparkle} Gelen Kutusuna Sor</h3>
    <div id="chat-log" class="chat-log"></div>
    <div class="form-row" style="margin-top:10px">
      <input id="chat-input" placeholder="ör. Ayşe'yle fiyat nede kalmıştı?" autocomplete="off">
      <button class="pill accent" id="chat-send" style="flex:0 0 auto">${MI.send} Sor</button>
    </div>`);
  renderChatLog();
  $("#chat-send").onclick = sendChatMessage;
  $("#chat-input").onkeydown = (e) => { if (e.key === "Enter") sendChatMessage(); };
  $("#chat-input").focus();
}

$("#chat-btn").onclick = openChatModal;

// ---- Global arama paleti (Cmd+K / Ctrl+K) ----

const gs = { items: [], sel: 0, seq: 0, open: false };

function openGlobalSearch() {
  gs.open = true; gs.items = []; gs.sel = 0;
  $("#gs-overlay").style.display = "flex";
  $("#gs-input").value = "";
  $("#gs-results").innerHTML = `<div class="gs-hint">Yazmaya başlayın — maillerde, dataroom belgelerinde ve takvimde birlikte arar.</div>`;
  $("#gs-input").focus();
}

function closeGlobalSearch() {
  gs.open = false;
  $("#gs-overlay").style.display = "none";
}

document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    if (gs.open) closeGlobalSearch(); else openGlobalSearch();
  } else if (e.key === "Escape" && gs.open) {
    e.stopPropagation();
    closeGlobalSearch();
  }
}, true); // capture: modal'ın Escape dinleyicisinden önce çalışsın

$("#gs-overlay").onclick = (e) => { if (e.target.id === "gs-overlay") closeGlobalSearch(); };

let gsTimer = null;
$("#gs-input").oninput = () => {
  clearTimeout(gsTimer);
  const q = $("#gs-input").value.trim();
  if (q.length < 2) {
    gs.items = [];
    $("#gs-results").innerHTML = `<div class="gs-hint">En az 2 karakter yazın.</div>`;
    return;
  }
  gsTimer = setTimeout(async () => {
    const seq = ++gs.seq;
    let data;
    try {
      data = await api(`/api/search?q=${encodeURIComponent(q)}`);
    } catch { return; }
    if (seq !== gs.seq || !gs.open) return; // eskimiş yanıt
    gs.items = [
      ...data.emails.map((m) => ({ type: "email", ...m })),
      ...data.files.map((f) => ({ type: "file", ...f })),
      ...data.events.map((ev) => ({ type: "event", ...ev })),
    ];
    gs.sel = 0;
    renderGsResults();
  }, 200);
};

function renderGsResults() {
  const holder = $("#gs-results");
  if (!gs.items.length) {
    holder.innerHTML = `<div class="gs-hint">Sonuç bulunamadı.</div>`;
    return;
  }
  let html = "";
  for (const [type, label] of [["email", "Mailler"], ["file", "Belgeler"], ["event", "Etkinlikler"]]) {
    const items = gs.items.filter((it) => it.type === type);
    if (!items.length) continue;
    html += `<div class="gs-group">${label}</div>`;
    for (const it of items) {
      const i = gs.items.indexOf(it);
      const sel = i === gs.sel ? " sel" : "";
      if (type === "email") {
        html += `<div class="gs-item${sel}" data-i="${i}">${MI.inbox}
          <div class="gs-body">
            <span class="gs-title">${esc(it.sender || "")} — ${esc(it.subject || "(konu yok)")}</span>
            ${it.snippet ? `<span class="gs-snip">${snippetHtml(it.snippet)}</span>` : ""}
          </div><span class="gs-meta">${formatDate(it.date)}</span></div>`;
      } else if (type === "file") {
        html += `<div class="gs-item${sel}" data-i="${i}">${DRI.file}
          <div class="gs-body">
            <span class="gs-title">${esc(it.filename)}</span>
            <span class="gs-snip">${it.snippet ? snippetHtml(it.snippet) : esc(it.path)}</span>
          </div><span class="gs-meta">Dataroom</span></div>`;
      } else {
        html += `<div class="gs-item${sel}" data-i="${i}">${MI.calendar}
          <div class="gs-body">
            <span class="gs-title">${esc(it.title || "")}</span>
            <span class="gs-snip">${esc(it.calendar_name || "Meil")}${it.location ? " · " + esc(it.location) : ""}</span>
          </div><span class="gs-meta">${formatDateFull(it.start)}</span></div>`;
      }
    }
  }
  holder.innerHTML = html;
  holder.querySelectorAll(".gs-item").forEach((el) => {
    el.onclick = () => activateGsItem(parseInt(el.dataset.i));
  });
}

$("#gs-input").onkeydown = (e) => {
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    if (!gs.items.length) return;
    gs.sel = e.key === "ArrowDown"
      ? Math.min(gs.sel + 1, gs.items.length - 1)
      : Math.max(gs.sel - 1, 0);
    renderGsResults();
    const el = document.querySelector(`.gs-item[data-i="${gs.sel}"]`);
    if (el) el.scrollIntoView({ block: "nearest" });
  } else if (e.key === "Enter") {
    e.preventDefault();
    if (gs.items[gs.sel]) activateGsItem(gs.sel);
  }
};

async function activateGsItem(i) {
  const it = gs.items[i];
  closeGlobalSearch();
  if (it.type === "email") {
    document.querySelector('.rail-btn[data-view="inbox"]').click();
    selectEmail(it.id);
  } else if (it.type === "file") {
    document.querySelector('.rail-btn[data-view="dataroom"]').click();
    await loadDataroom();
    const f = dr.files.find((x) => x.path === it.path);
    if (f) openInspector(f);
  } else {
    document.querySelector('.rail-btn[data-view="calendar"]').click();
    const d = new Date(it.start);
    if (!isNaN(d)) {
      state.cal.year = d.getFullYear();
      state.cal.month = d.getMonth();
      state.cal.selected = ymd(d);
    }
    loadCalendar();
  }
}

// ---- Klavye kısayolları (j/k gezin, e arşivle, s yıldızla, r yanıtla, c yeni) ----

document.addEventListener("keydown", (ev) => {
  if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) return;
  if ($("#modal-overlay").style.display === "flex") return;
  if ($("#view-inbox").style.display === "none") return;
  const emails = visibleEmails();
  const idx = emails.findIndex((e) => e.id === state.selectedId);
  if (ev.key === "j" || ev.key === "k") {
    ev.preventDefault();
    const next = ev.key === "j" ? Math.min(idx + 1, emails.length - 1) : Math.max(idx - 1, 0);
    if (emails[next]) selectEmail(emails[next].id);
  } else if (ev.key === "c") {
    ev.preventDefault();
    openComposeModal();
  } else if (state.selectedId) {
    if (ev.key === "s") { ev.preventDefault(); toggleStar(state.selectedId); }
    if (ev.key === "e") { ev.preventDefault(); const b = $("#d-archive"); if (b) b.click(); }
    if (ev.key === "r") { ev.preventDefault(); const t = $("#reply-text"); if (t) t.focus(); }
  }
});

// ---- Otomatik eşitleme (5 dakikada bir, sessiz) ----

setInterval(async () => {
  if (!state.accounts.length) return;
  try {
    const data = await api("/api/sync", { method: "POST" });
    if (data.new_emails > 0) {
      toast(`${data.new_emails} yeni mail geldi`);
      loadEmails();
    }
    if (data.new_notifications > 0) refreshNotifications();
  } catch { /* sessizce geç */ }
}, 5 * 60 * 1000);

// ---- Eşitleme ----

$("#sync-btn").onclick = async () => {
  const btn = $("#sync-btn");
  btn.disabled = true;
  btn.querySelector("span").textContent = "Eşitleniyor...";
  try {
    const data = await api("/api/sync", { method: "POST" });
    const failed = data.results.filter((r) => r.errors.length);
    let msg = `${data.new_emails} yeni mail tasnif edildi`;
    if (failed.length) msg += ` — hata: ${failed.map((r) => r.account).join(", ")}`;
    toast(msg, failed.length > 0 && data.new_emails === 0);
    failed.forEach((r) => console.warn(r.account, r.errors));
    if (data.new_notifications > 0) refreshNotifications();
    await loadEmails();
  } catch (err) {
    toast(err.message, true);
  } finally {
    btn.disabled = false;
    btn.querySelector("span").textContent = "Eşitle";
  }
};

// ---- Modal ----

function openModal(html) {
  $("#modal").innerHTML = html;
  $("#modal-overlay").style.display = "flex";
}
function closeModal() {
  $("#modal-overlay").style.display = "none";
  $("#modal").innerHTML = "";
}
$("#modal-overlay").onclick = (e) => { if (e.target.id === "modal-overlay") closeModal(); };
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

// ---- Dataroom ----

// ==== Dataroom v3 — Swiss/Minimal (ui-ux-pro-max tasarım sistemi) ====

const dr = {
  files: [], folders: [], activity: [], stats: {},
  folder: "", search: "", sort: "date", type: "all", favOnly: false,
  selected: new Set(), inspectorPath: null,
  contentHits: new Map(), searchSeq: 0,  // içerik araması: path → eşleşme parçası
};

// Lucide tarzı satır içi SVG ikonlar (emoji yok — skill kuralı)
const DRI = {
  file: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14 3v5h5M6 3h8l5 5v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z"/></svg>',
  pdf: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14 3v5h5M6 3h8l5 5v13a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z"/><path d="M9 13h6M9 17h4"/></svg>',
  image: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="10" r="1.5"/><path d="m5 19 5-5 3 3 3-3 3 3"/></svg>',
  sheet: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="4" y="4" width="16" height="16" rx="1.5"/><path d="M4 10h16M10 4v16"/></svg>',
  folder: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 8a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/></svg>',
  home: '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="m3 11 9-8 9 8M5 10v10h14V10"/></svg>',
  download: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 4v12m0 0 4-4m-4 4-4-4M4 20h16"/></svg>',
  send: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m3 3 18 9-18 9 4-9-4-9ZM7 12h14"/></svg>',
  link: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1.5 1.5M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1.5-1.5"/></svg>',
  trash: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7h16M9 7V4h6v3m-8 0 1 13h8l1-13"/></svg>',
  eye: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>',
  move: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 8a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><path d="M12 11v6m0-6-2 2m2-2 2 2"/></svg>',
  star: (on) => `<svg width="15" height="15" viewBox="0 0 24 24" fill="${on ? "currentColor" : "none"}" stroke="currentColor" stroke-width="1.8"><path d="m12 3 2.7 5.6 6.3.9-4.5 4.4 1 6.1L12 17.2 6.5 20l1-6.1L3 9.5l6.3-.9L12 3Z"/></svg>`,
  x: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg>',
  note: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5Z"/></svg>',
  clock: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>',
  user: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4-6 8-6s7 2 8 6"/></svg>',
};

const DR_TYPES = {
  pdf: ["pdf"],
  sheet: ["xls", "xlsx", "csv", "ods"],
  doc: ["doc", "docx", "txt", "rtf", "odt", "md", "ppt", "pptx"],
  image: ["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "heic"],
};

function drTypeOf(name) {
  const ext = (name.split(".").pop() || "").toLowerCase();
  for (const [t, exts] of Object.entries(DR_TYPES)) if (exts.includes(ext)) return t;
  return "other";
}

function drFileIcon(name) {
  const t = drTypeOf(name);
  if (t === "pdf") return DRI.pdf;
  if (t === "image") return DRI.image;
  if (t === "sheet") return DRI.sheet;
  return DRI.file;
}

function drDate(epoch) {
  return new Date(epoch * 1000).toLocaleDateString("tr-TR", { day: "2-digit", month: "short", year: "numeric" });
}

function relTime(sqliteUtc) {
  const d = new Date(String(sqliteUtc).replace(" ", "T") + "Z");
  const mins = Math.round((Date.now() - d.getTime()) / 60000);
  if (mins < 1) return "az önce";
  if (mins < 60) return `${mins} dk önce`;
  if (mins < 1440) return `${Math.round(mins / 60)} sa önce`;
  return `${Math.round(mins / 1440)} gün önce`;
}

async function loadDataroom() {
  const data = await api("/api/dataroom");
  dr.files = data.files;
  dr.folders = data.folders;
  dr.activity = data.activity;
  dr.stats = data.stats;
  dr.selected = new Set([...dr.selected].filter((p) => dr.files.some((f) => f.path === p)));
  renderDrStats();
  renderDrTree();
  renderDrActivity();
  renderDataroom();
  if (dr.inspectorPath) {
    const f = dr.files.find((x) => x.path === dr.inspectorPath);
    if (f) openInspector(f, false); else closeInspector();
  }
}

function renderDrStats() {
  const s = dr.stats;
  $("#dr-stats").innerHTML = `
    <div class="dr-stat"><span class="dr-stat-n">${s.count || 0}</span><span>dosya</span></div>
    <div class="dr-stat"><span class="dr-stat-n">${formatSize(s.size || 0)}</span><span>depolama</span></div>
    <div class="dr-stat"><span class="dr-stat-n">${s.shared || 0}</span><span>paylaşımda</span></div>`;
}

function renderDrTree() {
  const rows = [`<div class="dr-folder${dr.folder === "" ? " active" : ""}" data-folder="" role="button" tabindex="0">${DRI.home}<span>Tüm Dosyalar</span></div>`];
  for (const folder of dr.folders) {
    const depth = folder.split("/").length - 1;
    const name = folder.split("/").pop();
    rows.push(
      `<div class="dr-folder${dr.folder === folder ? " active" : ""}" data-folder="${esc(folder)}" title="${esc(folder)}" role="button" tabindex="0" style="padding-left:${10 + depth * 16}px">${DRI.folder}<span>${esc(name)}</span></div>`
    );
  }
  $("#dr-tree").innerHTML = rows.join("");
  $("#dr-tree").querySelectorAll(".dr-folder").forEach((el) => {
    el.onclick = () => { dr.folder = el.dataset.folder; renderDrTree(); renderDataroom(); };
  });
}

const DR_ACT_LABELS = {
  upload: "yüklendi", delete: "silindi", note: "not güncellendi",
  share_created: "paylaşıma açıldı", share_revoked: "paylaşım kapatıldı",
  share_download: "linkten indirildi", send: "mail atıldı",
  move: "taşındı", folder: "klasör oluşturuldu", download: "indirildi",
};

function renderDrActivity() {
  const holder = $("#dr-activity");
  if (!dr.activity.length) {
    holder.innerHTML = `<p class="dr-hint">Henüz etkinlik yok.</p>`;
    return;
  }
  holder.innerHTML = dr.activity.slice(0, 12).map((a) => {
    const name = (a.path || "").split("/").pop();
    const extra = a.action === "send" && a.detail ? ` → ${a.detail}` : "";
    return `<div class="dr-act-row">
      <div class="dr-act-text" title="${esc(a.path || "")}"><strong>${esc(name)}</strong> ${DR_ACT_LABELS[a.action] || a.action}${esc(extra)}</div>
      <div class="dr-act-time">${relTime(a.created_at)}</div>
    </div>`;
  }).join("");
}

function renderDrBreadcrumb() {
  const parts = dr.folder ? dr.folder.split("/") : [];
  let html = `<a data-goto="" role="button" tabindex="0">Dataroom</a>`;
  let acc = "";
  for (const p of parts) {
    acc = acc ? `${acc}/${p}` : p;
    html += `<span class="sep">/</span><a data-goto="${esc(acc)}" role="button" tabindex="0">${esc(p)}</a>`;
  }
  $("#dr-breadcrumb").innerHTML = html;
  $("#dr-breadcrumb").querySelectorAll("a").forEach((a) => {
    a.onclick = () => { dr.folder = a.dataset.goto; renderDrTree(); renderDataroom(); };
  });
}

function drScopedFiles() {
  return dr.files.filter((f) =>
    !dr.folder || f.folder === dr.folder || f.folder.startsWith(dr.folder + "/"));
}

function visibleDrFiles() {
  let files = drScopedFiles();
  if (dr.favOnly) files = files.filter((f) => f.favorite);
  if (dr.type !== "all") files = files.filter((f) => drTypeOf(f.filename) === (dr.type === "doc" ? "doc" : dr.type));
  if (dr.search) {
    const q = dr.search.toLowerCase();
    files = files.filter((f) =>
      [f.filename, f.folder, f.note, f.doc_type, f.ai_summary, (f.tags || []).join(" ")]
        .join(" ").toLowerCase().includes(q)
      || dr.contentHits.has(f.path));
  }
  if (dr.sort === "name") files = [...files].sort((a, b) => a.filename.localeCompare(b.filename, "tr"));
  else if (dr.sort === "size") files = [...files].sort((a, b) => b.size - a.size);
  else files = [...files].sort((a, b) => b.modified - a.modified);
  return files;
}

function renderDrTypeChips() {
  const scoped = drScopedFiles();
  const count = (t) => scoped.filter((f) => drTypeOf(f.filename) === t).length;
  const chips = [
    ["all", "Tümü", scoped.length],
    ["fav", "Favoriler", scoped.filter((f) => f.favorite).length],
    ["pdf", "PDF", count("pdf")],
    ["sheet", "Tablo", count("sheet")],
    ["doc", "Belge", count("doc")],
    ["image", "Görsel", count("image")],
    ["other", "Diğer", count("other")],
  ];
  $("#dr-type-chips").innerHTML = chips.map(([val, label, n]) => {
    const active = val === "fav" ? dr.favOnly : (!dr.favOnly && dr.type === val);
    return `<button class="dr-chip${active ? " active" : ""}" data-type="${val}">${label}<span class="n">${n}</span></button>`;
  }).join("");
  $("#dr-type-chips").querySelectorAll(".dr-chip").forEach((chip) => {
    chip.onclick = () => {
      if (chip.dataset.type === "fav") { dr.favOnly = !dr.favOnly; }
      else { dr.favOnly = false; dr.type = chip.dataset.type; }
      renderDataroom();
    };
  });
}

function renderDrBulkbar() {
  const bar = $("#dr-bulkbar");
  if (!dr.selected.size) { bar.style.display = "none"; return; }
  bar.style.display = "flex";
  $("#dr-bulk-count").textContent = `${dr.selected.size} dosya seçili`;
}

function renderDataroom() {
  renderDrBreadcrumb();
  renderDrTypeChips();
  renderDrBulkbar();
  const holder = $("#dataroom-list");
  const files = visibleDrFiles();
  if (!files.length) {
    holder.innerHTML = `<div class="dr-empty">
      ${dr.files.length ? "Bu görünümde dosya yok." : "Dataroom boş — mail ekleri geldikçe birikecek, ya da kendi belgelerinizi yükleyin."}
    </div>`;
    return;
  }
  holder.innerHTML = `
    <table class="dr-table">
      <thead><tr>
        <th class="w-check"><input type="checkbox" id="dr-check-all" aria-label="Tümünü seç"></th>
        <th class="w-star"></th>
        <th>Dosya</th><th>Klasör</th><th class="w-num">Boyut</th><th>Tarih</th>
      </tr></thead>
      <tbody>
        ${files.map((f, i) => `
          <tr class="${dr.inspectorPath === f.path ? "active" : ""}" data-row="${i}">
            <td class="w-check"><input type="checkbox" class="dr-check" data-path="${esc(f.path)}" ${dr.selected.has(f.path) ? "checked" : ""} aria-label="Seç"></td>
            <td class="w-star"><button class="dr-star${f.favorite ? " on" : ""}" data-fav="${i}" title="Favori" aria-label="Favori">${DRI.star(f.favorite)}</button></td>
            <td>
              <div class="dr-file-cell">
                <span class="dr-file-icon dr-ic-${drTypeOf(f.filename)}">${drFileIcon(f.filename)}</span>
                <div class="dr-file-info">
                  <span class="dr-file-name">${esc(f.filename)}</span>
                  <span class="dr-file-sub">
                    ${f.doc_type ? `<span class="dr-doctype">${esc(f.doc_type)}</span>` : ""}
                    ${f.doc_amount ? `<span class="dr-amount">${esc(f.doc_amount)}</span>` : ""}
                    ${f.share_token ? `<span class="dr-shared">${DRI.link} paylaşımda${f.share_downloads ? ` · ${f.share_downloads}` : ""}</span>` : ""}
                    ${(f.tags || []).map((t) => `<span class="dr-tag">${esc(t)}</span>`).join("")}
                    ${f.note ? `<span class="dr-note-preview">${esc(f.note)}</span>` : ""}
                  </span>
                  ${dr.search && dr.contentHits.has(f.path) ? `<span class="dr-snippet">${snippetHtml(dr.contentHits.get(f.path))}</span>` : ""}
                </div>
              </div>
            </td>
            <td class="dr-muted">${esc(f.folder === "." ? "—" : f.folder)}</td>
            <td class="w-num dr-mono">${formatSize(f.size)}</td>
            <td class="dr-muted dr-mono">${drDate(f.modified)}</td>
          </tr>`).join("")}
      </tbody>
    </table>`;

  holder.querySelectorAll("tbody tr").forEach((row) => {
    const file = files[parseInt(row.dataset.row)];
    row.onclick = (ev) => {
      if (ev.target.closest(".dr-check, .dr-star")) return;
      openInspector(file);
    };
  });
  holder.querySelectorAll(".dr-check").forEach((cb) => {
    cb.onchange = () => {
      if (cb.checked) dr.selected.add(cb.dataset.path);
      else dr.selected.delete(cb.dataset.path);
      renderDrBulkbar();
    };
  });
  const checkAll = $("#dr-check-all");
  if (checkAll) checkAll.onchange = () => {
    files.forEach((f) => checkAll.checked ? dr.selected.add(f.path) : dr.selected.delete(f.path));
    renderDataroom();
  };
  holder.querySelectorAll("[data-fav]").forEach((btn) => {
    const file = files[parseInt(btn.dataset.fav)];
    btn.onclick = async () => {
      await api("/api/dataroom/favorite", { method: "POST",
        body: JSON.stringify({ path: file.path, favorite: !file.favorite }) });
      loadDataroom();
    };
  });
}

function snippetHtml(s) {
  // Sunucu eşleşmeyi [[..]] ile işaretler; önce kaçır, sonra vurguya çevir
  return esc(s).replaceAll("[[", "<mark>").replaceAll("]]", "</mark>");
}

let drSearchTimer = null;
$("#dataroom-search").oninput = (e) => {
  dr.search = e.target.value;
  renderDataroom();
  clearTimeout(drSearchTimer);
  const q = dr.search.trim();
  if (q.length < 2) {
    if (dr.contentHits.size) { dr.contentHits.clear(); renderDataroom(); }
    return;
  }
  drSearchTimer = setTimeout(async () => {
    const seq = ++dr.searchSeq;
    try {
      const data = await api(`/api/dataroom/search?q=${encodeURIComponent(q)}`);
      if (seq !== dr.searchSeq) return;  // eskimiş yanıtı at
      dr.contentHits = new Map(data.results.map((r) => [r.path, r.snippet]));
      renderDataroom();
    } catch { /* içerik araması isteğe bağlı — sessizce geç */ }
  }, 300);
};
$("#dr-sort").onchange = (e) => { dr.sort = e.target.value; renderDataroom(); };

$("#dr-index-btn").onclick = async () => {
  const btn = $("#dr-index-btn");
  const old = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = "Taranıyor...";
  try {
    const r = await api("/api/dataroom/index", { method: "POST", body: JSON.stringify({}) });
    let msg = `${r.extracted} dosyadan metin çıkarıldı, ${r.analyzed} dosya AI ile analiz edildi`;
    if (!r.ai_enabled) msg += " — AI analizi için API anahtarı gerekli";
    if (r.errors.length) msg += ` (${r.errors.length} hata)`;
    toast(msg, false);
    loadDataroom();
  } catch (err) {
    toast(err.message, true);
  } finally {
    btn.disabled = false;
    btn.innerHTML = old;
  }
};

// ---- Sağ panel: dosya inceleme (inspector) ----

function closeInspector() {
  dr.inspectorPath = null;
  $("#dr-inspector").style.display = "none";
  $("#dr-inspector").innerHTML = "";
  renderDataroom();
}

async function openInspector(file, rerenderTable = true) {
  dr.inspectorPath = file.path;
  if (rerenderTable) renderDataroom();
  const panel = $("#dr-inspector");
  panel.style.display = "flex";
  const shareInfo = file.share_token
    ? `<div class="dr-share-live">
        <span class="dr-shared">${DRI.link} Paylaşımda</span>
        <span class="dr-muted">${file.share_expires ? "Bitiş: " + new Date(file.share_expires).toLocaleString("tr-TR") : "Süresiz"} · ${file.share_downloads || 0} indirme</span>
        <div class="dr-insp-row">
          <button class="dr-btn" id="insp-copy-link">Linki Kopyala</button>
          <button class="dr-btn danger" id="insp-revoke">İptal Et</button>
        </div>
      </div>`
    : `<div class="dr-share-live">
        <span class="dr-muted">Paylaşım linki yok.</span>
        <div class="dr-insp-row">
          <select id="insp-expiry" class="dr-select">
            <option value="0">Süresiz</option>
            <option value="1">1 gün</option>
            <option value="7" selected>7 gün</option>
            <option value="30">30 gün</option>
          </select>
          <button class="dr-btn primary" id="insp-share">Link Oluştur</button>
        </div>
      </div>`;

  panel.innerHTML = `
    <div class="dr-insp-head">
      <span class="dr-file-icon dr-ic-${drTypeOf(file.filename)}">${drFileIcon(file.filename)}</span>
      <div class="dr-insp-title">
        <h3>${esc(file.filename)}</h3>
        <span class="dr-muted dr-mono">${formatSize(file.size)} · ${drDate(file.modified)}</span>
      </div>
      <button class="dr-icon-btn" id="insp-close" title="Kapat" aria-label="Kapat">${DRI.x}</button>
    </div>

    <div class="dr-insp-actions">
      <button class="dr-btn" id="insp-preview">${DRI.eye}<span>Önizle</span></button>
      <a class="dr-btn" href="/api/dataroom/download?path=${encodeURIComponent(file.path)}">${DRI.download}<span>İndir</span></a>
      <button class="dr-btn" id="insp-send">${DRI.send}<span>Mail At</span></button>
      <button class="dr-btn" id="insp-move">${DRI.move}<span>Taşı</span></button>
      <button class="dr-btn danger" id="insp-delete">${DRI.trash}<span>Sil</span></button>
    </div>

    <div class="dr-insp-section">
      <h4>AI Analizi</h4>
      ${file.doc_type || file.ai_summary
        ? `<div class="dr-ai-box">
            <div class="dr-ai-meta">
              ${file.doc_type ? `<span class="dr-doctype">${esc(file.doc_type)}</span>` : ""}
              ${file.doc_date ? `<span class="dr-muted dr-mono">${esc(file.doc_date)}</span>` : ""}
            </div>
            ${file.doc_amount ? `<div class="dr-amount lg">${esc(file.doc_amount)}</div>` : ""}
            ${file.ai_summary ? `<p>${esc(file.ai_summary)}</p>` : ""}
          </div>`
        : `<p class="dr-hint">Henüz analiz edilmedi — araç çubuğundaki "AI Tara" tüm arşivden metin çıkarır ve belgeleri sınıflandırır.</p>`}
    </div>

    <div class="dr-insp-section">
      <h4>Paylaşım</h4>
      ${shareInfo}
    </div>

    <div class="dr-insp-section">
      <h4>Açıklama & Etiketler</h4>
      <textarea id="insp-desc" rows="2" placeholder="Kısa açıklama...">${esc(file.note || "")}</textarea>
      <input id="insp-tags" placeholder="Etiketler (virgülle: sözleşme, acil)" value="${esc((file.tags || []).join(", "))}">
      <button class="dr-btn" id="insp-save-meta">Kaydet</button>
    </div>

    <div class="dr-insp-section dr-notes-section">
      <h4>Notlar</h4>
      <div id="insp-notes" class="dr-notes"><p class="dr-hint">Yükleniyor...</p></div>
      <div class="dr-note-form">
        <input id="insp-note-author" value="${esc(config.USER_NAME)}" readonly title="Yazar">
        <textarea id="insp-note-text" rows="2" placeholder="Not ekle..."></textarea>
        <button class="dr-btn primary" id="insp-add-note">Ekle</button>
      </div>
    </div>`;

  $("#insp-close").onclick = closeInspector;
  $("#insp-preview").onclick = () => openPreviewModal(file);
  $("#insp-send").onclick = () => openSendModal(file);
  $("#insp-move").onclick = () => openMoveModal(file);
  $("#insp-delete").onclick = async () => {
    if (!confirm(`"${file.filename}" kalıcı olarak silinsin mi?`)) return;
    await api(`/api/dataroom/file?path=${encodeURIComponent(file.path)}`, { method: "DELETE" });
    toast("Dosya silindi");
    closeInspector();
    loadDataroom();
  };
  $("#insp-save-meta").onclick = async () => {
    await api("/api/dataroom/note", { method: "POST",
      body: JSON.stringify({ path: file.path, note: $("#insp-desc").value, tags: $("#insp-tags").value }) });
    toast("Kaydedildi");
    loadDataroom();
  };

  if (file.share_token) {
    $("#insp-copy-link").onclick = async () => {
      const url = window.location.origin + "/share/" + file.share_token;
      try { await navigator.clipboard.writeText(url); toast("Link kopyalandı"); }
      catch { toast(url, false); }
    };
    $("#insp-revoke").onclick = async () => {
      await api(`/api/dataroom/share?path=${encodeURIComponent(file.path)}`, { method: "DELETE" });
      toast("Paylaşım linki iptal edildi");
      loadDataroom();
    };
  } else {
    $("#insp-share").onclick = async () => {
      const data = await api("/api/dataroom/share", { method: "POST",
        body: JSON.stringify({ path: file.path, expires_days: parseInt($("#insp-expiry").value) }) });
      const url = window.location.origin + data.url;
      try { await navigator.clipboard.writeText(url); toast("Link oluşturuldu ve kopyalandı"); }
      catch { toast("Link oluşturuldu: " + url); }
      loadDataroom();
    };
  }

  loadInspectorNotes(file.path);
}

async function loadInspectorNotes(path) {
  try {
    const data = await api(`/api/dataroom/notes?path=${encodeURIComponent(path)}`);
    const holder = $("#insp-notes");
    if (!holder) return;
    if (!data.notes.length) {
      holder.innerHTML = `<p class="dr-hint">Henüz not yok.</p>`;
      return;
    }
    holder.innerHTML = data.notes.map((n) => `
      <div class="dr-note">
        <div class="dr-note-head">
          <span class="dr-note-author">${DRI.user} ${esc(n.author || "Anonim")}</span>
          <span class="dr-note-time">${DRI.clock} ${relTime(n.created_at)}</span>
          <button class="dr-icon-btn sm" data-delnote="${n.id}" title="Notu sil" aria-label="Notu sil">${DRI.x}</button>
        </div>
        <div class="dr-note-body">${esc(n.content)}</div>
      </div>`).join("");
    holder.querySelectorAll("[data-delnote]").forEach((btn) => {
      btn.onclick = async () => {
        await api(`/api/dataroom/notes/${btn.dataset.delnote}`, { method: "DELETE" });
        loadInspectorNotes(path);
      };
    });
  } catch { /* panel kapanmış olabilir */ }
}

// Not ekleme (inspector içinden — event delegation)
document.addEventListener("click", async (ev) => {
  if (ev.target.id !== "insp-add-note") return;
  const text = $("#insp-note-text").value.trim();
  if (!text) return toast("Not boş olamaz", true);
  await api("/api/dataroom/notes", { method: "POST",
    body: JSON.stringify({ path: dr.inspectorPath, author: $("#insp-note-author").value, content: text }) });
  $("#insp-note-text").value = "";
  loadInspectorNotes(dr.inspectorPath);
});

// ---- Toplu işlemler ----

$("#dr-bulk-clear").onclick = () => { dr.selected.clear(); renderDataroom(); };
$("#dr-bulk-zip").onclick = async () => {
  try {
    const res = await fetch("/api/dataroom/zip", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paths: [...dr.selected] }),
    });
    if (!res.ok) throw new Error("ZIP oluşturulamadı");
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "dataroom.zip";
    a.click();
    URL.revokeObjectURL(a.href);
    toast(`${dr.selected.size} dosya ZIP olarak indirildi`);
  } catch (err) { toast(err.message, true); }
};
$("#dr-bulk-delete").onclick = async () => {
  if (!confirm(`${dr.selected.size} dosya kalıcı olarak silinsin mi?`)) return;
  const data = await api("/api/dataroom/bulk-delete", {
    method: "POST", body: JSON.stringify({ paths: [...dr.selected] }),
  });
  toast(`${data.deleted} dosya silindi`);
  dr.selected.clear();
  closeInspector();
  loadDataroom();
};

// ---- Yükleme + yeni klasör ----

$("#upload-btn").onclick = () => $("#upload-input").click();
$("#upload-input").onchange = async () => {
  const input = $("#upload-input");
  if (!input.files.length) return;
  const fd = new FormData();
  for (const f of input.files) fd.append("files", f);
  if (dr.folder) fd.append("folder", dr.folder);
  const btn = $("#upload-btn");
  btn.disabled = true;
  try {
    const res = await fetch("/api/dataroom/upload", { method: "POST", body: fd });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Hata: ${res.status}`);
    toast(`${data.files.length} dosya yüklendi`);
    loadDataroom();
  } catch (err) { toast(err.message, true); }
  finally { btn.disabled = false; input.value = ""; }
};

$("#dr-new-folder").onclick = () => {
  openModal(`
    <h3>Yeni Klasör</h3>
    <div class="modal-sub">${dr.folder ? `Şurada: ${esc(dr.folder)}` : "Kök dizinde"}</div>
    <div class="form-col"><input id="nf-name" placeholder="Klasör adı"></div>
    <div class="modal-actions">
      <button class="pill ghost" onclick="closeModal()">Vazgeç</button>
      <button class="pill accent" id="nf-save">Oluştur</button>
    </div>`);
  $("#nf-name").focus();
  $("#nf-save").onclick = async () => {
    const name = $("#nf-name").value.trim();
    if (!name) return toast("Klasör adı gerekli", true);
    const full = dr.folder ? `${dr.folder}/${name}` : name;
    await api("/api/dataroom/folder", { method: "POST", body: JSON.stringify({ folder: full }) });
    toast("Klasör oluşturuldu");
    closeModal();
    loadDataroom();
  };
};

// ---- Önizleme / taşıma / mail atma pencereleri ----

function openPreviewModal(file) {
  const t = drTypeOf(file.filename);
  const ext = (file.filename.split(".").pop() || "").toLowerCase();
  const url = `/api/dataroom/view?path=${encodeURIComponent(file.path)}`;
  const previewable = t === "pdf" || t === "image" || ["txt", "csv", "md", "html"].includes(ext);
  openModal(`
    <h3>${esc(file.filename)}</h3>
    <div class="modal-sub">${formatSize(file.size)} · ${esc(file.folder === "." ? "kök" : file.folder)}</div>
    ${previewable
      ? `<iframe id="preview-frame" src="${url}" title="Önizleme"></iframe>`
      : `<p class="hint">Bu dosya türü tarayıcıda önizlenemiyor — indirerek açabilirsiniz.</p>`}
    <div class="modal-actions">
      <a class="pill ghost" href="/api/dataroom/download?path=${encodeURIComponent(file.path)}">İndir</a>
      <button class="pill accent" onclick="closeModal()">Kapat</button>
    </div>`);
  $("#modal").classList.add("modal-wide");
}

function openMoveModal(file) {
  const options = [`<option value="">(Kök dizin)</option>`]
    .concat(dr.folders.map((f) => `<option value="${esc(f)}" ${f === file.folder ? "selected" : ""}>${esc(f)}</option>`));
  openModal(`
    <h3>Taşı — ${esc(file.filename)}</h3>
    <div class="form-col">
      <select id="move-target">${options.join("")}</select>
      <input id="move-new" placeholder="...veya yeni klasör adı yazın">
    </div>
    <div class="modal-actions">
      <button class="pill ghost" onclick="closeModal()">Vazgeç</button>
      <button class="pill accent" id="move-save">Taşı</button>
    </div>`);
  $("#move-save").onclick = async () => {
    const folder = $("#move-new").value.trim() || $("#move-target").value;
    try {
      const data = await api("/api/dataroom/move", { method: "POST",
        body: JSON.stringify({ path: file.path, folder }) });
      dr.inspectorPath = data.path;
      toast("Dosya taşındı");
      closeModal();
      loadDataroom();
    } catch (err) { toast(err.message, true); }
  };
}

function openSendModal(file) {
  if (!state.accounts.length) {
    return toast("Önce Hesaplar sekmesinden bir mail hesabı ekleyin", true);
  }
  const accountOptions = state.accounts
    .map((a) => `<option value="${a.id}">${esc(a.display_name || a.email)}</option>`)
    .join("");
  openModal(`
    <h3>Belgeyi Mail At</h3>
    <div class="modal-sub">Ek: ${esc(file.filename)} (${formatSize(file.size)})</div>
    <div class="form-col">
      <select id="send-account">${accountOptions}</select>
      <input id="send-to" type="email" placeholder="Alıcı adresi">
      <input id="send-subject" placeholder="Konu" value="Belge: ${esc(file.filename)}">
      <textarea id="send-message" placeholder="Mesaj (isteğe bağlı)"></textarea>
    </div>
    <div class="modal-actions">
      <button class="pill ghost" onclick="closeModal()">Vazgeç</button>
      <button class="pill accent" id="send-file-btn">Gönder</button>
    </div>`);
  $("#send-file-btn").onclick = async () => {
    const to = $("#send-to").value.trim();
    if (!to) return toast("Alıcı adresi gerekli", true);
    const btn = $("#send-file-btn");
    btn.disabled = true; btn.textContent = "Gönderiliyor...";
    try {
      await api("/api/dataroom/send", { method: "POST",
        body: JSON.stringify({
          path: file.path, to,
          subject: $("#send-subject").value,
          message: $("#send-message").value,
          account_id: parseInt($("#send-account").value),
        }) });
      toast(`"${file.filename}" ${to} adresine gönderildi`);
      closeModal();
      loadDataroom();
    } catch (err) {
      toast(err.message, true);
      btn.disabled = false; btn.textContent = "Gönder";
    }
  };
}

// ---- Toplu mail ----

const bulk = { uploadId: null, columns: [], total: 0, valid: 0, rows: [], sending: false };

async function loadBulk() {
  const sel = $("#bulk-account");
  try {
    const r = await api("/api/accounts");
    state.accounts = r.accounts;
  } catch { /* mevcut listeyi kullan */ }
  const accounts = state.accounts || [];
  if (!accounts.length) {
    sel.innerHTML = '<option value="">Önce bir mail hesabı ekleyin</option>';
    return;
  }
  sel.innerHTML = accounts
    .map((a) => `<option value="${a.id}">${esc(a.display_name || a.email)} — ${esc(a.email)}</option>`)
    .join("");
}

// --- dosya yükleme ---
$("#bulk-drop").onclick = () => $("#bulk-file").click();
$("#bulk-file").onchange = (e) => { if (e.target.files[0]) uploadBulkFile(e.target.files[0]); };
["dragover", "dragleave", "drop"].forEach((ev) => {
  $("#bulk-drop").addEventListener(ev, (e) => {
    e.preventDefault();
    $("#bulk-drop").classList.toggle("over", ev === "dragover");
    if (ev === "drop" && e.dataTransfer.files[0]) uploadBulkFile(e.dataTransfer.files[0]);
  });
});

async function uploadBulkFile(file) {
  const info = $("#bulk-file-info");
  info.style.display = "";
  info.innerHTML = '<p class="hint">Okunuyor…</p>';
  const fd = new FormData();
  fd.append("file", file);
  try {
    const res = await fetch("/api/bulk/upload", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Yüklenemedi");
    bulk.uploadId = data.upload_id;
    bulk.columns = data.columns;
    bulk.total = data.total;
    bulk.valid = data.valid;
    bulk.rows = data.preview;
    info.innerHTML = `<div class="bulk-fileinfo">
      <span class="bulk-fi-name">📄 ${esc(data.filename)}</span>
      <span class="bulk-fi-stat"><b>${data.total}</b> satır</span>
      <span class="bulk-fi-stat ok"><b>${data.valid}</b> geçerli e-posta</span>
      ${data.total - data.valid > 0 ? `<span class="bulk-fi-stat warn"><b>${data.total - data.valid}</b> atlanacak</span>` : ""}
      <button class="pill mini" id="bulk-clear">Değiştir</button></div>`;
    $("#bulk-clear").onclick = resetBulk;
    renderBulkPreview(data.preview, data.columns);
    fillBulkColumns(data.columns, data.guessed_email_column,
      data.guessed_subject_column, data.guessed_body_column);
    $("#bulk-compose").style.display = "";
    $("#bulk-sendcard").style.display = "";
    updateBulkSummary();
  } catch (e) {
    info.innerHTML = `<p class="auth-error">${esc(e.message)}</p>`;
  }
}

function resetBulk() {
  bulk.uploadId = null;
  $("#bulk-file").value = "";
  $("#bulk-file-info").style.display = "none";
  $("#bulk-preview").innerHTML = "";
  $("#bulk-compose").style.display = "none";
  $("#bulk-sendcard").style.display = "none";
  $("#bulk-progress").style.display = "none";
}

function renderBulkPreview(rows, columns) {
  if (!rows.length) return;
  $("#bulk-preview").innerHTML = `<div class="bulk-table-wrap"><table class="bulk-table">
    <thead><tr>${columns.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead>
    <tbody>${rows.map((r) => `<tr>${columns.map((c) => `<td>${esc(r[c] || "")}</td>`).join("")}</tr>`).join("")}</tbody>
    </table></div><p class="hint">İlk ${rows.length} satır gösteriliyor.</p>`;
}

function fillBulkColumns(columns, guessedEmail, guessedSubject, guessedBody) {
  $("#bulk-email-col").innerHTML = columns
    .map((c) => `<option value="${esc(c)}"${c === guessedEmail ? " selected" : ""}>${esc(c)}</option>`).join("");

  const opt = ['<option value="">Sabit metin kullan</option>',
    ...columns.map((c) => `<option value="${esc(c)}">${esc(c)}</option>`),
  ].join("");
  $("#bulk-subject-col").innerHTML = opt;
  $("#bulk-body-col").innerHTML = opt;
  if (guessedSubject && columns.includes(guessedSubject)) $("#bulk-subject-col").value = guessedSubject;
  if (guessedBody && columns.includes(guessedBody)) $("#bulk-body-col").value = guessedBody;

  $("#bulk-chips").innerHTML = columns
    .map((c) => `<button class="bulk-chip" data-col="${esc(c)}">{${esc(c)}}</button>`).join("");
  $("#bulk-chips").querySelectorAll(".bulk-chip").forEach((chip) => {
    chip.onclick = () => insertPlaceholder(`{${chip.dataset.col}}`);
  });
}

function resolveBulkText(row, colId, inputId) {
  const col = $(colId).value;
  return col ? String(row[col] || "") : $(inputId).value;
}

function insertPlaceholder(text) {
  const el = document.activeElement;
  const target = (el && (el.id === "bulk-subject" || el.id === "bulk-body")) ? el : $("#bulk-body");
  const start = target.selectionStart ?? target.value.length;
  const end = target.selectionEnd ?? target.value.length;
  target.value = target.value.slice(0, start) + text + target.value.slice(end);
  target.focus();
  target.setSelectionRange(start + text.length, start + text.length);
}

$("#bulk-email-col").onchange = async () => {
  try {
    const r = await api("/api/bulk/count", { method: "POST", body: JSON.stringify(bulkPayload()) });
    bulk.valid = r.valid;
    updateBulkSummary();
  } catch { /* yoksay */ }
};
$("#bulk-subject-col").onchange = updateBulkSummary;
$("#bulk-body-col").onchange = updateBulkSummary;

function bulkPayload(extra = {}) {
  return {
    upload_id: bulk.uploadId,
    account_id: parseInt($("#bulk-account").value || "0", 10),
    email_column: $("#bulk-email-col").value,
    subject: $("#bulk-subject").value,
    body: $("#bulk-body").value,
    subject_column: $("#bulk-subject-col").value,
    body_column: $("#bulk-body-col").value,
    is_html: $("#bulk-html").checked,
    from_name: $("#bulk-from-name").value,
    delay_ms: parseInt($("#bulk-delay").value, 10),
    ...extra,
  };
}

function updateBulkSummary() {
  const acc = (state.accounts || []).find((a) => String(a.id) === $("#bulk-account").value);
  const mins = Math.ceil((bulk.valid * parseInt($("#bulk-delay").value, 10)) / 60000);
  $("#bulk-summary").innerHTML =
    `<b>${bulk.valid}</b> alıcıya gönderilecek${acc ? ` — <b>${esc(acc.email)}</b> hesabından` : ""}. ` +
    `Tahmini süre: ~${mins} dakika.`;
}
$("#bulk-delay").onchange = updateBulkSummary;
$("#bulk-account").onchange = updateBulkSummary;

// --- önizleme ---
$("#bulk-preview-btn").onclick = () => {
  const row = bulk.rows[0] || {};
  const render = (t) => (t || "").replace(/\{\s*([^}]+?)\s*\}/g, (m, k) => (row[k] ?? ""));
  const box = $("#bulk-render-preview");
  box.style.display = "";
  const subject = render(resolveBulkText(row, "#bulk-subject-col", "#bulk-subject"));
  const body = render(resolveBulkText(row, "#bulk-body-col", "#bulk-body"));
  box.innerHTML = `<div class="bulk-prev-mail">
    <div class="bulk-prev-head">
      <span class="bulk-prev-to">Kime: ${esc(row[$("#bulk-email-col").value] || "—")}</span>
      <span class="bulk-prev-sub">${esc(subject) || "(konu yok)"}</span>
    </div>
    <div class="bulk-prev-body">${$("#bulk-html").checked ? body : esc(body).replace(/\n/g, "<br>")}</div>
  </div><p class="hint">İlk satırın verisiyle önizleme.</p>`;
};

// --- deneme maili ---
$("#bulk-test-btn").onclick = async () => {
  const to = $("#bulk-test-to").value.trim();
  if (!to) { toast("Deneme adresi girin", true); return; }
  const btn = $("#bulk-test-btn");
  btn.disabled = true; btn.textContent = "Gönderiliyor…";
  try {
    await api("/api/bulk/send", { method: "POST", body: JSON.stringify(bulkPayload({ test_to: to })) });
    toast(`Deneme maili ${to} adresine gönderildi ✓`);
  } catch (e) {
    toast(e.message, true);
  } finally {
    btn.disabled = false; btn.textContent = "Deneme Gönder";
  }
};

// --- toplu gönderim (NDJSON akışı) ---
$("#bulk-send-btn").onclick = async () => {
  if (bulk.sending) return;
  if (!$("#bulk-subject-col").value && !$("#bulk-subject").value.trim()) {
    toast("Konu için sütun seçin veya sabit konu girin", true); return;
  }
  if (!$("#bulk-body-col").value && !$("#bulk-body").value.trim()) {
    toast("Mesaj için sütun seçin veya sabit mesaj girin", true); return;
  }
  if (!confirm(`${bulk.valid} kişiye mail gönderilecek. Devam edilsin mi?`)) return;

  bulk.sending = true;
  const btn = $("#bulk-send-btn");
  btn.disabled = true; btn.textContent = "Gönderiliyor…";
  $("#bulk-progress").style.display = "";
  $("#bulk-log").innerHTML = "";
  $("#bulk-bar-fill").style.width = "0%";
  let sent = 0, failed = 0, skipped = 0, total = bulk.valid;

  const paint = (done) => {
    $("#bulk-bar-fill").style.width = total ? `${Math.round((done / total) * 100)}%` : "0%";
    $("#bulk-stats").innerHTML =
      `<span class="ok">✓ ${sent} gönderildi</span>` +
      (failed ? `<span class="bad">✕ ${failed} başarısız</span>` : "") +
      (skipped ? `<span class="muted">− ${skipped} atlandı</span>` : "");
  };

  try {
    const res = await fetch("/api/bulk/send", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(bulkPayload()),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Gönderim başlatılamadı");
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop();
      for (const line of lines) {
        if (!line.trim()) continue;
        let ev; try { ev = JSON.parse(line); } catch { continue; }
        if (ev.type === "start") { total = ev.total; paint(0); }
        else if (ev.type === "progress") {
          if (ev.status === "sent") sent++;
          else if (ev.status === "failed") failed++;
          else skipped++;
          const cls = ev.status === "sent" ? "ok" : ev.status === "failed" ? "bad" : "muted";
          const icon = ev.status === "sent" ? "✓" : ev.status === "failed" ? "✕" : "−";
          const log = $("#bulk-log");
          log.insertAdjacentHTML("beforeend",
            `<div class="bulk-log-row ${cls}"><span>${icon}</span><span>${esc(ev.email)}</span>` +
            `${ev.error ? `<em>${esc(ev.error)}</em>` : ""}</div>`);
          log.scrollTop = log.scrollHeight;
          paint(sent + failed + skipped);
        } else if (ev.type === "done") {
          paint(total);
          toast(`Tamamlandı — ${ev.sent} gönderildi${ev.failed ? `, ${ev.failed} başarısız` : ""}`);
        } else if (ev.type === "error") {
          toast(ev.error, true);
        }
      }
    }
  } catch (e) {
    toast(e.message, true);
  } finally {
    bulk.sending = false;
    btn.disabled = false; btn.textContent = "Toplu Gönderimi Başlat";
  }
};

// ---- Hesaplar ----

const PROVIDER_HINTS = {
  gmail: 'Gmail için normal şifreniz çalışmaz — <a href="https://myaccount.google.com/apppasswords" target="_blank">uygulama şifresi</a> oluşturun (2 Adımlı Doğrulama açık olmalı).',
  "ms-oauth": "Şifre gerekmez: Microsoft girişiyle (OAuth) bağlanır. Microsoft, Nisan 2026'da IMAP/SMTP için şifreyle girişi kapattığından Outlook/M365 hesapları yalnızca bu yolla eklenebilir. Sunucuda MS_CLIENT_ID tanımlı olmalı — kurulum adımları README'de.",
  yahoo: 'Yahoo için <a href="https://login.yahoo.com/account/security" target="_blank">uygulama şifresi</a> oluşturmanız gerekir.',
  yandex: "Yandex için hesap ayarlarından IMAP erişimini açın ve uygulama şifresi oluşturun.",
  custom: "Şirket mail sunucunuzun IMAP/SMTP adreslerini BT ekibinizden öğrenebilirsiniz. IMAP genellikle 993 (SSL), SMTP 465 (SSL) veya 587 (STARTTLS) portunu kullanır. Şirketiniz Microsoft 365 kullanıyorsa bu seçenek çalışmaz — 'Microsoft ile giriş' seçeneğini kullanın.",
};

async function loadAccounts() {
  const data = await api("/api/accounts");
  state.accounts = data.accounts;
  const holder = $("#account-cards");
  if (!data.accounts.length) {
    holder.innerHTML = `<p class="hint">Henüz hesap eklenmedi. Aşağıdaki formdan ilk hesabınızı ekleyin.</p>`;
  } else {
    holder.innerHTML = data.accounts
      .map((a) => `
        <div class="account-card">
          ${avatarHtml(a.display_name, a.email)}
          <div class="info">
            <div class="name">${esc(a.display_name || a.email)}${a.auth_type === "oauth-ms" ? ' <span class="badge acct">Microsoft OAuth</span>' : ""}</div>
            <div class="detail">${esc(a.email)} · IMAP: ${esc(a.imap_host)}:${a.imap_port} · SMTP: ${esc(a.smtp_host)}:${a.smtp_port} (${esc(a.smtp_security)})</div>
          </div>
          <button class="pill danger-ghost" data-del="${a.id}">Kaldır</button>
        </div>`)
      .join("");
    holder.querySelectorAll("[data-del]").forEach((btn) => {
      btn.onclick = async () => {
        if (!confirm("Bu hesap kaldırılsın mı? (Çekilmiş mailler silinmez)")) return;
        await api(`/api/accounts/${btn.dataset.del}`, { method: "DELETE" });
        toast("Hesap kaldırıldı");
        loadAccounts();
        loadEmails();
      };
    });
  }
  renderFilters();
}

$("#acc-provider").onchange = () => {
  const p = $("#acc-provider").value;
  const oauth = p === "ms-oauth";
  $("#custom-fields").style.display = p === "custom" ? "grid" : "none";
  $("#acc-email").parentElement.style.display = oauth ? "none" : "";
  $("#acc-password").parentElement.style.display = oauth ? "none" : "";
  $("#acc-save").textContent = oauth ? "Microsoft ile Bağlan" : "Bağlantıyı Test Et ve Ekle";
  $("#provider-hint").innerHTML = PROVIDER_HINTS[p] || "";
};
$("#acc-provider").onchange();

async function startMsOauth(displayName) {
  let flow;
  try {
    flow = await api("/api/accounts/oauth/ms/start", { method: "POST" });
  } catch (err) { return toast(err.message, true); }
  openModal(`
    <h3>Microsoft ile Bağlan</h3>
    <div class="form-col" style="text-align:center">
      <p style="font-size:13.5px">Aşağıdaki adrese gidin ve bu kodu girin; girişi tamamlayınca hesap otomatik eklenecek.</p>
      <a href="${esc(flow.verification_uri)}" target="_blank" style="font-weight:650">${esc(flow.verification_uri)}</a>
      <div id="ms-code" style="font-family:'Fira Code',monospace;font-size:26px;font-weight:600;letter-spacing:3px;padding:12px;border:1px dashed var(--border);border-radius:10px;user-select:all">${esc(flow.user_code)}</div>
      <p class="hint" id="ms-status">Giriş bekleniyor... Bu pencereyi kapatmayın.</p>
    </div>
    <div class="modal-actions">
      <button class="pill ghost" id="ms-cancel">Vazgeç</button>
    </div>`);
  let stopped = false;
  $("#ms-cancel").onclick = () => { stopped = true; closeModal(); };
  while (!stopped) {
    await new Promise((r) => setTimeout(r, 3000));
    if (stopped) break;
    let s;
    try {
      s = await api("/api/accounts/oauth/ms/poll", { method: "POST",
        body: JSON.stringify({ flow_id: flow.flow_id, display_name: displayName }) });
    } catch (err) {
      closeModal();
      return toast(err.message, true);
    }
    if (s.status === "pending") continue;
    if (s.status === "error") {
      closeModal();
      return toast("Microsoft girişi tamamlanamadı: " + s.error, true);
    }
    closeModal();
    toast(`${s.email} bağlandı ✓ — Eşitle butonuyla mailleri getirebilirsiniz`);
    $("#acc-name").value = "";
    loadAccounts();
    return;
  }
}

$("#acc-save").onclick = async () => {
  const btn = $("#acc-save");
  const provider = $("#acc-provider").value;
  if (provider === "ms-oauth") return startMsOauth($("#acc-name").value);
  const payload = {
    display_name: $("#acc-name").value,
    email: $("#acc-email").value.trim(),
    password: $("#acc-password").value,
    provider,
  };
  if (!payload.email || !payload.password) return toast("E-posta ve şifre gerekli", true);
  if (provider === "custom") {
    payload.imap_host = $("#acc-imap-host").value.trim();
    payload.imap_port = parseInt($("#acc-imap-port").value) || 993;
    payload.smtp_host = $("#acc-smtp-host").value.trim();
    payload.smtp_port = parseInt($("#acc-smtp-port").value) || 465;
    payload.smtp_security = $("#acc-smtp-security").value;
    if (!payload.imap_host || !payload.smtp_host) return toast("IMAP ve SMTP sunucusu gerekli", true);
  }
  btn.disabled = true;
  btn.textContent = "Bağlantı test ediliyor...";
  try {
    await api("/api/accounts", { method: "POST", body: JSON.stringify(payload) });
    toast("Hesap eklendi ✓ — Eşitle butonuyla mailleri getirebilirsiniz");
    ["acc-name", "acc-email", "acc-password", "acc-imap-host", "acc-smtp-host"].forEach(
      (id) => ($("#" + id).value = "")
    );
    loadAccounts();
  } catch (err) {
    toast(err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = "Bağlantıyı Test Et ve Ekle";
  }
};

// ---- Takvim ----

const MONTHS_TR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
  "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];
const DAYS_TR = ["Pazar", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi"];

const ymd = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

function calColor(ev) {
  return ev.calendar_color || "#0f8a6d";
}

async function loadCalendar() {
  const { year, month } = state.cal;
  if (!state.cal.selected) state.cal.selected = ymd(new Date());
  // Izgara aralığı: ayın ilk gününün pazartesisi → +42 gün
  const first = new Date(year, month, 1);
  const gridStart = new Date(first);
  gridStart.setDate(first.getDate() - ((first.getDay() + 6) % 7));
  const gridEnd = new Date(gridStart);
  gridEnd.setDate(gridStart.getDate() + 42);
  const data = await api(`/api/events?start=${ymd(gridStart)}&end=${ymd(gridEnd)}T23:59`);
  state.cal.events = data.events;
  state.calendars = data.calendars;
  renderCalendarGrid(gridStart);
  renderDayAgenda();
  renderCalendarSources();
  renderEventCalendarSelect();
}

function eventsOnDay(dayStr) {
  return state.cal.events.filter((ev) => (ev.start || "").slice(0, 10) === dayStr);
}

function renderCalendarGrid(gridStart) {
  const { year, month } = state.cal;
  $("#cal-title").textContent = `${MONTHS_TR[month]} ${year}`;
  const todayStr = ymd(new Date());
  let html = "";
  for (let i = 0; i < 42; i++) {
    const d = new Date(gridStart);
    d.setDate(gridStart.getDate() + i);
    const dStr = ymd(d);
    const other = d.getMonth() !== month ? " other" : "";
    const today = dStr === todayStr ? " today" : "";
    const selected = dStr === state.cal.selected ? " selected" : "";
    const evs = eventsOnDay(dStr);
    const chips = evs.slice(0, 3)
      .map((ev) => `<div class="cal-event-chip" style="background:${calColor(ev)}">${ev.all_day ? "" : (ev.start || "").slice(11, 16) + " "}${esc(ev.title)}</div>`)
      .join("");
    const more = evs.length > 3 ? `<span class="cal-more">+${evs.length - 3} daha</span>` : "";
    html += `<div class="cal-cell${other}${today}${selected}" data-day="${dStr}">
      <span class="daynum">${d.getDate()}</span>${chips}${more}
    </div>`;
  }
  $("#cal-grid").innerHTML = html;
  document.querySelectorAll(".cal-cell").forEach((cell) => {
    cell.onclick = () => {
      state.cal.selected = cell.dataset.day;
      renderCalendarGrid(gridStart);
      renderDayAgenda();
    };
  });
}

function renderDayAgenda() {
  const dayStr = state.cal.selected;
  const d = new Date(dayStr + "T00:00");
  $("#cal-day-title").textContent =
    `${d.getDate()} ${MONTHS_TR[d.getMonth()]} ${DAYS_TR[d.getDay()]}`;
  const evs = eventsOnDay(dayStr).sort((a, b) => (a.start || "").localeCompare(b.start || ""));
  const holder = $("#cal-day-events");
  if (!evs.length) {
    holder.innerHTML = `<p class="hint">Bu günde etkinlik yok.</p>`;
    return;
  }
  holder.innerHTML = evs
    .map((ev) => {
      const time = ev.all_day
        ? "Tüm gün"
        : `${(ev.start || "").slice(11, 16)}${ev.end ? "–" + (ev.end || "").slice(11, 16) : ""}`;
      const calName = ev.calendar_name || "Meil";
      const deletable = ev.source !== "sync";
      return `<div class="day-event">
        <span class="bar" style="background:${calColor(ev)}"></span>
        <div class="ev-body">
          <div class="ev-title">${esc(ev.title)}</div>
          <div class="ev-meta">${time} · ${esc(calName)}${ev.location ? " · " + MI.pin + " " + esc(ev.location) : ""}</div>
        </div>
        ${deletable ? `<button class="ev-del" data-ev="${ev.id}" title="Sil">${MI.x}</button>` : ""}
      </div>`;
    })
    .join("");
  holder.querySelectorAll(".ev-del").forEach((btn) => {
    btn.onclick = async () => {
      if (!confirm("Etkinlik silinsin mi?")) return;
      await api(`/api/events/${btn.dataset.ev}`, { method: "DELETE" });
      toast("Etkinlik silindi");
      loadCalendar();
    };
  });
}

function renderCalendarSources() {
  const holder = $("#calendar-sources");
  if (!state.calendars.length) {
    holder.innerHTML = `<p class="hint">Henüz takvim bağlanmadı. Mailden eklenen etkinlikler yerel "Meil" takviminde tutulur.</p>`;
    return;
  }
  const typeLabel = { icloud: "iCloud", ics: "ICS", local: "yerel" };
  holder.innerHTML = state.calendars
    .map((c) => `<div class="cal-source-row">
      <span class="dot" style="background:${c.color || "#0f8a6d"}"></span>
      <span class="src-name">${esc(c.name)}</span>
      <span class="src-type">${typeLabel[c.type] || c.type}</span>
      <button class="ev-del" data-cal="${c.id}" title="Kaldır">${MI.x}</button>
    </div>`)
    .join("");
  holder.querySelectorAll("[data-cal]").forEach((btn) => {
    btn.onclick = async () => {
      if (!confirm("Bu takvim ve etkinlikleri kaldırılsın mı?")) return;
      await api(`/api/calendars/${btn.dataset.cal}`, { method: "DELETE" });
      toast("Takvim kaldırıldı");
      loadCalendar();
    };
  });
}

function renderEventCalendarSelect() {
  const sel = $("#ev-calendar");
  const writable = state.calendars.filter((c) => c.type === "icloud");
  sel.innerHTML =
    `<option value="">Meil (yerel)</option>` +
    writable.map((c) => `<option value="${c.id}">${esc(c.name)} (iCloud)</option>`).join("");
}

$("#cal-prev").onclick = () => {
  state.cal.month--;
  if (state.cal.month < 0) { state.cal.month = 11; state.cal.year--; }
  loadCalendar();
};
$("#cal-next").onclick = () => {
  state.cal.month++;
  if (state.cal.month > 11) { state.cal.month = 0; state.cal.year++; }
  loadCalendar();
};
$("#cal-today").onclick = () => {
  const now = new Date();
  state.cal.year = now.getFullYear();
  state.cal.month = now.getMonth();
  state.cal.selected = ymd(now);
  loadCalendar();
};

$("#cal-sync").onclick = async () => {
  const btn = $("#cal-sync");
  btn.disabled = true;
  btn.innerHTML = MI.refresh + " Eşitleniyor...";
  try {
    const data = await api("/api/calendars/sync", { method: "POST" });
    const failed = data.results.filter((r) => r.error);
    let msg = `${data.total_events} etkinlik eşitlendi`;
    if (failed.length) msg += ` — hata: ${failed.map((r) => r.calendar).join(", ")}`;
    toast(msg, failed.length > 0 && data.total_events === 0);
    failed.forEach((r) => console.warn(r.calendar, r.error));
    loadCalendar();
  } catch (err) {
    toast(err.message, true);
  } finally {
    btn.disabled = false;
    btn.innerHTML = MI.refresh + " Takvimleri Eşitle";
  }
};

// Yeni etkinlik formu
$("#cal-new-event").onclick = () => {
  const card = $("#new-event-card");
  card.style.display = card.style.display === "none" ? "block" : "none";
  $("#ev-date").value = state.cal.selected || ymd(new Date());
};
$("#ev-cancel").onclick = () => ($("#new-event-card").style.display = "none");
$("#ev-save").onclick = async () => {
  const payload = {
    title: $("#ev-title").value.trim(),
    date: $("#ev-date").value,
    time: $("#ev-time").value,
    duration_minutes: parseInt($("#ev-duration").value) || 60,
    location: $("#ev-location").value.trim(),
    calendar_id: $("#ev-calendar").value ? parseInt($("#ev-calendar").value) : null,
  };
  if (!payload.title) return toast("Başlık gerekli", true);
  if (!payload.date) return toast("Tarih gerekli", true);
  try {
    const data = await api("/api/events", { method: "POST", body: JSON.stringify(payload) });
    toast(`Etkinlik "${data.calendar}" takvimine eklendi ✓`);
    $("#ev-title").value = ""; $("#ev-location").value = "";
    $("#new-event-card").style.display = "none";
    state.cal.selected = payload.date;
    loadCalendar();
  } catch (err) {
    toast(err.message, true);
  }
};

// Takvim kaynağı ekleme
const CAL_SRC_HINTS = {
  icloud: 'Apple Kimliğinizle giriş yapın; normal şifreniz çalışmaz — <a href="https://account.apple.com/account/manage" target="_blank">appleid.apple.com</a> → Oturum Açma ve Güvenlik → Uygulama Şifreleri bölümünden oluşturun. Hesabınızdaki tüm takvimler bağlanır ve etkinlik EKLENEBİLİR.',
  ics: 'Google Takvim → Ayarlar → takviminizi seçin → "Takvimi entegre et" → <strong>iCal biçiminde gizli adres</strong>i kopyalayıp yapıştırın. Salt okunurdur (görüntüleme).',
  "ics-generic": "Herhangi bir ICS/webcal adresi bağlayabilirsiniz (Outlook yayınlama bağlantısı, şirket takvimi vb.). Salt okunurdur.",
};

$("#cal-src-type").onchange = () => {
  const t = $("#cal-src-type").value;
  $("#cal-src-icloud").style.display = t === "icloud" ? "flex" : "none";
  $("#cal-src-ics").style.display = t === "icloud" ? "none" : "flex";
  $("#cal-src-hint").innerHTML = CAL_SRC_HINTS[t] || "";
};
$("#cal-src-type").onchange();

$("#cal-src-add").onclick = async () => {
  const btn = $("#cal-src-add");
  const t = $("#cal-src-type").value;
  const payload = t === "icloud"
    ? { type: "icloud", username: $("#cal-apple-id").value.trim(), password: $("#cal-apple-pass").value }
    : { type: "ics", name: $("#cal-ics-name").value.trim(), url: $("#cal-ics-url").value.trim() };
  if (t === "icloud" && (!payload.username || !payload.password))
    return toast("Apple ID ve uygulama şifresi gerekli", true);
  if (t !== "icloud" && !payload.url) return toast("ICS adresi gerekli", true);
  btn.disabled = true;
  btn.textContent = "Bağlanıyor...";
  try {
    const data = await api("/api/calendars", { method: "POST", body: JSON.stringify(payload) });
    toast(`Bağlandı: ${data.added.join(", ")} ✓ — etkinlikler eşitleniyor...`);
    ["cal-apple-id", "cal-apple-pass", "cal-ics-name", "cal-ics-url"].forEach(
      (id) => ($("#" + id).value = "")
    );
    try { await api("/api/calendars/sync", { method: "POST" }); } catch { /* ilk eşitleme başarısızsa manuel denenir */ }
    loadCalendar();
  } catch (err) {
    toast(err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = "Takvimi Bağla";
  }
};

// ---- Başlangıç ----

// ---- Giriş ekranı (PIN) ----

let authMode = "login"; // login | setup

function showAuthOverlay(mode) {
  authMode = mode;
  const setup = mode === "setup";
  twofaStage = false;
  pendingPin = "";
  $("#auth-overlay").style.display = "flex";
  $("#auth-error").textContent = "";
  $("#auth-caps").style.display = "none";
  $("#auth-pin").value = "";
  $("#auth-pin2").value = "";
  $("#auth-code").value = "";
  $("#auth-code").style.display = "none";
  document.querySelector(".auth-field").style.display = "";
  $("#auth-pin2").style.display = setup ? "" : "none";
  $("#auth-strength").style.display = setup ? "" : "none";
  $("#auth-pin").setAttribute("autocomplete", setup ? "new-password" : "current-password");
  $("#auth-pin").placeholder = setup ? "Yeni parola (en az 8 karakter)" : "Parola";
  $("#auth-title").textContent = setup ? "Meil'e Hoş Geldiniz" : "Meil";
  $("#auth-desc").textContent = setup
    ? "Uygulamanızı korumak için güçlü bir parola belirleyin. Mailleriniz ve belgeleriniz bu parolanın arkasında durur."
    : "Devam etmek için parolanızı girin.";
  $("#auth-submit").textContent = setup ? "Parolayı Belirle" : "Giriş";
  updateStrength();
  setTimeout(() => $("#auth-pin").focus(), 30);
}

function hideAuthOverlay() {
  clearInterval(lockTimer);
  $("#auth-overlay").style.display = "none";
}

function pwStrength(pw) {
  let s = 0;
  if (pw.length >= 8) s++;
  if (pw.length >= 12) s++;
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) s++;
  if (/\d/.test(pw)) s++;
  if (/[^A-Za-z0-9]/.test(pw)) s++;
  return Math.min(s, 4); // 0..4
}

function updateStrength() {
  if (authMode !== "setup") return;
  const pw = $("#auth-pin").value;
  const el = $("#auth-strength");
  const lvl = pwStrength(pw);
  const labels = ["Çok zayıf", "Zayıf", "Orta", "İyi", "Güçlü"];
  const colors = ["#ef4444", "#f97316", "#eab308", "#22c55e", "#16a34a"];
  el.querySelector("span").textContent = pw ? labels[lvl] : "";
  el.style.setProperty("--sw", (pw ? (lvl + 1) * 20 : 0) + "%");
  el.style.setProperty("--sc", colors[lvl]);
}

let lockTimer = null;
let twofaStage = false;
let pendingPin = "";

function enterTwofaStage() {
  twofaStage = true;
  document.querySelector(".auth-field").style.display = "none";
  $("#auth-strength").style.display = "none";
  $("#auth-pin2").style.display = "none";
  $("#auth-caps").style.display = "none";
  $("#auth-code").style.display = "";
  $("#auth-code").value = "";
  $("#auth-title").textContent = "İki adımlı doğrulama";
  $("#auth-desc").textContent = "Authenticator uygulamanızdaki 6 haneli kodu (veya bir kurtarma kodunu) girin.";
  $("#auth-submit").textContent = "Doğrula";
  $("#auth-error").textContent = "";
  setTimeout(() => $("#auth-code").focus(), 30);
}

function startLockCountdown(sec) {
  clearInterval(lockTimer);
  const err = $("#auth-error");
  const btn = $("#auth-submit");
  btn.disabled = true;
  const tick = () => {
    if (sec <= 0) {
      clearInterval(lockTimer);
      err.textContent = "";
      btn.disabled = false;
      return;
    }
    err.textContent = `Çok fazla hatalı deneme. ${sec} saniye sonra tekrar deneyin.`;
    sec--;
  };
  tick();
  lockTimer = setInterval(tick, 1000);
}

async function submitAuth() {
  const err = $("#auth-error");
  const btn = $("#auth-submit");
  err.textContent = "";

  // 2FA ikinci adımı — parola zaten doğrulandı, kod bekleniyor
  if (authMode === "login" && twofaStage) {
    const code = $("#auth-code").value.trim();
    if (!code) { err.textContent = "Doğrulama kodunu girin"; return; }
    btn.disabled = true;
    try {
      await api("/api/auth/login", { method: "POST", body: JSON.stringify({ pin: pendingPin, code }) });
      hideAuthOverlay();
      bootApp();
    } catch (e) {
      err.textContent = e.message;
      const m = /(\d+)\s*saniye/.exec(e.message || "");
      if (m) startLockCountdown(parseInt(m[1], 10));
    } finally {
      if (!lockTimer) btn.disabled = false;
    }
    return;
  }

  const pin = $("#auth-pin").value;
  if (authMode === "setup") {
    if (pin.length < 8) { err.textContent = "Parola en az 8 karakter olmalı"; return; }
    if (pin !== $("#auth-pin2").value) { err.textContent = "Parolalar eşleşmiyor"; return; }
  } else if (!pin) {
    err.textContent = "Parolanızı girin"; return;
  }
  btn.disabled = true;
  try {
    const r = await api(`/api/auth/${authMode === "setup" ? "setup" : "login"}`,
      { method: "POST", body: JSON.stringify({ pin }) });
    if (authMode === "login" && r && r.twofa_required) {
      pendingPin = pin;
      enterTwofaStage();
      btn.disabled = false;
      return;
    }
    hideAuthOverlay();
    if (authMode === "setup") toast("Parola belirlendi — uygulama artık korunuyor ✓");
    bootApp();
  } catch (e) {
    err.textContent = e.message;
    const m = /(\d+)\s*saniye/.exec(e.message || "");
    if (m) startLockCountdown(parseInt(m[1], 10));
  } finally {
    if (!lockTimer && !twofaStage) btn.disabled = false;
  }
}

function capsCheck(e) {
  const on = e.getModifierState && e.getModifierState("CapsLock");
  $("#auth-caps").style.display = on ? "" : "none";
}

$("#auth-pin").addEventListener("input", updateStrength);
$("#auth-pin").addEventListener("keyup", capsCheck);
$("#auth-pin2").addEventListener("keyup", capsCheck);
$("#auth-toggle").onclick = () => {
  const f = $("#auth-pin"), f2 = $("#auth-pin2");
  const show = f.type === "password";
  f.type = f2.type = show ? "text" : "password";
  $("#auth-toggle").textContent = show ? "🙈" : "👁";
};
$("#auth-submit").onclick = submitAuth;
$("#auth-pin").onkeydown = (e) => {
  if (e.key !== "Enter") return;
  if (authMode === "setup") $("#auth-pin2").focus(); else submitAuth();
};
$("#auth-pin2").onkeydown = (e) => { if (e.key === "Enter") submitAuth(); };
$("#auth-code").onkeydown = (e) => { if (e.key === "Enter") submitAuth(); };

// ---- İki adımlı doğrulama (modal) ----

const twofaOverlay = $("#twofa-overlay");
function closeTwofa() { twofaOverlay.hidden = true; }
$("#twofa-close").onclick = closeTwofa;
twofaOverlay.addEventListener("click", (e) => { if (e.target === twofaOverlay) closeTwofa(); });

async function refreshTwofaMenuTag() {
  try {
    const st = await api("/api/2fa/status");
    const tag = $("#twofa-state");
    if (tag) { tag.textContent = st.enabled ? "Açık" : "Kapalı"; tag.classList.toggle("on", st.enabled); }
  } catch { /* yoksay */ }
}

async function openTwofa() {
  $("#user-menu").hidden = true;
  twofaOverlay.hidden = false;
  const body = $("#twofa-body");
  body.innerHTML = '<p class="modal-muted">Yükleniyor…</p>';
  try {
    const st = await api("/api/2fa/status");
    if (st.enabled) renderTwofaOn(st); else renderTwofaOff();
  } catch (e) {
    body.innerHTML = `<p class="auth-error">${esc(e.message)}</p>`;
  }
}

function renderTwofaOff() {
  $("#twofa-body").innerHTML = `
    <p class="modal-muted">Parolanıza ek bir katman: girişte telefonunuzdaki Authenticator uygulamasından 6 haneli bir kod istenir. Böylece parolanız çalınsa bile hesabınıza girilemez.</p>
    <button class="pill accent modal-wide" id="tf-start">Etkinleştir</button>`;
  $("#tf-start").onclick = startTwofaSetup;
}

async function startTwofaSetup() {
  const body = $("#twofa-body");
  body.innerHTML = '<p class="modal-muted">Hazırlanıyor…</p>';
  let r;
  try { r = await api("/api/2fa/setup", { method: "POST" }); }
  catch (e) { body.innerHTML = `<p class="auth-error">${esc(e.message)}</p>`; return; }
  body.innerHTML = `
    <p class="modal-muted"><b>1.</b> Authenticator uygulamasında (Google Authenticator, Authy, 1Password…) QR'ı okutun veya anahtarı elle girin.</p>
    <div class="tf-qr">${r.qr_svg}</div>
    <div class="tf-secret"><span>Anahtar</span><code>${esc(r.secret)}</code></div>
    <p class="modal-muted"><b>2.</b> Uygulamadaki 6 haneli kodu girin:</p>
    <input id="tf-code" class="tf-input" inputmode="numeric" maxlength="6" placeholder="000000" autocomplete="one-time-code">
    <p class="auth-error" id="tf-err"></p>
    <button class="pill accent modal-wide" id="tf-verify">Doğrula ve Aç</button>`;
  const codeEl = $("#tf-code");
  setTimeout(() => codeEl.focus(), 30);
  const go = async () => {
    const code = codeEl.value.trim();
    if (code.length < 6) { $("#tf-err").textContent = "6 haneli kodu girin"; return; }
    $("#tf-verify").disabled = true;
    try {
      const res = await api("/api/2fa/enable", { method: "POST", body: JSON.stringify({ code }) });
      renderRecovery(res.recovery_codes);
      refreshTwofaMenuTag();
    } catch (e) { $("#tf-err").textContent = e.message; $("#tf-verify").disabled = false; }
  };
  $("#tf-verify").onclick = go;
  codeEl.onkeydown = (e) => { if (e.key === "Enter") go(); };
}

function renderRecovery(codes) {
  $("#twofa-body").innerHTML = `
    <p class="tf-ok">✓ İki adımlı doğrulama açıldı</p>
    <p class="modal-muted">Bu <b>kurtarma kodlarını</b> güvenli bir yere kaydedin. Telefonunuza erişemezseniz biriyle giriş yapabilirsiniz. Her kod <b>tek kullanımlıktır</b> ve bu ekran bir daha gösterilmez.</p>
    <div class="tf-codes">${codes.map((c) => `<code>${esc(c)}</code>`).join("")}</div>
    <button class="pill modal-wide" id="tf-copy">Kodları Kopyala</button>
    <button class="pill accent modal-wide" id="tf-done">Kaydettim, Bitti</button>`;
  $("#tf-copy").onclick = () => {
    (navigator.clipboard?.writeText(codes.join("\n")) || Promise.reject()).then(
      () => toast("Kurtarma kodları kopyalandı"), () => toast("Kopyalanamadı — elle kaydedin", true));
  };
  $("#tf-done").onclick = closeTwofa;
}

function renderTwofaOn(st) {
  $("#twofa-body").innerHTML = `
    <p class="tf-ok">✓ İki adımlı doğrulama açık</p>
    <p class="modal-muted">Girişte parolanıza ek olarak doğrulama kodu istenir. Kalan kurtarma kodu: <b>${st.recovery_left}</b>.</p>
    <p class="modal-muted">Kapatmak için parolanızı girin:</p>
    <input id="tf-pass" class="tf-input" type="password" placeholder="Parola" autocomplete="current-password">
    <p class="auth-error" id="tf-err"></p>
    <button class="pill danger modal-wide" id="tf-off">Kapat</button>`;
  const go = async () => {
    const pin = $("#tf-pass").value;
    if (!pin) { $("#tf-err").textContent = "Parolanızı girin"; return; }
    $("#tf-off").disabled = true;
    try {
      await api("/api/2fa/disable", { method: "POST", body: JSON.stringify({ pin }) });
      toast("İki adımlı doğrulama kapatıldı");
      refreshTwofaMenuTag();
      closeTwofa();
    } catch (e) { $("#tf-err").textContent = e.message; $("#tf-off").disabled = false; }
  };
  $("#tf-off").onclick = go;
  $("#tf-pass").onkeydown = (e) => { if (e.key === "Enter") go(); };
}

$("#twofa-btn").onclick = openTwofa;

// ---- Donna (asistan paneli) ----

const donna = { open: false, loading: false, history: [], briefed: false, notifications: [] };

function donnaOpen() {
  donna.open = true;
  $("#donna-panel").classList.add("open");
  $("#donna-panel").setAttribute("aria-hidden", "false");
  $("#donna-scrim").hidden = false;
  if (!donna.briefed) loadDonnaBrief();
  refreshNotifications();
  setTimeout(() => $("#donna-input").focus(), 260);
}

function donnaClose() {
  donna.open = false;
  $("#donna-panel").classList.remove("open");
  $("#donna-panel").setAttribute("aria-hidden", "true");
  $("#donna-scrim").hidden = true;
}

$("#donna-btn").onclick = () => (donna.open ? donnaClose() : donnaOpen());
$("#donna-close").onclick = donnaClose;
$("#donna-scrim").onclick = donnaClose;
$("#donna-refresh").onclick = () => { donna.briefed = false; loadDonnaBrief(); };
$("#donna-automations-btn").onclick = () => { if (!donna.open) donnaOpen(); loadAutomationsList(); };

// ---- Bildirimler (otomasyon uyarıları) ----

async function refreshNotifications() {
  try {
    const r = await api("/api/notifications");
    donna.notifications = r.notifications || [];
    $("#donna-dot").hidden = (r.unread_count || 0) === 0;
    if (donna.open && donna.briefed) renderNotifBlock();
  } catch { /* sessizce geç */ }
}

function renderNotifBlock() {
  const holder = $("#donna-notifs-slot");
  if (!holder) return;
  const unread = donna.notifications.filter((n) => !n.is_read);
  if (!unread.length) { holder.innerHTML = ""; return; }
  holder.innerHTML = `
    <div class="donna-notifs">
      <div class="dn-head">🔔 Bildirimler <button class="dn-readall">Tümünü okundu işaretle</button></div>
      ${unread.map((n) => `
        <div class="donna-notif" data-id="${n.id}">
          <div class="dn-body"><b>${esc(n.title)}</b><span>${esc(n.body)}</span></div>
          <button class="dn-read" title="Okundu işaretle">✓</button>
        </div>`).join("")}
    </div>`;
  holder.querySelector(".dn-readall").onclick = async () => {
    await api("/api/notifications/read-all", { method: "POST" });
    await refreshNotifications();
  };
  holder.querySelectorAll(".dn-read").forEach((btn) => {
    btn.onclick = async () => {
      const row = btn.closest(".donna-notif");
      await api(`/api/notifications/${row.dataset.id}/read`, { method: "POST" });
      await refreshNotifications();
    };
  });
}

const URGENCY = { acil: "u-high", normal: "u-mid", bilgi: "u-low" };
const KIND_ICON = { mail: "✉️", etkinlik: "📅", fatura: "🧾", hatirlatma: "🔔" };

function donnaAppend(html) {
  const body = $("#donna-body");
  body.insertAdjacentHTML("beforeend", html);
  body.scrollTop = body.scrollHeight;
}

async function loadDonnaBrief() {
  const body = $("#donna-body");
  body.innerHTML = `<div class="donna-loading"><span></span><span></span><span></span> Donna verilerine bakıyor…</div>`;
  try {
    const r = await api("/api/donna/brief");
    donna.briefed = true;
    const st = r.stats || {};
    const items = (r.items || []).map((it) => `
      <button class="donna-item ${URGENCY[it.urgency] || "u-mid"}" ${it.email_id ? `data-mail="${it.email_id}"` : ""}>
        <span class="di-ico">${KIND_ICON[it.kind] || "•"}</span>
        <span class="di-main">
          <b>${esc(it.title)}</b>
          <span>${esc(it.detail)}</span>
        </span>
        ${it.email_id ? '<span class="di-go">→</span>' : ""}
      </button>`).join("");
    body.innerHTML = `
      <div id="donna-notifs-slot"></div>
      <div class="donna-brief">
        <div class="donna-greet">${esc(r.greeting || "Merhaba")}</div>
        <div class="donna-headline">${esc(r.headline || "")}</div>
        <div class="donna-stats">
          <span><b>${st.needs_reply ?? 0}</b> yanıt bekliyor</span>
          <span><b>${st.today_events ?? 0}</b> bugün etkinlik</span>
          <span><b>${st.events_14d ?? 0}</b> 14 günde</span>
        </div>
        ${items ? `<div class="donna-items">${items}</div>`
                : '<p class="donna-calm">Şu an acil bir şey yok. Sakin bir gün. ☕</p>'}
      </div>`;
    body.querySelectorAll(".donna-item[data-mail]").forEach((el) => {
      el.onclick = () => openMailFromDonna(parseInt(el.dataset.mail, 10));
    });
    renderNotifBlock();
    setDonnaChips(["Bugün neler var?", "Acil yanıtlamam gerekenler?", "Bu hafta hangi ödemeler var?"]);
  } catch (e) {
    body.innerHTML = `<p class="auth-error donna-err">${esc(e.message)}</p>`;
  }
}

function setDonnaChips(list) {
  $("#donna-chips").innerHTML = (list || [])
    .map((q) => `<button class="donna-chip">${esc(q)}</button>`).join("");
  $("#donna-chips").querySelectorAll(".donna-chip").forEach((c) => {
    c.onclick = () => { $("#donna-input").value = c.textContent; askDonna(); };
  });
}

// ---- Otomasyonlarım (yönetim listesi) ----

async function loadAutomationsList() {
  const body = $("#donna-body");
  body.innerHTML = `<div class="donna-loading"><span></span><span></span><span></span> Otomasyonlar yükleniyor…</div>`;
  setDonnaChips([]);
  try {
    const r = await api("/api/automations");
    const list = r.automations || [];
    const rows = list.map((a) => `
      <div class="donna-auto ${a.status === "paused" ? "paused" : ""}" data-id="${a.id}">
        <div class="da2-main">
          <b>${esc(a.sender_name || a.sender_email || "Gönderen")}</b>
          <span>${esc(a.interval_text)} içinde yanıt gelmezse bildir ${a.waiting ? "· şu an bekleniyor" : ""}</span>
        </div>
        <div class="da2-btns">
          <button class="pill ghost sm da2-toggle">${a.status === "paused" ? "Etkinleştir" : "Duraklat"}</button>
          <button class="pill danger-ghost sm da2-del">Sil</button>
        </div>
      </div>`).join("");
    body.innerHTML = `
      <div class="donna-auto-list">
        <button class="link-btn da2-back">← Brifinge dön</button>
        <h4>Otomasyonlarım</h4>
        ${rows || '<p class="donna-calm">Henüz bir otomasyon yok. Donna\'ya "X\'ten 3 gün yanıt gelmezse bildir" gibi yazarak oluşturabilirsin.</p>'}
      </div>`;
    body.querySelector(".da2-back").onclick = () => { donna.briefed = false; loadDonnaBrief(); };
    body.querySelectorAll(".donna-auto").forEach((row) => {
      const id = row.dataset.id;
      row.querySelector(".da2-toggle").onclick = async () => {
        const paused = row.classList.contains("paused");
        await api(`/api/automations/${id}/status`, { method: "POST", body: JSON.stringify({ active: paused }) });
        loadAutomationsList();
      };
      row.querySelector(".da2-del").onclick = async () => {
        await api(`/api/automations/${id}`, { method: "DELETE" });
        loadAutomationsList();
      };
    });
  } catch (e) {
    body.innerHTML = `<p class="auth-error donna-err">${esc(e.message)}</p>`;
  }
}

async function openMailFromDonna(id) {
  donnaClose();
  document.querySelector('.rail-btn[data-view="inbox"]').click();
  try {
    await selectEmail(id);
  } catch { toast("Mail açılamadı", true); }
}

async function askDonna() {
  const input = $("#donna-input");
  const q = input.value.trim();
  if (!q || donna.loading) return;
  input.value = "";
  donna.loading = true;
  $("#donna-send").disabled = true;
  setDonnaChips([]);

  donnaAppend(`<div class="donna-msg me">${esc(q)}</div>`);
  const thinkingId = `dt${Date.now()}`;
  donnaAppend(`<div class="donna-msg her thinking" id="${thinkingId}"><span></span><span></span><span></span></div>`);

  try {
    const r = await api("/api/donna/ask", {
      method: "POST",
      body: JSON.stringify({ question: q, history: donna.history.slice(-6) }),
    });
    donna.history.push({ role: "user", content: q });
    donna.history.push({ role: "assistant", content: r.answer || "" });
    const srcs = (r.sources || []).map((s) =>
      `<button class="donna-src" data-mail="${s.id}">✉️ ${esc(s.sender)} · ${esc(s.subject)}</button>`).join("");
    const el = document.getElementById(thinkingId);
    el.classList.remove("thinking");
    el.innerHTML = esc(r.answer || "—").replace(/\n/g, "<br>") +
      (srcs ? `<div class="donna-srcs">${srcs}</div>` : "");
    el.querySelectorAll(".donna-src").forEach((b) => {
      b.onclick = () => openMailFromDonna(parseInt(b.dataset.mail, 10));
    });
    if (r.action && r.action.type && r.action.type !== "yok") renderDonnaAction(r.action);
    setDonnaChips(r.follow_ups || []);
    $("#donna-body").scrollTop = $("#donna-body").scrollHeight;
  } catch (e) {
    const el = document.getElementById(thinkingId);
    el.classList.remove("thinking");
    el.classList.add("err");
    el.textContent = e.message;
  } finally {
    donna.loading = false;
    $("#donna-send").disabled = false;
    input.focus();
  }
}

// --- Donna'nın hazırladığı işlem: onay kartı ---

const ACTION_META = {
  mail_yanitla:      ["✉️", "Yanıt gönder", "Gönder"],
  etkinlik_olustur:  ["📅", "Etkinlik oluştur", "Oluştur"],
  etkinlik_guncelle: ["✏️", "Etkinliği güncelle", "Güncelle"],
  etkinlik_sil:      ["🗑️", "Etkinliği sil", "Sil"],
  belge_sil:         ["🗑️", "Belgeyi sil", "Sil"],
  belge_yukle:       ["📎", "Belge yükle", "Yükleme ekranını aç"],
  otomasyon_olustur: ["🔔", "Otomasyon oluştur", "Oluştur"],
};

function renderDonnaAction(a) {
  const [icon, heading, cta] = ACTION_META[a.type] || ["⚙️", "İşlem", "Uygula"];
  const danger = a.type === "etkinlik_sil" || a.type === "belge_sil";
  const id = `da${Date.now()}`;

  let fields = "";
  if (a.type === "mail_yanitla") {
    fields = `
      <div class="da-line">Kime: <b>${esc(a.mail_to || "—")}</b> · ${esc(a.mail_subject || "")}</div>
      <textarea class="da-input da-text" rows="6" data-f="reply_text">${esc(a.reply_text || "")}</textarea>`;
  } else if (a.type === "etkinlik_olustur" || a.type === "etkinlik_guncelle") {
    fields = `
      <input class="da-input" data-f="title" value="${esc(a.title || a.event_title || "")}" placeholder="Başlık">
      <div class="da-row">
        <input class="da-input" data-f="date" type="date" value="${esc(a.date || "")}">
        <input class="da-input" data-f="time" type="time" value="${esc(a.time || "")}">
        <input class="da-input da-dur" data-f="duration_minutes" type="number" min="15" step="15"
               value="${a.duration_minutes || 60}" data-def="60" title="Süre (dk)">
      </div>
      <input class="da-input" data-f="location" value="${esc(a.location || "")}" placeholder="Yer (isteğe bağlı)">`;
  } else if (a.type === "etkinlik_sil") {
    fields = `<div class="da-line"><b>${esc(a.event_title || "")}</b> · ${esc(a.event_when || "")}</div>`;
  } else if (a.type === "belge_sil") {
    fields = `<div class="da-line"><code>${esc(a.path || "")}</code></div>`;
  } else if (a.type === "otomasyon_olustur") {
    fields = `
      <input class="da-input" data-f="automation_sender" value="${esc(a.automation_sender || "")}" placeholder="Gönderen adı/e-postası">
      <div class="da-row">
        <input class="da-input da-dur" data-f="automation_interval_value" type="number" min="1" step="1"
               value="${a.automation_interval_value || 1}" data-def="1" title="Süre">
        <select class="da-input" data-f="automation_interval_unit">
          <option value="gun" ${a.automation_interval_unit === "gun" ? "selected" : ""}>gün</option>
          <option value="saat" ${a.automation_interval_unit === "saat" ? "selected" : ""}>saat</option>
        </select>
      </div>
      <div class="da-line">🔔 Eylem: Bildirim gönder</div>
      ${a.automation_note ? `<div class="da-line da-muted">${esc(a.automation_note)}</div>` : ""}`;
  }

  donnaAppend(`
    <div class="donna-action${danger ? " danger" : ""}" id="${id}">
      <div class="da-head"><span>${icon}</span><b>${esc(heading)}</b></div>
      ${a.summary ? `<div class="da-sum">${esc(a.summary)}</div>` : ""}
      ${fields}
      <div class="da-btns">
        <button class="pill da-cancel">Vazgeç</button>
        <button class="pill accent da-ok${danger ? " danger" : ""}">${esc(cta)}</button>
      </div>
      <p class="da-err"></p>
    </div>`);

  const card = document.getElementById(id);
  card.querySelector(".da-cancel").onclick = () => {
    card.classList.add("done");
    card.innerHTML = '<div class="da-done">Vazgeçildi</div>';
  };
  card.querySelector(".da-ok").onclick = async () => {
    const payload = { ...a };
    card.querySelectorAll("[data-f]").forEach((el) => {
      payload[el.dataset.f] = el.type === "number"
        ? parseInt(el.value, 10) || parseInt(el.dataset.def || "0", 10)
        : el.value;
    });
    if (a.type === "belge_yukle") {
      donnaClose();
      document.querySelector('.rail-btn[data-view="dataroom"]').click();
      setTimeout(() => { const f = $("#dr-upload") || $("#upload-input"); if (f) f.click(); }, 300);
      return;
    }
    const btn = card.querySelector(".da-ok");
    btn.disabled = true; btn.textContent = "Uygulanıyor…";
    try {
      const res = await api("/api/donna/act", { method: "POST", body: JSON.stringify(payload) });
      card.classList.add("done");
      card.innerHTML = `<div class="da-done ok">✓ ${esc(res.message || "Yapıldı")}</div>`;
      toast(res.message || "İşlem tamamlandı");
      if (payload.type.startsWith("etkinlik")) { if (typeof loadCalendar === "function") loadCalendar(); }
      if (payload.type === "mail_yanitla" && typeof loadEmails === "function") loadEmails();
      if (payload.type === "belge_sil" && typeof loadDataroom === "function") loadDataroom();
      donna.briefed = false;   // brifing artık eski
    } catch (e) {
      card.querySelector(".da-err").textContent = e.message;
      btn.disabled = false; btn.textContent = cta;
    }
  };
}

$("#donna-send").onclick = askDonna;
$("#donna-input").onkeydown = (e) => { if (e.key === "Enter") askDonna(); };
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && donna.open) donnaClose();
  // "d" ile aç/kapat — yazı yazarken devreye girmesin
  if (e.key === "d" && !e.metaKey && !e.ctrlKey && !e.altKey) {
    const t = e.target.tagName;
    if (t !== "INPUT" && t !== "TEXTAREA" && !e.target.isContentEditable) {
      e.preventDefault();
      donna.open ? donnaClose() : donnaOpen();
    }
  }
});

// ---- Yapay zekâ sağlayıcısı ----

const aiOverlay = $("#ai-overlay");
function closeAi() { aiOverlay.hidden = true; }
$("#ai-close").onclick = closeAi;
aiOverlay.addEventListener("click", (e) => { if (e.target === aiOverlay) closeAi(); });

async function refreshAiMenuTag() {
  try {
    const r = await api("/api/ai/providers");
    const tag = $("#ai-state");
    if (!tag) return;
    const act = r.providers.find((p) => p.active);
    tag.textContent = r.selected === "auto"
      ? (act ? `Oto · ${act.label.split(" ")[0]}` : "Oto")
      : (act ? act.label.split(" ")[0] : r.selected);
    tag.classList.toggle("on", !!act);
  } catch { /* yoksay */ }
}

async function openAiSettings() {
  $("#user-menu").hidden = true;
  aiOverlay.hidden = false;
  $("#ai-body").innerHTML = '<p class="modal-muted">Yükleniyor…</p>';
  try {
    renderAiSettings(await api("/api/ai/providers"));
  } catch (e) {
    $("#ai-body").innerHTML = `<p class="auth-error">${esc(e.message)}</p>`;
  }
}

function renderAiSettings(r) {
  const rows = r.providers.map((p) => {
    const sel = r.selected === p.name;
    const stats = [];
    if (p.avg_ms) stats.push(`${(p.avg_ms / 1000).toFixed(1)} sn`);
    if (p.ok) stats.push(`${p.ok} başarılı`);
    if (p.fail) stats.push(`${p.fail} hata`);
    if (p.cooldown) stats.push(`${p.cooldown} sn beklemede`);
    return `<div class="ai-row${p.configured ? "" : " off"}${sel ? " sel" : ""}" data-p="${p.name}">
      <label class="ai-pick">
        <input type="radio" name="aiprov" value="${p.name}" ${sel ? "checked" : ""} ${p.configured ? "" : "disabled"}>
        <span class="ai-name">${esc(p.label)}${p.active ? '<span class="ai-live">kullanımda</span>' : ""}</span>
      </label>
      <div class="ai-meta">
        <code>${esc(p.model || "—")}</code>
        ${p.configured ? `<span class="ai-stats">${stats.join(" · ") || "henüz kullanılmadı"}</span>`
                       : '<span class="ai-stats warn">API anahtarı yok (.env)</span>'}
        ${p.last_error ? `<span class="ai-err" title="${esc(p.last_error)}">son hata: ${esc(p.last_error.slice(0, 60))}</span>` : ""}
      </div>
      <button class="pill mini ai-test" data-t="${p.name}" ${p.configured ? "" : "disabled"}>Test Et</button>
    </div>`;
  }).join("");

  $("#ai-body").innerHTML = `
    <div class="ai-list">
      <div class="ai-row auto${r.selected === "auto" ? " sel" : ""}">
        <label class="ai-pick">
          <input type="radio" name="aiprov" value="auto" ${r.selected === "auto" ? "checked" : ""}>
          <span class="ai-name">⚡ Otomatik (önerilen)</span>
        </label>
        <div class="ai-meta"><span class="ai-stats">En hızlı ve çalışan sağlayıcı seçilir; hata olursa diğerine geçilir</span></div>
      </div>
      ${rows}
    </div>
    <p class="auth-error" id="ai-err"></p>`;

  $("#ai-body").querySelectorAll('input[name="aiprov"]').forEach((el) => {
    el.onchange = async () => {
      try {
        await api("/api/ai/provider", { method: "POST", body: JSON.stringify({ provider: el.value }) });
        toast(el.value === "auto" ? "Otomatik seçim açıldı" : "Sağlayıcı değiştirildi ✓");
        refreshAiMenuTag();
        renderAiSettings(await api("/api/ai/providers"));
      } catch (e) { $("#ai-err").textContent = e.message; }
    };
  });

  $("#ai-body").querySelectorAll(".ai-test").forEach((btn) => {
    btn.onclick = async () => {
      const name = btn.dataset.t;
      btn.disabled = true; btn.textContent = "Test…";
      try {
        const res = await api("/api/ai/test", { method: "POST", body: JSON.stringify({ provider: name }) });
        if (res.ok) toast(`${name}: çalışıyor ✓ (${(res.ms / 1000).toFixed(1)} sn)`);
        else toast(`${name}: ${res.error}`, true);
      } catch (e) {
        toast(e.message, true);
      } finally {
        btn.disabled = false; btn.textContent = "Test Et";
        renderAiSettings(await api("/api/ai/providers"));
        refreshAiMenuTag();
      }
    };
  });
}

$("#ai-btn").onclick = openAiSettings;

// ---- Giriş kayıtları (güvenlik günlüğü) ----

const logOverlay = $("#log-overlay");
function closeLog() { logOverlay.hidden = true; }
$("#log-close").onclick = closeLog;
logOverlay.addEventListener("click", (e) => { if (e.target === logOverlay) closeLog(); });

const EVENT_LABELS = {
  login_success: ["Başarılı giriş", "ok"],
  login_fail: ["Hatalı parola", "bad"],
  twofa_fail: ["Hatalı 2FA kodu", "bad"],
  lockout: ["Kilit — çok deneme", "warn"],
  setup: ["Parola kuruldu", "ok"],
  logout: ["Çıkış", "muted"],
  "2fa_enabled": ["2FA açıldı", "ok"],
  "2fa_disabled": ["2FA kapatıldı", "warn"],
};
function fmtLogTs(ts) {
  try {
    return new Date(ts.replace(" ", "T") + "Z")
      .toLocaleString("tr-TR", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  } catch { return ts; }
}
async function openSecurityLog() {
  $("#user-menu").hidden = true;
  logOverlay.hidden = false;
  const body = $("#log-body");
  body.innerHTML = '<p class="modal-muted">Yükleniyor…</p>';
  try {
    const r = await api("/api/security/log");
    const rows = r.entries || [];
    if (!rows.length) { body.innerHTML = '<p class="modal-muted">Henüz kayıt yok.</p>'; return; }
    body.innerHTML = `<div class="log-list">${rows.map((e) => {
      const [label, cls] = EVENT_LABELS[e.event] || [e.event, "muted"];
      return `<div class="log-row">
        <span class="log-dot ${cls}"></span>
        <span class="log-ev">${esc(label)}</span>
        <span class="log-ip" title="${esc(e.user_agent || "")}">${esc(e.ip || "?")}</span>
        <span class="log-ts">${esc(fmtLogTs(e.ts))}</span>
      </div>`;
    }).join("")}</div>`;
  } catch (e) {
    body.innerHTML = `<p class="auth-error">${esc(e.message)}</p>`;
  }
}
$("#log-btn").onclick = openSecurityLog;

// ---- Kullanıcı menüsü / çıkış ----

(function setupUserMenu() {
  const avatar = $("#me-avatar");
  const menu = $("#user-menu");
  if (!avatar || !menu) return;
  avatar.onclick = (e) => {
    e.stopPropagation();
    menu.hidden = !menu.hidden;
    if (!menu.hidden) { refreshTwofaMenuTag(); refreshAiMenuTag(); }
  };
  menu.onclick = (e) => e.stopPropagation();
  document.addEventListener("click", () => { menu.hidden = true; });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") menu.hidden = true; });
  $("#logout-btn").onclick = async () => {
    try { await api("/api/auth/logout", { method: "POST" }); } catch { /* yoksay */ }
    window.location.href = "/";   // landing sayfasına dön
  };
})();

// ---- Başlatma ----

async function bootApp() {
  try {
    const EXPECTED_API_VERSION = 17;
    const [status, accounts, cals] = await Promise.all([
      api("/api/status"), api("/api/accounts"), api("/api/calendars"),
    ]);
    state.accounts = accounts.accounts;
    state.calendars = cals.calendars;
    if (status.api_version !== EXPECTED_API_VERSION) {
      toast(RESTART_MSG, true);
    }
    if (!status.ai_configured) {
      toast("Yapay zekâ API anahtarı ayarlanmadı — .env dosyasını düzenleyin", true);
    } else if (!status.accounts) {
      toast("Başlamak için Hesaplar sekmesinden bir mail hesabı ekleyin");
      document.querySelector('[data-view="accounts"]').click();
    }
  } catch { /* yoksay */ }
  loadEmails().catch((e) => toast(e.message, true));
  refreshNotifications();
}

(async function init() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
  let st = { setup: true, authed: true };
  try { st = await api("/api/auth/status"); } catch { /* sunucu eski olabilir */ }
  if (!st.setup) { showAuthOverlay("setup"); return; }
  if (!st.authed) { showAuthOverlay("login"); return; }
  bootApp();
})();
