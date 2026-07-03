let state = {
  emails: [],
  counts: {},
  categories: [],
  selectedId: null,
  activeCategory: "",
};

const $ = (sel) => document.querySelector(sel);

function toast(msg, isError = false) {
  const el = $("#toast");
  el.textContent = msg;
  el.className = "show" + (isError ? " error" : "");
  setTimeout(() => (el.className = ""), 3500);
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
    return new Date(iso).toLocaleString("tr-TR", {
      day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1048576).toFixed(1) + " MB";
}

// ---- Gelen kutusu ----

async function loadEmails() {
  const params = state.activeCategory ? `?category=${encodeURIComponent(state.activeCategory)}` : "";
  const data = await api(`/api/emails${params}`);
  state.emails = data.emails;
  state.counts = data.counts;
  state.categories = data.categories;
  renderSidebar();
  renderList();
}

function renderSidebar() {
  const total = Object.values(state.counts).reduce((a, b) => a + b, 0);
  $("#count-all").textContent = total || "";
  const holder = $("#category-list");
  holder.innerHTML = state.categories
    .map((cat) => {
      const n = state.counts[cat] || 0;
      const active = state.activeCategory === cat ? " active" : "";
      return `<button class="cat-btn${active}" data-cat="${esc(cat)}">${esc(cat)} <span class="count">${n || ""}</span></button>`;
    })
    .join("");
  document.querySelectorAll(".cat-btn").forEach((btn) => {
    btn.onclick = () => {
      state.activeCategory = btn.dataset.cat;
      document.querySelectorAll(".cat-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      loadEmails();
    };
  });
}

function renderList() {
  const list = $("#email-list");
  if (!state.emails.length) {
    list.innerHTML = `<div class="placeholder">Mail yok. "Mailleri Getir"e tıklayın.</div>`;
    return;
  }
  list.innerHTML = state.emails
    .map((e) => {
      const active = e.id === state.selectedId ? " active" : "";
      const replied = e.status === "replied" ? `<span class="badge replied">✓ yanıtlandı</span>` : "";
      const att = e.attachments.length ? `<span class="badge">📎 ${e.attachments.length}</span>` : "";
      return `
      <div class="email-item${active}" data-id="${e.id}">
        <div class="from"><span>${esc(e.sender_name || e.sender_email)}</span>
          <span class="count">${formatDate(e.date)}</span></div>
        <div class="subject">${esc(e.subject)}</div>
        <div class="summary">${esc(e.summary || "")}</div>
        <div class="meta">
          <span class="badge cat">${esc(e.category || "")}</span>
          <span class="badge p-${esc(e.priority || "orta")}">${esc(e.priority || "")}</span>
          ${att}${replied}
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
    ? `<div class="card"><h3>Ekler (dataroom'a kaydedildi)</h3><div class="attachment-list">
        ${e.attachments.map((a) => `<a href="/api/dataroom/download?path=${encodeURIComponent(a.path)}">📎 ${esc(a.filename)} (${formatSize(a.size)})</a>`).join("")}
       </div></div>`
    : "";

  const replySection = `
    <div class="card">
      <h3>Yanıt Taslağı ${e.status === "replied" ? "— ✓ gönderildi" : "(onayınızla gönderilecek)"}</h3>
      <textarea id="reply-text" placeholder="Yanıt taslağı...">${esc(e.suggested_reply || "")}</textarea>
      <div class="reply-actions">
        <button class="success" id="send-btn" ${e.status === "replied" ? "disabled" : ""}>✓ Onayla ve Gönder</button>
        <input id="regen-instruction" placeholder="İsteğe bağlı talimat (ör: daha resmi yaz, teklifi reddet...)">
        <button class="secondary" id="regen-btn">↻ Yeniden Öner</button>
        <button class="secondary" id="archive-btn">Arşivle</button>
      </div>
    </div>`;

  $("#email-detail").innerHTML = `
    <div class="detail-subject">${esc(e.subject)}</div>
    <div class="detail-meta">
      ${esc(e.sender_name || "")} &lt;${esc(e.sender_email)}&gt; · ${formatDate(e.date)}
      · <span class="badge cat">${esc(e.category || "")}</span>
      <span class="badge p-${esc(e.priority || "orta")}">${esc(e.priority || "")} öncelik</span>
    </div>
    <div class="card summary-card"><h3>Özet</h3><p>${esc(e.summary || "")}</p></div>
    ${attachments}
    ${replySection}
    <div class="card"><h3>Mail İçeriği</h3><div class="body-text">${esc(e.body_text || "(içerik yok)")}</div></div>
  `;

  $("#send-btn").onclick = async () => {
    const text = $("#reply-text").value.trim();
    if (!text) return toast("Yanıt metni boş", true);
    if (!confirm(`${e.sender_email} adresine bu yanıt gönderilsin mi?`)) return;
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

// ---- Sync ----

$("#sync-btn").onclick = async () => {
  const btn = $("#sync-btn");
  btn.disabled = true;
  btn.textContent = "Getiriliyor & tasnif ediliyor...";
  try {
    const data = await api("/api/sync", { method: "POST" });
    toast(`${data.new_emails} yeni mail tasnif edildi (${data.checked} kontrol edildi)`);
    if (data.errors.length) console.warn("Tasnif hataları:", data.errors);
    await loadEmails();
  } catch (err) {
    toast(err.message, true);
  } finally {
    btn.disabled = false;
    btn.textContent = "Mailleri Getir";
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

// ---- Sekmeler ----

document.querySelectorAll(".tab").forEach((tab) => {
  tab.onclick = () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    const view = tab.dataset.view;
    $("#view-inbox").style.display = view === "inbox" ? "flex" : "none";
    $("#view-dataroom").style.display = view === "dataroom" ? "block" : "none";
    if (view === "dataroom") loadDataroom();
  };
});

// ---- Başlangıç ----

(async function init() {
  try {
    const status = await api("/api/status");
    if (!status.email_configured || !status.ai_configured) {
      const missing = [];
      if (!status.email_configured) missing.push("EMAIL_ADDRESS / EMAIL_PASSWORD");
      if (!status.ai_configured) missing.push("ANTHROPIC_API_KEY");
      toast(`Eksik ayar: ${missing.join(", ")} — .env dosyasını düzenleyin`, true);
    }
    if (status.email_address) $("#account-info").textContent = status.email_address;
  } catch { /* yoksay */ }
  loadEmails().catch((e) => toast(e.message, true));
})();
