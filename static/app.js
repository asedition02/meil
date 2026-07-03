let state = {
  emails: [],
  counts: {},
  categories: [],
  accounts: [],
  selectedId: null,
  activeCategory: "",
  activeAccount: "",
  search: "",
};

const $ = (sel) => document.querySelector(sel);

const AVATAR_COLORS = ["#6264a7", "#c4314b", "#237b4b", "#835c00", "#0078d4", "#8764b8", "#ca5010"];

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
    const sameDay = d.toDateString() === now.toDateString();
    if (sameDay) return d.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
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

// ---- Görünüm geçişi ----

document.querySelectorAll(".rail-btn").forEach((btn) => {
  btn.onclick = () => {
    document.querySelectorAll(".rail-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const view = btn.dataset.view;
    ["inbox", "dataroom", "accounts"].forEach((v) => {
      $(`#view-${v}`).style.display = v === view ? "flex" : "none";
    });
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
  const catSel = $("#category-filter");
  const total = Object.values(state.counts).reduce((a, b) => a + b, 0);
  catSel.innerHTML =
    `<option value="">Tüm kategoriler (${total})</option>` +
    state.categories
      .map((c) => `<option value="${esc(c)}" ${state.activeCategory === c ? "selected" : ""}>${esc(c)} (${state.counts[c] || 0})</option>`)
      .join("");

  const accSel = $("#account-filter");
  accSel.innerHTML =
    `<option value="">Tüm hesaplar</option>` +
    state.accounts
      .map((a) => `<option value="${a.id}" ${String(state.activeAccount) === String(a.id) ? "selected" : ""}>${esc(a.display_name || a.email)}</option>`)
      .join("");
}

$("#category-filter").onchange = (e) => { state.activeCategory = e.target.value; loadEmails(); };
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
      ${state.emails.length ? "Aramayla eşleşen mail yok." : 'Mail yok. Sağ üstten "⟳ Eşitle"ye tıklayın.'}
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
    ? `<div class="card"><h3>Ekler — dataroom'a kaydedildi</h3><div class="attachment-list">
        ${e.attachments.map((a) => `<a href="/api/dataroom/download?path=${encodeURIComponent(a.path)}">📎 ${esc(a.filename)} <span style="color:var(--t-muted)">(${formatSize(a.size)})</span></a>`).join("")}
       </div></div>`
    : "";

  const acctInfo = e.account_email
    ? `<span class="badge acct">${esc(e.account_name || e.account_email)} hesabına geldi</span>`
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
    ${attachments}
    <div class="card">
      <h3>Yanıt Taslağı ${e.status === "replied" ? "— ✓ gönderildi" : "(onayınızla gönderilir)"}</h3>
      <textarea id="reply-text" placeholder="Yanıt taslağı...">${esc(e.suggested_reply || "")}</textarea>
      <div class="reply-actions">
        <button class="primary" id="send-btn" ${e.status === "replied" ? "disabled" : ""}>➤ Onayla ve Gönder</button>
        <input id="regen-instruction" placeholder="İsteğe bağlı talimat (ör: daha resmi yaz, toplantı öner...)">
        <button class="secondary" id="regen-btn">↻ Yeniden Öner</button>
        <button class="secondary" id="archive-btn">Arşivle</button>
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
}

// ---- Eşitleme ----

$("#sync-btn").onclick = async () => {
  const btn = $("#sync-btn");
  btn.disabled = true;
  btn.textContent = "⟳ Eşitleniyor...";
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
    btn.textContent = "⟳ Eşitle";
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
          <button class="danger" data-del="${a.id}">Kaldır</button>
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

// ---- Başlangıç ----

(async function init() {
  try {
    const [status, accounts] = await Promise.all([api("/api/status"), api("/api/accounts")]);
    state.accounts = accounts.accounts;
    if (!status.ai_configured) {
      toast("ANTHROPIC_API_KEY ayarlanmadı — .env dosyasını düzenleyin", true);
    } else if (!status.accounts) {
      toast("Başlamak için Hesaplar sekmesinden bir mail hesabı ekleyin");
      document.querySelector('[data-view="accounts"]').click();
    }
  } catch { /* yoksay */ }
  loadEmails().catch((e) => toast(e.message, true));
})();
