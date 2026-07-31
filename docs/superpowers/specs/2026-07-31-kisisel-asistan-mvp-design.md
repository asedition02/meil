# Meil — Kişisel Asistan MVP Tasarımı

**Tarih:** 2026-07-31
**Durum:** Onaylandı — uygulama planı bekleniyor

## Amaç

Meil'i "mail istemcisi + AI özet" olmaktan çıkarıp gerçek bir kişisel asistana
dönüştürecek ilk MVP paketi. Beş bileşen:

1. Arka plan zamanlayıcı (altyapı)
2. Hatırlatmalar (reminders)
3. "Cevap bekliyorum" takibi (awaiting-reply)
4. Kalıcı Donna konuşmaları
5. Bugün ekranı

## Mevcut Durum Analizi

Kod incelemesinde şu boşluklar tespit edildi:

- **Arka plan işi yok.** Her şey istemci tetiklemeli: `static/app.js` içinde
  `setInterval` ile periyodik `/api/sync` çağrısı yapılıyor (satır ~1003),
  sunucu tarafında hiçbir zamanlanmış görev çalışmıyor.
- **Donna geçmişi kalıcı değil.** `donna.ask_with_tools()` (`app/donna.py`)
  `history` parametresini çağrıdan alıyor; istemci tarafında bu sadece
  `donna.history` adlı bir JS değişkeninde tutuluyor (`static/app.js` ~2753).
  Sayfa yenilenince kaybolur.
- **Gönderilen mailler hiçbir yerde saklanmıyor.** `email_client.send_message`
  ve `send_reply` (`app/email_client.py`) SMTP üzerinden gönderiyor ama IMAP
  Sent klasörü senkronize edilmiyor, `emails` tablosuna yazılmıyor. Ayrıca
  giden mailde `Message-ID` header'ı hiç set edilmiyor.
- **Konuşma zinciri (threading) altyapısı var ve yeniden kullanılabilir.**
  `emails` tablosunda `in_reply_to`, `refs`, `thread_id` sütunları ve
  `_compute_thread_id()` (`app/database.py` ~930) zaten mevcut — gelen bir
  mailin hangi giden mesaja yanıt olduğunu bu alanlardan tespit edebiliriz.
- **Tasks (görevler) modülü örnek desen olarak kullanılacak.** `app/database.py`
  sonundaki `tasks` tablosu + CRUD fonksiyonları, `app/main.py`'deki
  `/api/tasks/*` uçları ve ilişkilendirme (mail/dosya/etkinlik arama) deseni
  hatırlatmalar için birebir tekrar kullanılıyor.

## Mimari

```
app/scheduler.py    (YENİ)   asyncio arka plan döngüsü, FastAPI lifespan ile başlar/durur
app/database.py     (GENİŞLER) 4 yeni tablo + CRUD: reminders, awaiting_replies,
                                donna_conversations, donna_messages
app/donna.py        (KÜÇÜK DEĞİŞİKLİK) ask()/ask_with_tools() imzası aynı kalır;
                                        çağıran taraf (main.py) artık history'yi DB'den okur/yazar
app/email_client.py (KÜÇÜK DEĞİŞİKLİK) send_message/send_reply kendi ürettiği
                                        Message-ID'yi döndürür
app/main.py         (GENİŞLER) /api/reminders/*, /api/awaiting-replies/*,
                                /api/donna/conversations/*, /api/today
static/*            (GENİŞLER) Bugün sekmesi, Donna panelinde konuşma değiştirici,
                                compose/reply'de "cevap bekliyorum" seçeneği
```

Zamanlayıcı tek process içinde çalışır (Redis/Celery yok — tek VPS/systemd
servisine uygun, mevcut altyapıyla tutarlı). FastAPI `lifespan` context
manager'ı ile başlatılır/durdurulur:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    task = asyncio.create_task(scheduler.run_forever())
    yield
    task.cancel()

app = FastAPI(title="Meil — E-posta Asistanı", lifespan=lifespan)
```

`scheduler.run_forever()`: 60 saniyede bir "tick" atar. Her iş kendi
`try/except` bloğunda çalışır ve loglanır — biri patlarsa döngü durmaz, bir
sonraki tick'te devam eder. 15 tick'te bir (~15 dk) tüm hesapları arka planda
senkronize eder (mevcut `/api/sync` mantığının yeniden kullanımı) — böylece
tarayıcı kapalıyken de awaiting-reply çözümü ve Bugün ekranı güncel kalır.
Bu, `docs/PHASE2_SUMMARY.md`'de önerilen harici cron job önerisinin yerini
alır.

Test edilebilirlik için tick mantığı küçük, saf fonksiyonlara bölünür
(`_notify_due_reminders()`, `_resolve_awaiting_replies()`,
`_sync_all_accounts()`) — testler sonsuz döngüyü değil bu fonksiyonları
doğrudan çağırır.

## Veri Modeli

### reminders

```sql
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    remind_at TEXT NOT NULL,         -- ISO tarih-saat
    status TEXT DEFAULT 'bekliyor',  -- bekliyor | tamamlandi | iptal
    related_email_id INTEGER,
    related_file_path TEXT,
    related_event_id INTEGER,
    related_task_id INTEGER,
    notified_at TEXT,                -- e-posta bildirimi gönderildi mi (tek seferlik)
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_reminders_remind_at ON reminders(remind_at);
CREATE INDEX idx_reminders_status ON reminders(status);
```

Tasks'tan farkı: öncelik/durum/etiket/ilgili-kişi yok — tek satırlık bir not
+ zaman + isteğe bağlı ilişkilendirme. "Gecikmiş" durumu ayrı bir status
değeri değil, `remind_at <= now AND status = 'bekliyor'` olarak hesaplanır
(tasks'taki `tk-overdue` deseniyle aynı yaklaşım).

### awaiting_replies

```sql
CREATE TABLE IF NOT EXISTS awaiting_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER,
    to_email TEXT NOT NULL,
    to_name TEXT,
    subject TEXT,
    message_id TEXT NOT NULL,        -- gönderdiğimiz mailin ürettiğimiz Message-ID'si
    sent_at TEXT DEFAULT (datetime('now')),
    due_at TEXT NOT NULL,            -- sent_at + kullanıcının seçtiği gün sayısı
    status TEXT DEFAULT 'bekliyor',  -- bekliyor | cevaplandi | iptal
    resolved_at TEXT,
    resolved_email_id INTEGER,       -- otomatik eşleşen gelen mail (varsa)
    notified_at TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_awaiting_status ON awaiting_replies(status);
CREATE INDEX idx_awaiting_message_id ON awaiting_replies(message_id);
```

**Oluşturma:** Yeni mail (`/api/compose`) veya yanıt (`/api/emails/{id}/reply`)
gönderilirken kullanıcı isteğe bağlı "Cevap bekliyorum, N gün içinde
hatırlat" kutusunu işaretler. `email_client.send_message`/`send_reply`
`email.utils.make_msgid()` ile bir Message-ID üretip header'a yazar ve bu
ID'yi çağırana döndürür; `awaiting_replies` satırı bu ID ile oluşturulur.

**Otomatik çözümleme:** Yeni mail senkronize edildiğinde (`insert_email`),
gelen mailin `in_reply_to` alanı ya da `refs` alanı içinde bekleyen bir
`awaiting_replies.message_id` geçiyorsa o kayıt otomatik `cevaplandi` olur.
Bu kontrol hem `/api/sync` sonrasında hem zamanlayıcının arka plan
senkronizasyonundan sonra çalışır (tek bir paylaşılan fonksiyon).

**Manuel çözümleme:** Header eşleşmesi bulunamazsa (bazı mail istemcileri
`In-Reply-To`/`References` düzgün set etmez) kullanıcı Bugün ekranından elle
"cevaplandı" işaretleyebilir veya kaydı iptal edebilir.

### donna_conversations / donna_messages

```sql
CREATE TABLE IF NOT EXISTS donna_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT DEFAULT 'Yeni sohbet',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS donna_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL,              -- user | assistant
    content TEXT NOT NULL,
    sources TEXT,                    -- JSON: kaynak mail listesi (varsa)
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_donna_msg_conv ON donna_messages(conversation_id, id);
```

`title`, ilk kullanıcı mesajının ilk ~40 karakterinden otomatik türetilir
(ek AI çağrısı gerektirmez); kullanıcı isterse yeniden adlandırabilir.
`donna_conversations.updated_at`, her yeni mesajda güncellenir (liste en son
konuşulan sohbeti üstte gösterir).

`/api/donna/ask` artık `history` parametresi almaz, `conversation_id` alır
(yoksa yeni konuşma otomatik oluşturulur). Sunucu, `donna_messages`'tan son
N mesajı okuyup `donna.ask_with_tools()`'a aynı `[{role, content}, ...]`
biçiminde geçirir, dönen soru+cevabı DB'ye yazar. `donna.py` içindeki
fonksiyon imzaları değişmez — sadece çağıran taraf (main.py) artık
istemciye güvenmek yerine DB'yi kaynak olarak kullanır.

## Bileşen Tasarımları

### 1. Zamanlayıcı (`app/scheduler.py`)

```python
TICK_SECONDS = 60
SYNC_EVERY_TICKS = 15

async def run_forever():
    tick = 0
    while True:
        tick += 1
        await _safe(_notify_due_reminders)
        await _safe(_resolve_and_notify_awaiting_replies)
        if tick % SYNC_EVERY_TICKS == 0:
            await _safe(_sync_all_accounts)
        await asyncio.sleep(TICK_SECONDS)

async def _safe(fn):
    try:
        fn()
    except Exception:
        log.exception("Zamanlanmış görev başarısız: %s", fn.__name__)
```

- `_notify_due_reminders()`: `remind_at <= now AND status='bekliyor' AND
  notified_at IS NULL` olan kayıtları bulur, varsa ilk hesaptan kendine
  bildirim maili gönderir, `notified_at`'i işaretler. SMTP hatası olursa
  loglanır, `notified_at` işaretlenmez (bir sonraki tick tekrar dener) —
  ama uygulama-içi görünürlük (Bugün ekranı) bundan etkilenmez, çünkü o
  doğrudan `remind_at <= now` hesaplamasına bakar.
- `_resolve_and_notify_awaiting_replies()`: `_resolve_awaiting_replies()`
  (paylaşılan fonksiyon, sync sonrası da çağrılır) + süresi geçmiş/yakın
  kayıtlar için tek seferlik bildirim maili.
- `_sync_all_accounts()`: mevcut `/api/sync` endpoint'inin arkasındaki
  mantığı çağırır (endpoint'ten çıkarılıp paylaşılan bir fonksiyona taşınır).

### 2. Hatırlatmalar

`app/database.py`: `create_reminder`, `list_reminders(status=None, when=None)`,
`get_reminder`, `update_reminder`, `complete_reminder`, `delete_reminder`,
`due_reminders_unnotified()` — Tasks CRUD deseniyle birebir aynı yapı.

`app/main.py`: `/api/reminders` (GET/POST), `/api/reminders/{id}`
(GET/PUT/DELETE), `/api/reminders/{id}/complete` (POST) — Tasks
endpoint'leriyle aynı doğrulama/hata deseni.

Frontend: Ayrı bir rail sekmesi yok — hatırlatmalar Bugün ekranından
oluşturulur/yönetilir (Tasks'taki `openTaskModal` deseninin küçük bir
kopyası: metin + tarih-saat + isteğe bağlı ilişkilendirme).

### 3. Cevap bekliyorum

`app/email_client.py`: `send_message`/`send_reply` artık ürettiği
Message-ID'yi (`str`) döndürür — mevcut çağıranlar dönüş değerini
kullanmadığı için geriye dönük uyumlu.

`app/database.py`: `create_awaiting_reply`, `list_awaiting_replies(status=None)`,
`resolve_awaiting_reply(id, email_id=None)`, `cancel_awaiting_reply(id)`,
`_match_awaiting_reply_for_incoming(email_data)` (yeni gelen mail
`insert_email` edilirken çağrılır).

`app/main.py`: `ComposeRequest` ve `ReplyRequest`'e `await_reply_days:
int | None = None` alanı eklenir; `> 0` ise gönderim başarılı olduktan sonra
`awaiting_replies` kaydı oluşturulur. `/api/awaiting-replies` (GET),
`/api/awaiting-replies/{id}/resolve` (POST), `/api/awaiting-replies/{id}`
(DELETE).

Frontend: Compose ve reply modallarına "Cevap bekliyorum" onay kutusu +
gün seçici eklenir; liste Bugün ekranında gösterilir.

### 4. Kalıcı Donna konuşmaları

`app/database.py`: `create_conversation`, `list_conversations`,
`rename_conversation`, `delete_conversation` (SQLite'ta otomatik CASCADE
yok — fonksiyon önce `donna_messages`'tan `conversation_id` eşleşenleri,
sonra `donna_conversations` satırını siler, tek `get_db()` bloğu içinde),
`add_message`, `get_conversation_messages(id, limit=20)`.

`app/main.py`: `/api/donna/conversations` (GET liste, POST yeni),
`/api/donna/conversations/{id}` (PUT yeniden adlandır, DELETE sil),
`/api/donna/conversations/{id}/messages` (GET geçmiş). `DonnaAskRequest`
`history` yerine `conversation_id: int | None` alır.

Frontend: Donna panelinde küçük bir liste/geçiş ikonu — konuşma listesi
(başlık + son güncelleme), "+ Yeni sohbet", her satırda yeniden adlandır
(satır içi düzenleme) ve sil (onaylı). `donna.history` JS değişkeni
kaldırılır; panel açıldığında aktif `conversation_id`'nin mesajları
sunucudan çekilir.

### 5. Bugün ekranı

`GET /api/today` — tek istekte:

```json
{
  "greeting": "...",
  "summary": "...",          // donna.brief() çıktısından
  "tasks_today": [...],      // due_date <= today, status yapilacak/devam_ediyor
  "reminders_today": [...],  // remind_at bugün içinde, status bekliyor
  "events_today": [...],     // list_events(start_of_today, end_of_today)
  "awaiting_replies": [...], // status bekliyor, due_at geçmiş veya yakın
  "needs_reply_count": 3     // mevcut "awaiting" inbox view sayacı
}
```

Özet metni için yeni bir AI çağrısı icat edilmez — mevcut `donna.brief()`
(`app/donna.py`) tekrar kullanılır. Diğer alanlar saf DB sorgusu, hızlı ve
ücretsiz.

Frontend: Yeni rail sekmesi "Bugün" (varsayılan giriş ekranı **yapılmıyor**
— mevcut "Posta" varsayılan kalır). Kart grid: özet, toplantılar, açık
görevler, hatırlatmalar, cevap bekleyenler, yanıt bekleyen mail sayacı
(inbox'a link).

## Hata Yönetimi

- Zamanlayıcı tick'i asla uygulamayı çökertmez — her iş ayrı `try/except`,
  loglanır, döngü devam eder.
- E-posta bildirimi başarısız olursa (SMTP kapalı, hesap yok) sessizce
  loglanır; uygulama-içi gösterim (Bugün ekranı, `remind_at`/`due_at`
  hesaplaması) buna bağımlı değildir.
- Awaiting-reply otomatik eşleşmesi best-effort'tur (header tabanlı); veri
  kaybı riski yok çünkü kayıt hiç silinmez, sadece durumu değişir — manuel
  çözümleme her zaman mevcuttur.
- Yeni tablolar `CREATE TABLE IF NOT EXISTS` ile eklenir (mevcut `tasks`/
  `bulk_campaigns` deseniyle aynı) — yıkıcı migration gerekmez.
- Tüm yeni `/api/*` uçları mevcut `security_middleware`'den otomatik geçer
  (oturum koruması), ayrıca bir şey yapılması gerekmez.

## Test Stratejisi

`tests/conftest.py`'deki `tmp_db` fixture deseni aynen kullanılır. Yeni test
dosyaları:

- `tests/test_reminders.py` — CRUD + "bugün/gecikmiş" filtreleme
- `tests/test_awaiting_replies.py` — oluşturma, header-eşleşme ile otomatik
  çözümleme, manuel çözümleme/iptal
- `tests/test_donna_conversations.py` — CRUD, mesaj sırası, otomatik başlık
- `tests/test_today.py` — agregatör endpoint'in doğru alanları döndürdüğü
- `tests/test_scheduler.py` — `_notify_due_reminders`,
  `_resolve_and_notify_awaiting_replies` gibi saf fonksiyonlar (gerçek
  `asyncio.sleep` döngüsü test edilmez)

Her fazın sonunda: `pytest tests/ -q` yeşil + curl ile uçtan uca smoke test
(Tasks'ta yapılan yöntemle aynı) + UI değişen fazlarda Playwright ekran
görüntüsü (açık/koyu tema, taşma kontrolü).

## Yapım Sırası

1. **Zamanlayıcı iskeleti** — görünür özellik yok, sadece altyapı + test.
   `lifespan` bağlanması, boş tick döngüsü, log doğrulaması.
2. **Hatırlatmalar** — DB → API → zamanlayıcı bildirimi → Bugün ekranından
   erişilen basit oluşturma/tamamlama/silme UI'ı.
3. **Cevap bekliyorum** — DB → Message-ID yakalama → compose/reply
   entegrasyonu → otomatik+manuel çözümleme → Bugün ekranında liste.
4. **Kalıcı Donna konuşmaları** — DB → API → panel UI (yeni/yeniden
   adlandır/sil/geçiş).
5. **Bugün ekranı** — hepsini birleştiren agregatör endpoint + kart arayüzü
   (4 numaralı adımdan sonra çünkü özet için Donna'yı, hatırlatma/awaiting
   için 2-3 numaralı adımların verisini kullanır).

Her adım bağımsız commit edilebilir ve kendi testleriyle doğrulanabilir.
