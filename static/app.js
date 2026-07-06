let state = {
  emails: [],
  counts: {},
  categories: [],
  accounts: [],
  calendars: [],
  selectedId: null,
  activeCategory: "",
  activeAccount: "",
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

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
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
      $(`#view-${v}`).style.display = v === view ? "flex" : "none";
    });
    if (view === "calendar") loadCalendar();
    if (view === "dataroom") loadDataroom();
    if (view === "accounts") loadAccounts();
  };
});

// ---- Posta ----

async function loadEmails() {
  const params = new URLSearchParams();
  if (state.activeCategory) params.set("category", state.activeCategory);
  if (state.activeAccount) params.set("account_id", state.activeAccount);
  const data = await api(`/api/emails?${params}`);
  state.emails = data.emails;
  state.counts = data.counts;
  state.categories = data.categories;
  renderFilters();
  renderList();
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
      return `
      <div class="email-item${active}" data-id="${e.id}">
        ${avatarHtml(e.sender_name, e.sender_email)}
        <div class="item-body">
          <div class="row1">
            <span class="from">${esc(e.sender_name || e.sender_email)}</span>
            <span class="time">${formatDate(e.date)}</span>
          </div>
          <div class="subject">${esc(e.subject)}</div>
          <div class="summary">${esc(e.summary || "")}</div>
          <div class="meta">
            <span class="badge cat">${esc(e.category || "")}</span>
            <span class="badge p-${esc(e.priority || "orta")}">${esc(e.priority || "")}</span>
            ${att}${acct}${replied}
          </div>
        </div>
      </div>`;
    })
    .join("");
  document.querySelectorAll(".email-item").forEach((item) => {
    item.onclick = () => selectEmail(parseInt(item.dataset.id));
  });
}

async function selectEmail(id) {
  state.selectedId = id;
  renderList();
  const e = await api(`/api/emails/${id}`);
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
      <div>
        <div class="detail-subject">${esc(e.subject)}</div>
        <div class="detail-meta">
          <span>${esc(e.sender_name || "")} &lt;${esc(e.sender_email)}&gt;</span>
          <span>·</span><span>${formatDateFull(e.date)}</span>
          <span class="badge cat">${esc(e.category || "")}</span>
          <span class="badge p-${esc(e.priority || "orta")}">${esc(e.priority || "")} öncelik</span>
          ${acctInfo}
        </div>
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

// ---- Dataroom ----

async function loadDataroom() {
  const data = await api("/api/dataroom");
  const holder = $("#dataroom-list");
  if (!data.files.length) {
    holder.innerHTML = `<div class="placeholder">Dataroom boş. Ekli mailler geldikçe dosyalar burada birikecek.</div>`;
    return;
  }
  holder.innerHTML = `
    <table class="dataroom">
      <thead><tr><th>Dosya</th><th>Klasör</th><th>Boyut</th><th></th></tr></thead>
      <tbody>
        ${data.files.map((f) => `
          <tr>
            <td>📎 ${esc(f.filename)}</td>
            <td>${esc(f.folder)}</td>
            <td>${formatSize(f.size)}</td>
            <td><a href="/api/dataroom/download?path=${encodeURIComponent(f.path)}">İndir</a></td>
          </tr>`).join("")}
      </tbody>
    </table>`;
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
    const [status, accounts, cals] = await Promise.all([
      api("/api/status"), api("/api/accounts"), api("/api/calendars"),
    ]);
    state.accounts = accounts.accounts;
    state.calendars = cals.calendars;
    if (!status.ai_configured) {
      toast("ANTHROPIC_API_KEY ayarlanmadı — .env dosyasını düzenleyin", true);
    } else if (!status.accounts) {
      toast("Başlamak için Hesaplar sekmesinden bir mail hesabı ekleyin");
      document.querySelector('[data-view="accounts"]').click();
    }
  } catch { /* yoksay */ }
  loadEmails().catch((e) => toast(e.message, true));
})();
