# 📬 Meil — E-posta Tasnif & Yanıt Asistanı

Microsoft Teams görünümlü arayüzüyle **birden fazla mail hesabına** (Gmail, Outlook / Microsoft 365, Yahoo, Yandex veya şirket IMAP sunucusu) bağlanır ve:

1. **Tasnif eder** — Gelen mailleri yapay zekâ ile kategorilere ayırır (Önemli, İş, Kişisel, Fatura/Finans, Bülten, Tanıtım/Reklam, Spam, Diğer) ve öncelik atar. Modern posta deneyimi: okundu/okunmadı takibi, yıldızlama, erteleme (snooze), görünüm sekmeleri (Gelen · Yıldızlı · Yanıt Bekleyen · Ertelenen · Arşiv), sıfırdan mail yazma (✎ Yeni, "✨ AI ile Yaz" destekli, CC'li), klavye kısayolları (j/k gezin, e arşivle, s yıldızla, r yanıtla, c yeni mail) ve 5 dakikada bir otomatik eşitleme.
2. **Okur ve özetler** — Her mail için 1-3 cümlelik Türkçe özet çıkarır.
3. **Yanıt önerir** — Yanıt gerektiren mailler için gönderilmeye hazır taslak yazar. Taslağı düzenleyebilir, "Yeniden Öner" ile talimat verebilir ve **sizin onayınızla** gönderirsiniz. Onaysız hiçbir mail gönderilmez.
4. **Dataroom** — Mail ekleri otomatik saklanır; aynı zamanda tam donanımlı bir sanal veri odası: klasör ağacı ve taşıma, belge önizleme (PDF/görsel), not + etiket + favori, süreli paylaşım linkleri (indirme sayaçlı, iptal edilebilir), belgeyi doğrudan mail atma, toplu ZIP indirme/silme ve tüm işlemlerin kaydedildiği etkinlik günlüğü (audit trail).
5. **Takvim** — Apple iCloud (CalDAV) ve Google Takvim (gizli iCal adresi) entegrasyonlu ay görünümü. Yapay zekâ, maillerdeki toplantı/randevu/son tarihleri otomatik tespit eder; tek tıkla yerel takvime veya iCloud takviminize eklersiniz.
6. **Toplu Mail** — Excel/CSV listesindeki adreslere kişiselleştirilmiş toplu mail (mail merge). `{sütun}` yer tutucularıyla her alıcıya özel konu/içerik, HTML veya düz metin, deneme maili, canlı ilerleme takibi.
7. **Donna** — sağ üstteki butondan açılan kişisel asistan. Mail, takvim ve dataroom verilerinin tamamına bakar; panel açılır açılmaz "şu an neye bakmalısın" brifingi verir (acil yanıt bekleyenler, bugünkü etkinlikler, yaklaşan ödemeler) ve istediğinizi sorabilirsiniz. Yanıtları yalnızca gerçek verilerinize dayanır, kaynak mailleri tıklanabilir gösterir. **İşlem de yapar:** maile yanıt yazar, takvime etkinlik ekler/günceller/siler, dataroom'dan belge siler — ama her işlem önce **onay kartı** olarak gösterilir; siz düzenleyip onaylamadan hiçbir şey uygulanmaz.

## Kurulum

### Yerel Geliştirme

```bash
# 1. Bağımlılıkları yükleyin
pip install -r requirements.txt

# 2. Ayar dosyasını oluşturun
cp .env.example .env
# .env dosyasını düzenleyin (aşağıya bakın)

# 3. Başlatın (--reload: kod güncellemelerinde otomatik yeniden başlar)
uvicorn app.main:app --port 8000 --reload
```

> **Güncelleme sonrası:** `git pull` yaptıysanız `pip install -r requirements.txt` çalıştırın ve sunucuyu **yeniden başlatın** — aksi halde arayüz yenilenir ama API eski kalır ve "Method Not Allowed" benzeri hatalar görürsünüz (`--reload` ile başlattıysanız otomatik yenilenir).

Tarayıcıda **http://localhost:8000** adresini açın:

### Üretim Dağıtımı (VPS, PWA, iPhone Kurulumu)

İphone veya Android'e "uygulama gibi" kurulmasını ve https://meil.example.com adresiyle erişilmesini istiyorsanız **[docs/PHASE2_DEPLOYMENT.md](docs/PHASE2_DEPLOYMENT.md)** rehberine bakın. Caddy + Systemd + Let's Encrypt ile adım adım kurulum anlatılıyor.

1. **Hesaplar** sekmesinden mail hesaplarınızı ekleyin — sağlayıcı seçin (Gmail, Outlook / Microsoft 365, Yahoo, Yandex) veya "Şirket / Özel" ile kendi IMAP/SMTP sunucunuzu girin. Uygulama kaydetmeden önce bağlantıyı test eder.
2. Sağ üstteki **"⟳ Eşitle"** butonuna tıklayın — tüm hesapların gelen kutuları taranır ve tasnif edilir.
3. Posta sekmesinde hesaba ve kategoriye göre filtreleyebilirsiniz. Yanıtlar, maili alan hesabın kendi SMTP sunucusundan gönderilir.

## `.env` ayarları

| Değişken | Açıklama |
|---|---|
| `GEMINI_API_KEY` | Google Gemini anahtarı — [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| `GEMINI_MODEL` | Varsayılan `gemini-flash-latest`; daha hızlı/ucuz: `gemini-flash-lite-latest` |
| `NVIDIA_API_KEY` | NVIDIA NIM anahtarı — [build.nvidia.com](https://build.nvidia.com) |
| `NVIDIA_MODEL` | Varsayılan `meta/llama-3.3-70b-instruct` |
| `ANTHROPIC_API_KEY` | Anthropic Claude anahtarı (isteğe bağlı) |
| `AI_PROVIDER` | `auto` (varsayılan), `gemini`, `nvidia` veya `claude`. En az bir anahtar zorunlu |
| `USER_NAME` | Yanıt taslaklarında imza olarak kullanılacak adınız |
| `SYNC_LIMIT` | Her eşitlemede hesap başına işlenecek en fazla mail sayısı (varsayılan 25) |
| `EMAIL_ADDRESS` vb. | İsteğe bağlı — ilk hesabı arayüz yerine buradan tanımlamak isterseniz |

## Takvim entegrasyonu

Takvim sekmesindeki **"Takvim Kaynakları"** bölümünden bağlanır:

| Kaynak | Nasıl | Yetki |
|---|---|---|
| **Apple iCloud** | Apple ID + **uygulama şifresi** ([appleid.apple.com](https://account.apple.com/account/manage) → Oturum Açma ve Güvenlik → Uygulama Şifreleri). Hesaptaki tüm takvimler bağlanır. | Okuma + **etkinlik ekleme** |
| **Google Takvim** | Google Takvim → Ayarlar → takviminiz → "Takvimi entegre et" → **iCal biçiminde gizli adres**i kopyalayın | Salt okunur |
| **Diğer ICS/webcal** | Outlook yayınlama bağlantısı, şirket takvimi vb. herhangi bir ICS adresi | Salt okunur |

Mailde tespit edilen etkinlikler mail detayındaki **"📅 Takvime Ekle"** kartıyla yerel "Meil" takvimine veya iCloud takvimlerinizden birine yazılır. "⟳ Takvimleri Eşitle" butonu harici kaynaklardan etkinlikleri yeniler (geçmiş 30 gün – gelecek 1 yıl).

### Hesap türlerine göre notlar

- **Gmail / Yahoo / Yandex:** Normal şifre çalışmaz; **uygulama şifresi** gerekir (Gmail: [buradan](https://myaccount.google.com/apppasswords), önce 2 Adımlı Doğrulama açık olmalı).
- **Şirket maili (Microsoft dışı):** IMAP/SMTP sunucu adreslerini ve portları BT ekibinizden öğrenin. IMAP genellikle 993 (SSL), SMTP 465 (SSL) veya 587 (STARTTLS) kullanır.
- **Outlook / Microsoft 365:** Aşağıdaki OAuth kurulumu gerekir — şifreyle giriş artık mümkün değil.

## Microsoft 365 / Outlook hesabı bağlama (OAuth)

Microsoft, **Nisan 2026'da** Exchange Online ve Outlook.com'da IMAP/SMTP için
şifreyle girişi (temel kimlik doğrulama) tamamen kapattı. Şifreniz doğru olsa
bile sunucu artık reddeder; tek yol OAuth 2.0'dır. Meil bunun için "Microsoft
ile giriş" (cihaz kodu) akışını destekler. Tek seferlik kurulum:

1. [portal.azure.com](https://portal.azure.com) → **Microsoft Entra ID** →
   **App registrations** → **New registration**.
2. Ad: `Meil` (herhangi bir şey olabilir). *Supported account types*:
   **"Accounts in any organizational directory and personal Microsoft
   accounts"** seçin. Redirect URI **boş** bırakın → **Register**.
3. Açılan sayfada **Application (client) ID** değerini kopyalayın.
4. Sol menü → **Authentication** → en altta **Advanced settings** →
   **"Allow public client flows"** anahtarını **Yes** yapın → **Save**.
5. Kopyaladığınız ID'yi `.env` dosyanıza yazın: `MS_CLIENT_ID=xxxxxxxx-...`
   ve sunucuyu yeniden başlatın.

Sonra uygulamada **Hesaplar → Sağlayıcı: "Outlook / Microsoft 365 (Microsoft
ile giriş)" → Microsoft ile Bağlan**. Ekranda çıkan kodu
[microsoft.com/devicelogin](https://microsoft.com/devicelogin) adresine girin;
giriş tamamlanınca hesap otomatik eklenir. Şifreniz hiçbir yerde saklanmaz —
yalnızca Microsoft'un verdiği (şifrelenmiş) erişim jetonu tutulur.

> **Şirket hesabı notu:** Kuruluşunuz "kullanıcı onayı"nı kapattıysa ilk
> girişte "admin approval required" görebilirsiniz — BT yöneticinizin bir
> kez onay vermesi yeterli. Ayrıca kiracıda IMAP erişimi ve "Authenticated
> SMTP" açık olmalıdır (uygulama kapalıysa anlaşılır bir hata gösterir).

## Nasıl çalışır?

```
Gmail (IMAP) ──► Mail çekilir ──► Ekler dataroom'a kaydedilir
                                   │
                                   ▼
                     Yapay zekâ tasnif eder:
                        kategori + öncelik + özet + yanıt taslağı
                                   │
                                   ▼
                        Web arayüzünde incelersiniz
                                   │
                        "Onayla ve Gönder" ──► Gmail (SMTP)
```

- Mailler yalnızca **okunur** modda çekilir; gelen kutunuzda hiçbir şey değişmez (okundu işareti dahil).
- Aynı konudaki mailler `References`/`In-Reply-To` başlıklarına göre **konuşma dizisi** olarak gruplanır; listede tek satır görünür, detayda tüm yazışma sıralanır ve AI'ya dizinin tamamı özetletilebilir.
- **Global arama (Cmd+K / Ctrl+K)**: tek kutuda mail + dataroom belgesi + takvim etkinliği birlikte aranır; ok tuşlarıyla gezinip Enter ile doğrudan açarsınız. Türkçe karakter katlamalıdır — "hakedis" yazsanız da "hakediş"i bulur.
- **"AI'ya Sor"** ile gelen kutunuza soru sorabilirsiniz ("Ayşe'yle fiyat nede kalmıştı?", "bu hafta hangi faturalar geldi?"): ilgili mailler tam metin aramayla bulunur, yanıt yalnızca bu maillere dayanır ve kaynak mailler tıklanabilir bağlantı olarak gösterilir.
- Dataroom'da **içerik araması** vardır: PDF, Word, Excel, PowerPoint ve metin dosyalarından metin çıkarılır (pypdf + Office XML); arama kutusu dosya adına ek olarak belge içeriğinde de arar ve eşleşen parçayı vurgular. "AI Tara" butonu belgeleri sınıflandırır (fatura, sözleşme, dekont...), özet ve etiket üretir; faturalardan tutar ile son ödeme tarihini çıkarır.
- Yanıtlar yalnızca sizin onayınızla, sizin hesabınızdan `Re:` konusuyla ve doğru konu dizisi (thread) referansıyla gönderilir.
- **Toplu mail** sekmesinde `.xlsx`/`.csv` listesi yüklersiniz (ilk satır başlık, bir sütun e-posta). E-posta sütunu otomatik tahmin edilir; konu ve mesajda `{sütun}` yazarak kişiselleştirirsiniz (ör. `Merhaba {isim}`). Göndermeden önce **önizleme** ve **deneme maili** yapabilir, gönderim sırasında satır satır ilerlemeyi (gönderildi / başarısız / atlandı) canlı izlersiniz. Mailler kendi hesabınızın SMTP'sinden, tek bağlantı üzerinden ve aralarında ayarlanabilir bekleme ile gönderilir — sağlayıcı limitlerine takılmamak için. Geçersiz adresler atlanır; HTML seçilirse düz metin alternatifi de eklenir. Not: Gmail gibi sağlayıcıların günlük gönderim limiti vardır (kişisel hesaplarda ~500/gün) ve toplu gönderimde yasal izin/onay sorumluluğu size aittir.
- Tüm veriler yerel `data/` klasöründe tutulur (SQLite + dosyalar).

## Güvenlik notları

- Uygulama **PIN ile korunur**: ilk açılışta PIN belirlersiniz; sonraki her girişte sorulur. PIN, PBKDF2-SHA256 ile özetlenir (düz metin saklanmaz); 5 hatalı denemede 60 saniye kilit devreye girer. Oturum 30 gün hatırlanır. Tüm API uçları oturum ister — yalnızca dataroom paylaşım linkleri (tasarım gereği) açıktır.
- **Telefona kurulum (PWA):** Sunucuyu `--host 0.0.0.0` ile başlatıp iPhone'da Safari → Paylaş → **Ana Ekrana Ekle** deyin; Meil kendi ikonuyla tam ekran uygulama gibi açılır. App Store planı için `docs/APP_STORE_YOL_HARITASI.md` dosyasına bakın.
- Hesap ve takvim şifreleri veritabanında **şifreli** (Fernet/AES) saklanır; düz metin tutulmaz. Eski kayıtlar ilk açılışta otomatik şifrelenir.
- Şifreleme anahtarı öncelikle `MEIL_SECRET_KEY` ortam değişkeninden okunur; tanımlı değilse `data/secret.key` otomatik üretilir. Anahtarı `.env`'e taşımanız önerilir — böylece `meil.db` dosyası tek başına sızsa bile şifreler çözülemez. **Anahtarı kaybederseniz** kayıtlı şifreler geri getirilemez; hesapları arayüzden yeniden eklemeniz gerekir.
- `.env` dosyası `.gitignore`'dadır — şifrelerinizi asla commit etmeyin.
- Uygulama şifresini istediğiniz an Google hesabınızdan iptal edebilirsiniz.
- Mail içerikleri tasnif için seçili yapay zekâ sağlayıcısına gönderilir. **Birden fazla sağlayıcı** (Gemini, NVIDIA NIM, Claude) tanımlayabilirsiniz: **Otomatik** modda Meil ölçtüğü gecikmeye göre en hızlısını kullanır, biri hata verirse diğerine geçer ve hatalı olanı bir süre devre dışı bırakır. Sağ üst menü → **Yapay Zekâ Modeli** ekranından sağlayıcıyı elle seçebilir, her birini "Test Et" ile sınayabilirsiniz.
