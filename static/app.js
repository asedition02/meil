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

function formatSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1048576).toFixed(1) + " MB";
}

// ---- Tema ----

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  $("#theme-toggle").textContent = theme === "dark" ? "☀️" : "🌙";
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
    ["inbox", "calendar", "dataroom", "accounts"].forEach((v) => {
      const elem = $(`#view-${v}`);
      if (!elem) { console.error(`View element not found: #view-${v}`); return; }
      elem.style.display = v === view ? "flex" : "none";
    });
    if (view === "calendar") loadCalendar();
    if (view === "dataroom") loadDataroom();
    if (view === "accounts") loadAccounts();
  };
});

// ---- Posta ----

const VIEW_LABELS = {
  inbox: ["📥", "Gelen"], starred: ["⭐", "Yıldızlı"], awaiting: ["⏳", "Bekleyen"],
  snoozed: ["😴", "Ertelenen"], archived: ["🗂", "Arşiv"],
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
      const att = e.attachments.length ? `<span class="badge">📎 ${e.attachments.length}</span>` : "";
      const acct = showAcct && e.account_email ? `<span class="badge acct">${esc(e.account_name || e.account_email)}</span>` : "";
      const unread = !e.is_read ? " unread" : "";
      const snoozed = state.activeView === "snoozed" && e.snooze_until
        ? `<span class="badge">😴 ${formatDateFull(e.snooze_until)}</span>` : "";
      return `
      <div class="email-item${active}${unread}" data-id="${e.id}">
        ${!e.is_read ? '<span class="unread-dot"></span>' : ""}
        ${avatarHtml(e.sender_name, e.sender_email)}
        <div class="item-body">
          <div class="row1">
            <span class="from">${esc(e.sender_name || e.sender_email)}</span>
            <span style="display:flex;align-items:center">
              <span class="time">${formatDate(e.date)}</span>
              <button class="star-btn${e.starred ? " on" : ""}" data-star="${e.id}" title="Yıldızla (s)">⭐</button>
            </span>
          </div>
          <div class="subject">${esc(e.subject)}</div>
          <div class="summary">${esc(e.summary || "")}</div>
          <div class="meta">
            <span class="badge cat">${esc(e.category || "")}</span>
            <span class="badge p-${esc(e.priority || "orta")}">${esc(e.priority || "")}</span>
            ${att}${acct}${replied}${snoozed}
          </div>
        </div>
      </div>`;
    })
    .join("");
  document.querySelectorAll(".email-item").forEach((item) => {
    item.onclick = (ev) => {
      if (ev.target.closest(".star-btn")) return;
      selectEmail(parseInt(item.dataset.id));
    };
  });
  document.querySelectorAll(".star-btn[data-star]").forEach((btn) => {
    btn.onclick = () => toggleStar(parseInt(btn.dataset.star));
  });
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
  const e = await api(`/api/emails/${id}`);
  const local = state.emails.find((x) => x.id === id);
  if (local && !local.is_read) {
    local.is_read = true;
    state.views.unread = Math.max(0, (state.views.unread || 1) - 1);
    renderUnreadBadge();
  }
  renderList();
  renderDetail(e);
}

function renderDetail(e) {
  const attachments = e.attachments.length
    ? `<div class="card"><h3>📎 Ekler — dataroom'a kaydedildi</h3><div class="attachment-list">
        ${e.attachments.map((a) => `<a href="/api/dataroom/download?path=${encodeURIComponent(a.path)}">${esc(a.filename)} <span class="size">${formatSize(a.size)}</span></a>`).join("")}
       </div></div>`
    : "";

  const acctInfo = e.account_email
    ? `<span class="badge acct">${esc(e.account_name || e.account_email)}</span>`
    : "";

  const writableCals = state.calendars.filter((c) => c.type === "icloud");
  const eventCard = e.event && e.event.exists && e.event.date
    ? `<div class="card event-card">
        <h3>📅 Tespit Edilen Etkinlik</h3>
        <div class="ev-line"><strong>${esc(e.event.title || e.subject)}</strong></div>
        <div class="ev-line">${esc(e.event.date)}${e.event.time ? " · " + esc(e.event.time) : " · tüm gün"}${e.event.location ? " · 📍 " + esc(e.event.location) : ""}</div>
        <div class="ev-actions">
          <select id="event-cal-select">
            <option value="">Meil (yerel takvim)</option>
            ${writableCals.map((c) => `<option value="${c.id}">${esc(c.name)} (iCloud)</option>`).join("")}
          </select>
          <button class="pill accent" id="add-event-btn">＋ Takvime Ekle</button>
        </div>
      </div>`
    : "";

  $("#detail-panel").innerHTML = `
    <div class="detail-header">
      ${avatarHtml(e.sender_name, e.sender_email, "large")}
      <div style="flex:1; min-width:0">
        <div class="detail-subject">${esc(e.subject)}</div>
        <div class="detail-meta">
          <span>${esc(e.sender_name || "")} &lt;${esc(e.sender_email)}&gt;</span>
          <span>·</span><span>${formatDateFull(e.date)}</span>
          <span class="badge cat">${esc(e.category || "")}</span>
          <span class="badge p-${esc(e.priority || "orta")}">${esc(e.priority || "")} öncelik</span>
          ${acctInfo}
        </div>
      </div>
      <div class="detail-toolbar">
        <button class="icon-btn" id="d-star" title="Yıldızla">${e.starred ? "⭐" : "☆"}</button>
        <button class="icon-btn" id="d-snooze" title="Ertele">😴</button>
        <button class="icon-btn" id="d-unread" title="Okunmadı işaretle">📪</button>
        <button class="icon-btn" id="d-archive" title="${e.status === "archived" ? "Gelen kutusuna taşı" : "Arşivle"}">${e.status === "archived" ? "📥" : "🗂"}</button>
      </div>
    </div>
    <div class="card summary-card"><h3>✨ Özet</h3><p>${esc(e.summary || "")}</p></div>
    ${eventCard}
    ${attachments}
    <div class="card">
      <h3>Yanıt Taslağı ${e.status === "replied" ? "— ✓ gönderildi" : "· onayınızla gönderilir"}</h3>
      <textarea id="reply-text" placeholder="Yanıt taslağı...">${esc(e.suggested_reply || "")}</textarea>
      <div class="reply-actions">
        <button class="pill accent" id="send-btn" ${e.status === "replied" ? "disabled" : ""}>➤ Onayla ve Gönder</button>
        <input id="regen-instruction" placeholder="İsteğe bağlı talimat (ör: daha resmi yaz, toplantı öner...)">
        <button class="pill ghost" id="regen-btn">↻ Yeniden Öner</button>
        <button class="pill ghost" id="archive-btn">Arşivle</button>
      </div>
    </div>
    <div class="card"><h3>Mail İçeriği</h3><div class="body-text">${esc(e.body_text || "(içerik yok)")}</div></div>
  `;

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
      btn.textContent = "↻ Yeniden Öner";
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
    $("#d-star").textContent = e.starred ? "⭐" : "☆";
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
    <h3>😴 Ertele — ${esc(e.subject)}</h3>
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
    toast(until ? "Mail ertelendi 😴" : "Erteleme kaldırıldı");
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
    <h3>✎ Yeni Mail</h3>
    <div class="form-col">
      <select id="c-account">${accountOptions}</select>
      <input id="c-to" type="email" placeholder="Alıcı" value="${esc(prefill.to || "")}">
      <input id="c-cc" placeholder="CC (isteğe bağlı, virgülle ayırın)">
      <input id="c-subject" placeholder="Konu" value="${esc(prefill.subject || "")}">
      <textarea id="c-body" style="min-height:180px" placeholder="Mesajınız...">${esc(prefill.body || "")}</textarea>
      <div class="form-row">
        <input id="c-ai" placeholder="✨ AI'ya anlatın: 'yarınki toplantıyı iptal et, kibarca'">
        <button class="pill ghost" id="c-ai-btn" style="flex:0 0 auto">✨ AI ile Yaz</button>
      </div>
    </div>
    <div class="modal-actions">
      <button class="pill ghost" onclick="closeModal()">Vazgeç</button>
      <button class="pill accent" id="c-send">➤ Gönder</button>
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
    finally { btn.disabled = false; btn.textContent = "✨ AI ile Yaz"; }
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
      btn.disabled = false; btn.textContent = "➤ Gönder";
    }
  };
}

$("#compose-btn").onclick = () => openComposeModal();

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
      toast(`📬 ${data.new_emails} yeni mail geldi`);
      loadEmails();
    }
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

let dataroomFiles = [];
let dataroomSearch = "";
let dataroomCurrentFolder = ".";  // Mevcut klasör
let dataroomSelectedFile = null;  // Seçili dosya (notlar paneli için)

async function loadDataroom() {
  const data = await api("/api/dataroom");
  dataroomFiles = data.files;
  dataroomCurrentFolder = ".";
  dataroomSelectedFile = null;
  renderDataroom();
  renderNotesPanel();
}

function getFolderContents(folder) {
  // folder'ındaki dosyaları ve alt klasörleri döner
  const contents = { folders: new Set(), files: [] };
  for (const f of dataroomFiles) {
    if (f.folder === folder) {
      contents.files.push(f);
    } else if (f.folder.startsWith(folder === "." ? "" : folder + "/")) {
      const rest = f.folder.slice((folder === "." ? 0 : folder.length + 1));
      const next = rest.split("/")[0];
      if (next) contents.folders.add(next);
    }
  }
  return { folders: Array.from(contents.folders).sort(), files: contents.files };
}

function renderDataroom() {
  console.log("renderDataroom called, dataroomSelectedFile:", dataroomSelectedFile);
  const holder = $("#dataroom-list");
  const q = dataroomSearch.toLowerCase();
  let files = dataroomFiles;
  if (q) {
    files = files.filter((f) => [f.filename, f.folder, f.note].join(" ").toLowerCase().includes(q));
  }
  
  const { folders, files: currentFiles } = getFolderContents(dataroomCurrentFolder);
  const filteredFiles = files.filter((f) => f.folder === dataroomCurrentFolder);
  
  if (!filteredFiles.length && !folders.length) {
    holder.innerHTML = `<div class="placeholder" style="margin-top:40px">
      ${dataroomFiles.length ? "Bu klasör boş." : "Dataroom boş. Ekli mailler geldikçe dosyalar birikecek — ya da kendi belgelerinizi yükleyin."}
    </div>`;
    return;
  }
  
  // Breadcrumb navigation
  let breadcrumb = '<div class="breadcrumb">';
  if (dataroomCurrentFolder !== ".") {
    breadcrumb += '<button class="breadcrumb-btn" onclick="dataroomCurrentFolder = \'.\'; dataroomSelectedFile = null; renderDataroom(); renderNotesPanel()">📁 /</button>';
    const parts = dataroomCurrentFolder.split("/");
    let path = "";
    for (let i = 0; i < parts.length; i++) {
      path = i === 0 ? parts[0] : path + "/" + parts[i];
      const p = path;
      breadcrumb += ` / <button class="breadcrumb-btn" onclick="dataroomCurrentFolder = '${p}'; dataroomSelectedFile = null; renderDataroom(); renderNotesPanel()">${esc(parts[i])}</button>`;
    }
  } else {
    breadcrumb += '<span>📁 /</span>';
  }
  breadcrumb += '</div>';
  
  holder.innerHTML = breadcrumb + `
    <table class="dataroom">
      <thead><tr><th>Dosya / Klasör</th><th>Boyut</th><th style="text-align:right">İşlemler</th></tr></thead>
      <tbody>
        ${folders.map((fld) => `
          <tr class="folder-row">
            <td>
              <button class="folder-btn" onclick="dataroomCurrentFolder = '${dataroomCurrentFolder === "." ? "" : dataroomCurrentFolder + "/"}${fld}'; dataroomSelectedFile = null; renderDataroom(); renderNotesPanel()">
                📁 ${esc(fld)}
              </button>
            </td>
            <td></td>
            <td></td>
          </tr>`).join("")}
        ${filteredFiles.map((f, i) => `
          <tr${dataroomSelectedFile === f.path ? ' class="selected-file-row"' : ''}>
            <td>
              <button class="file-name-btn" onclick="dataroomSelectedFile = '${f.path}'; renderDataroom(); renderNotesPanel()">
                📎 ${esc(f.filename)} ${f.share_token ? '<span class="shared-badge">🔗 paylaşımda</span>' : ""}
              </button>
            </td>
            <td>${formatSize(f.size)}</td>
            <td>
              <div class="file-actions">
                <a class="mini-btn" href="/api/dataroom/download?path=${encodeURIComponent(f.path)}" title="İndir">⬇ İndir</a>
                <button class="mini-btn" data-act="send" data-i="${i}" title="Mail olarak gönder">✉ Gönder</button>
                <button class="mini-btn" data-act="share" data-i="${i}" title="Paylaşım linki">🔗 Paylaş</button>
                <button class="mini-btn danger" data-act="delete" data-i="${i}" title="Sil">🗑</button>
                ${dataroomSelectedFile === f.path ? '<button class="mini-btn accent" id="quick-note-btn" title="Not ekle">📝 Not Ekle</button>' : ""}
              </div>
            </td>
          </tr>`).join("")}
      </tbody>
    </table>`;
  holder.querySelectorAll("[data-act]").forEach((btn) => {
    const file = filteredFiles[parseInt(btn.dataset.i)];
    btn.onclick = () => {
      if (btn.dataset.act === "send") openSendModal(file);
      if (btn.dataset.act === "share") openShareModal(file);
      if (btn.dataset.act === "delete") deleteDataroomFile(file);
    };
  });
  
  // Quick Note Button
  const quickNoteBtn = holder.querySelector("#quick-note-btn");
  if (quickNoteBtn) {
    quickNoteBtn.onclick = () => {
      const textarea = $("#note-content");
      if (textarea) textarea.focus();
    };
  }
}

$("#dataroom-search").oninput = (e) => { dataroomSearch = e.target.value; renderDataroom(); };

// Notlar paneli
function renderNotesPanel() {
  const notesPanel = $("#dataroom-notes");
  if (!notesPanel) return; // Panel henüz yüklenmemişse çık
  
  if (!dataroomSelectedFile) {
    notesPanel.innerHTML = '<div class="placeholder">Dosya seçin</div>';
    return;
  }
  
  const file = dataroomFiles.find((f) => f.path === dataroomSelectedFile);
  if (!file) {
    notesPanel.innerHTML = '<div class="placeholder">Dosya bulunamadı</div>';
    return;
  }
  
  notesPanel.innerHTML = `
    <div class="notes-panel">
      <h3>📝 ${esc(file.filename)}</h3>
      <div class="notes-list" id="notes-list"></div>
      <div class="add-note-form">
        <input id="note-author" placeholder="Adınız..." value="${config.USER_NAME || ""}" readonly>
        <textarea id="note-content" placeholder="Not ekleyin..."></textarea>
        <button id="add-note-btn" class="pill accent">➤ Not Ekle</button>
      </div>
    </div>`;
  
  loadFileNotes(dataroomSelectedFile);
}

async function loadFileNotes(filePath) {
  try {
    const data = await api(`/api/dataroom/notes?path=${encodeURIComponent(filePath)}`);
    const list = $("#notes-list");
    if (!list) return; // Notlar listesi henüz yüklenmemişse çık
    
    if (!data.notes.length) {
      list.innerHTML = '<div class="placeholder" style="font-size:12px">Henüz not yok</div>';
    } else {
      list.innerHTML = data.notes.map((n) => `
        <div class="note-item">
          <div class="note-header">
            <span class="note-author">👤 ${esc(n.author)}</span>
            <span class="note-time">${formatDateFull(n.created_at)}</span>
            <button class="note-delete-btn" onclick="deleteFileNote(${n.id})">✕</button>
          </div>
          <div class="note-content">${esc(n.content)}</div>
        </div>`).join("");
    }
    
    const addBtn = $("#add-note-btn");
    if (addBtn) {
      addBtn.onclick = async () => {
        const author = $("#note-author").value.trim();
        const content = $("#note-content").value.trim();
        if (!content) return toast("Not yazınız", true);
        try {
          addBtn.disabled = true;
          addBtn.textContent = "Ekleniyor...";
          await api("/api/dataroom/notes", {
            method: "POST",
            body: JSON.stringify({ path: filePath, author, content }),
          });
          toast("Not eklendi ✓");
          $("#note-content").value = "";
          await loadFileNotes(filePath);
        } catch (err) {
          toast(err.message, true);
        } finally {
          addBtn.disabled = false;
          addBtn.textContent = "➤ Not Ekle";
        }
      };
    }
  } catch (err) {
    toast(err.message, true);
  }
}

async function deleteFileNote(noteId) {
  if (!confirm("Bu notu silmek istediğinizden emin misiniz?")) return;
  try {
    await api(`/api/dataroom/notes/${noteId}`, { method: "DELETE" });
    toast("Not silindi");
    await loadFileNotes(dataroomSelectedFile);
  } catch (err) {
    toast(err.message, true);
  }
}

// Yükleme
$("#upload-btn").onclick = () => $("#upload-input").click();
$("#upload-input").onchange = async () => {
  const input = $("#upload-input");
  if (!input.files.length) return;
  const fd = new FormData();
  for (const f of input.files) fd.append("files", f);
  const btn = $("#upload-btn");
  btn.disabled = true;
  btn.textContent = "⬆ Yükleniyor...";
  try {
    const res = await fetch("/api/dataroom/upload", { method: "POST", body: fd });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || `Hata: ${res.status}`);
    toast(`${data.files.length} dosya yüklendi ✓`);
    loadDataroom();
  } catch (err) {
    toast(err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = "⬆ Dosya Yükle";
    input.value = "";
  }
};

async function deleteDataroomFile(file) {
  if (!confirm(`"${file.filename}" kalıcı olarak silinsin mi?`)) return;
  try {
    await api(`/api/dataroom/file?path=${encodeURIComponent(file.path)}`, { method: "DELETE" });
    toast("Dosya silindi");
    loadDataroom();
  } catch (err) {
    toast(err.message, true);
  }
}

function openNoteModal(file) {
  openModal(`
    <h3>📝 Not — ${esc(file.filename)}</h3>
    <div class="modal-sub">${esc(file.folder === "." ? "" : file.folder)}</div>
    <textarea id="note-text" placeholder="Bu belge hakkında notunuz...">${esc(file.note || "")}</textarea>
    <div class="modal-actions">
      <button class="pill ghost" onclick="closeModal()">Vazgeç</button>
      <button class="pill accent" id="note-save">Kaydet</button>
    </div>`);
  $("#note-save").onclick = async () => {
    try {
      await api("/api/dataroom/note", {
        method: "POST",
        body: JSON.stringify({ path: file.path, note: $("#note-text").value }),
      });
      toast("Not kaydedildi ✓");
      closeModal();
      loadDataroom();
    } catch (err) {
      toast(err.message, true);
    }
  };
}

async function openShareModal(file) {
  try {
    const data = await api("/api/dataroom/share", {
      method: "POST",
      body: JSON.stringify({ path: file.path }),
    });
    const url = window.location.origin + data.url;
    openModal(`
      <h3>🔗 Paylaşım Linki</h3>
      <div class="modal-sub">${esc(file.filename)} — bu linki bilen herkes dosyayı indirebilir.</div>
      <div class="share-url"><code id="share-url-text">${esc(url)}</code></div>
      <div class="modal-actions">
        <button class="pill danger-ghost" id="share-revoke">Linki İptal Et</button>
        <button class="pill ghost" onclick="closeModal()">Kapat</button>
        <button class="pill accent" id="share-copy">📋 Kopyala</button>
      </div>`);
    $("#share-copy").onclick = async () => {
      try {
        await navigator.clipboard.writeText(url);
        toast("Link kopyalandı ✓");
      } catch {
        toast("Kopyalanamadı — linki elle seçin", true);
      }
    };
    $("#share-revoke").onclick = async () => {
      await api(`/api/dataroom/share?path=${encodeURIComponent(file.path)}`, { method: "DELETE" });
      toast("Paylaşım linki iptal edildi");
      closeModal();
      loadDataroom();
    };
    loadDataroom();
  } catch (err) {
    toast(err.message, true);
  }
}

function openSendModal(file) {
  if (!state.accounts.length) {
    return toast("Önce Hesaplar sekmesinden bir mail hesabı ekleyin", true);
  }
  const accountOptions = state.accounts
    .map((a) => `<option value="${a.id}">${esc(a.display_name || a.email)}</option>`)
    .join("");
  openModal(`
    <h3>✉ Belgeyi Mail At</h3>
    <div class="modal-sub">Ek: ${esc(file.filename)} (${formatSize(file.size)})</div>
    <div class="form-col">
      <select id="send-account">${accountOptions}</select>
      <input id="send-to" type="email" placeholder="Alıcı adresi (ör. ad@firma.com)">
      <input id="send-subject" placeholder="Konu" value="Belge: ${esc(file.filename)}">
      <textarea id="send-message" placeholder="Mesaj (isteğe bağlı)"></textarea>
    </div>
    <div class="modal-actions">
      <button class="pill ghost" onclick="closeModal()">Vazgeç</button>
      <button class="pill accent" id="send-file-btn">➤ Gönder</button>
    </div>`);
  $("#send-file-btn").onclick = async () => {
    const to = $("#send-to").value.trim();
    if (!to) return toast("Alıcı adresi gerekli", true);
    const btn = $("#send-file-btn");
    btn.disabled = true;
    btn.textContent = "Gönderiliyor...";
    try {
      await api("/api/dataroom/send", {
        method: "POST",
        body: JSON.stringify({
          path: file.path,
          to,
          subject: $("#send-subject").value,
          message: $("#send-message").value,
          account_id: parseInt($("#send-account").value),
        }),
      });
      toast(`"${file.filename}" ${to} adresine gönderildi ✓`);
      closeModal();
    } catch (err) {
      toast(err.message, true);
      btn.disabled = false;
      btn.textContent = "➤ Gönder";
    }
  };
}

// ---- Hesaplar ----

const PROVIDER_HINTS = {
  gmail: 'Gmail için normal şifreniz çalışmaz — <a href="https://myaccount.google.com/apppasswords" target="_blank">uygulama şifresi</a> oluşturun (2 Adımlı Doğrulama açık olmalı).',
  outlook: "Microsoft 365 şirket hesabınızda IMAP erişimi ve temel kimlik doğrulama/uygulama şifresi BT yöneticiniz tarafından açılmış olmalıdır. Emin değilseniz BT ekibinize sorun.",
  yahoo: 'Yahoo için <a href="https://login.yahoo.com/account/security" target="_blank">uygulama şifresi</a> oluşturmanız gerekir.',
  yandex: "Yandex için hesap ayarlarından IMAP erişimini açın ve uygulama şifresi oluşturun.",
  custom: "Şirket mail sunucunuzun IMAP/SMTP adreslerini BT ekibinizden öğrenebilirsiniz. IMAP genellikle 993 (SSL), SMTP 465 (SSL) veya 587 (STARTTLS) portunu kullanır.",
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
            <div class="name">${esc(a.display_name || a.email)}</div>
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
  $("#custom-fields").style.display = p === "custom" ? "grid" : "none";
  $("#provider-hint").innerHTML = PROVIDER_HINTS[p] || "";
};
$("#acc-provider").onchange();

$("#acc-save").onclick = async () => {
  const btn = $("#acc-save");
  const provider = $("#acc-provider").value;
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
          <div class="ev-meta">${time} · ${esc(calName)}${ev.location ? " · 📍 " + esc(ev.location) : ""}</div>
        </div>
        ${deletable ? `<button class="ev-del" data-ev="${ev.id}" title="Sil">✕</button>` : ""}
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
      <button class="ev-del" data-cal="${c.id}" title="Kaldır">✕</button>
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
  btn.textContent = "⟳ Eşitleniyor...";
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
    btn.textContent = "⟳ Takvimleri Eşitle";
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

(async function init() {
  try {
    const EXPECTED_API_VERSION = 7;
    const [status, accounts, cals] = await Promise.all([
      api("/api/status"), api("/api/accounts"), api("/api/calendars"),
    ]);
    state.accounts = accounts.accounts;
    state.calendars = cals.calendars;
    if (status.api_version !== EXPECTED_API_VERSION) {
      toast(RESTART_MSG, true);
    }
    if (!status.ai_configured) {
      toast("ANTHROPIC_API_KEY ayarlanmadı — .env dosyasını düzenleyin", true);
    } else if (!status.accounts) {
      toast("Başlamak için Hesaplar sekmesinden bir mail hesabı ekleyin");
      document.querySelector('[data-view="accounts"]').click();
    }
  } catch { /* yoksay */ }
  loadEmails().catch((e) => toast(e.message, true));
})();
